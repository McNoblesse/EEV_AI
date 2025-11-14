from uuid import uuid4
import asyncio, tempfile
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from pinecone import Pinecone, ServerlessSpec
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_pinecone.vectorstores import PineconeVectorStore
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_community.document_loaders.parsers import LLMImageBlobParser
from langchain_google_genai import ChatGoogleGenerativeAI

from app.api.logger.api_logs import logger
from app.schemas.agent_schemas import UserQueryAnalysisSchema
from app.schemas.agent_schemas import CategorizeChatFunc, ConversationLogClassification

import os
from app.eev_configurations.config import settings
os.environ["GOOGLE_API_KEY"] = settings.GEMINI_API_KEY
os.environ["PINECONE_API_KEY"] = settings.PINECONE_API_KEY
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

embeddings = OpenAIEmbeddings(model=settings.OPENAI_EMBEDDING_NAME)

pc = Pinecone()

# Knowledge Base toolkit
def InitializeVectorStore(index_name:str):
    index = pc.Index(index_name)
    vectorstore = PineconeVectorStore(index=index, embedding=embeddings)
    retriever = vectorstore.as_retriever()

    prompt = PromptTemplate(
    input_variables=["context", "question"],
    template="""You are a helpful customer service AI assistant for eeV AI Platform. Your job is to provide clear and accurate answers to customer questions.

INSTRUCTIONS:
- Use only the information in the context below.
- Consider the conversation history to understand the full context of the question.
- Do NOT mention or reference the "knowledge base" in any form.
- Give short, direct, and complete answers.
- Provide step-by-step instructions when needed.
- Keep a friendly and professional tone.
- If the answer isn't in the context, say so clearly and suggest contacting support.
- Focus on helping the customer solve the issue on their own.
- If the question references something from earlier in the conversation, use that context.

CONTEXT:
{context}

CONVERSATION HISTORY + CUSTOMER QUESTION:
{question}

RESPONSE:"""
)

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

    # Knowledge Base toolkit
    return RetrievalQA.from_llm(llm=llm, 
                                retriever=retriever,
                                prompt=prompt, 
                                return_source_documents=True)

# Data Generation toolkit
async def GenerateDataFromUserQuery(query: str):
    data_gen_llm = ChatOpenAI(model="gpt-5-mini")

    prompt = ChatPromptTemplate.from_template("""
    You are an intelligent classifier. 
    Analyze the following user query and return:
    1. The intent — what the user wants to achieve.
    2. The sentiment — positive, negative, or neutral.
    3. The complexity_score — rate the complexity of understanding or responding (1-10 scale).

    User Query: {question}
    """)

    data_gen_chain = prompt | data_gen_llm.with_structured_output(UserQueryAnalysisSchema)

    return await data_gen_chain.ainvoke({"question": query})


# Knowledge Base toolkit
def DoesIndexExist(index_name: str):
    existing_indexes = [i["name"] for i in pc.list_indexes()]
    return index_name in existing_indexes

async def BatchUpload(extracted_data, vector_store, batch_size: int = 100):
    for i in range(0, len(extracted_data), batch_size):
        batch_docs = extracted_data[i:i + batch_size]
        batch_uuids = [str(uuid4()) for _ in range(len(batch_docs))]
        try:
            vector_store.add_documents(documents=batch_docs, ids=batch_uuids)
            logger.info(f"Uploaded batch {i // batch_size + 1} ({len(batch_docs)} documents)")
        except Exception as e:
            logger.error(f"Error in batch {i // batch_size + 1}: {e}")
            logger.info("Retrying in 3 seconds...")
            await asyncio.sleep(3)
            vector_store.add_documents(documents=batch_docs, ids=batch_uuids)
            logger.info(f"Uploaded batch {i // batch_size + 1} ({len(batch_docs)} documents)")


# Extract and split content from uploaded file
async def ExtractAndSplitContentFromFile(upload_file, doc_id: str = None):
    # Extract file extension
    filename = upload_file.filename.lower()
    file_ext = filename.split(".")[-1]

    # Read the file content in bytes
    file_bytes = await upload_file.read()

    # Create a temporary file with proper extension
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
        temp_file.write(file_bytes)
        temp_file.flush()
        temp_path = temp_file.name

    try:
        # Select the right loader
        if file_ext in ["pdf", "txt", "docx", "doc", "docm"]:
            loader = PyMuPDFLoader(
                file_path=temp_path,
                mode="page",
                images_inner_format="markdown-img",
                images_parser=LLMImageBlobParser(model=ChatOpenAI(model="gpt-4o", max_tokens=1024)),
            )

        else:
            raise ValueError(f"Unsupported file type: {file_ext}")

        docs = loader.load()
        
        for doc in docs:
            doc.metadata["doc_id"] = doc_id.lower()
            
        logger.info(f"Extracted {len(docs)} documents from {upload_file.filename}")
        return docs

    finally:
        # Always clean up temp file
        os.remove(temp_path)


# Embed documents into Pinecone index
async def EmbeddDoc(index_name: str, extracted_data):
    if DoesIndexExist(index_name):
        vector_store = PineconeVectorStore(
            index=pc.Index(index_name),
            embedding=embeddings
        )
        await BatchUpload(extracted_data, vector_store)
    else:
        logger.info(f"Index '{index_name}' not found. Creating index...")
        pc.create_index(
            name=index_name,
            dimension=3072,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        logger.info("Index created.")
        vector_store = PineconeVectorStore(
            index=pc.Index(index_name),
            embedding=embeddings
        )
        await BatchUpload(extracted_data, vector_store)
    

# Delete Knowledge Base toolkit
async def DeleteIndex(index_name: str, doc_id: str):
    vectorstore = PineconeVectorStore.from_existing_index(
        index_name=index_name,
        embedding=embeddings
    )
    if DoesIndexExist(index_name):
        vectorstore.delete(filter={"doc_id":{"$eq": doc_id}})
        logger.info(f"Document '{doc_id}' deleted successfully from index '{index_name}'.")
    else:
        logger.warning(f"Index '{index_name}' does not exist. Cannot delete.")
        
# Categorize Chat toolkit
async def CategorizeChat(category:list[str], Chatlog: str):
    CategorizeChat = CategorizeChatFunc(category)  
    categorization_llm = ChatOpenAI(model="gpt-5-mini")
    prompt = ChatPromptTemplate.from_template("""
    You are an intelligent chat categorizer. 
    Analyze the following user query and assign the most appropriate category from the provided list.
    
    User Query: {question}
    """)
    categorization_chain = prompt | categorization_llm.with_structured_output(CategorizeChat)
    return await categorization_chain.ainvoke({"question": Chatlog})

# Classifiy Conversation Log toolkit
async def ClassifyConversationLog(chat_log: str):
    classification_llm = ChatOpenAI(model="gpt-5-mini")
    prompt = ChatPromptTemplate.from_template("""
    You are an intelligent classifier. 
    Analyze the following chat log with timestamps and determine if the conversation has ended or not.
    
    Consider these indicators:
    - Explicit goodbye messages (bye, goodbye, see you, talk later, etc.)
    - Natural conversation closures (thanks + acknowledgment, problem resolved)
    - Topic resolution followed by no new questions
    - Time gaps between messages (long silences may indicate conversation end)
    - Message frequency patterns (slowing down, one-word responses)
    - Time of day (late night messages followed by long gap might be natural sleep)
    - Last message sentiment and completeness
    
    Pay special attention to:
    - How much time has passed since the last message
    - Whether the last message feels like a natural endpoint
    - The overall conversation flow and rhythm
    
    Chat Log with Timestamps:
    {chat_log}
    
    Provide your classification with clear reasoning, including temporal analysis.
    """)
    classification_chain = prompt | classification_llm.with_structured_output(ConversationLogClassification)
    return await classification_chain.ainvoke({"chat_log": chat_log})

