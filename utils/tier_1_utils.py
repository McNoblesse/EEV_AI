import os
import sqlite3
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from langgraph.graph.message import add_messages, AnyMessage
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from typing import TypedDict, List, Annotated
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver

from config.access_keys import accessKeys

os.environ["GOOGLE_API_KEY"] = accessKeys.GEMINI_API_KEY
os.environ["OPENAI_API_KEY"] = accessKeys.OPENAI_API_KEY

embed_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

pc = Pinecone(api_key=accessKeys.pinecone_api)

spec = ServerlessSpec(
    cloud="aws", region="us-east-1"
)

index_name = 'eev-ai-unstructured-data'

index = pc.Index(index_name)

vectorstore = PineconeVectorStore(
    index=index,
    embedding=embed_model,
    text_key="text"
)

class MessagesState(TypedDict):
  messages: Annotated[List[AnyMessage], add_messages]

llm = ChatOpenAI(model_name="gpt-4o-mini-2024-07-18")

@tool
def retriever_tool(query: str) -> str:
    """
    Retrieve FAQ data for Optimus or Branch systems.

    Args:
        source (str): The source of FAQs to retrieve. Accepted values are "optimus" or "branch".
        query (str): The user's question or search phrase used to find a matching FAQ.

    Returns:
        str: The most relevant FAQ response or an appropriate message if no match is found.
    """

    if not query.strip():
        return "Error: Please provide a search query"

    try:
        results = vectorstore.similarity_search(query.strip(), k=3)

        if not results:
            return f"No information found for '{query}'"

        output = ""
        for i, doc in enumerate(results, 1):
            text = doc.metadata.get('text', doc.page_content)
            output += f"Result {i}: {text}\n\n"

        return output

    except Exception as e:
        return f"Search failed: {str(e)}"

tools = [retriever_tool]

tool_node = ToolNode(tools=tools)

llm_with_tools = llm.bind_tools(tools)

prompt = ChatPromptTemplate.from_messages([
    ("system", """
    You are a helpful customer support assistant.

    CRITICAL INSTRUCTION: For simple greetings like "Hi", "Hello", "Good morning", etc., respond directly with a friendly greeting. DO NOT use any tools for greetings.

    Only use the retriever_tool when the user asks a specific question that requires looking up information.
    """),
    MessagesPlaceholder(variable_name="messages")
])

chain = prompt | llm_with_tools

def CustomerAgent(state: MessagesState):
  user_input = state["messages"]
  response = chain.invoke({"messages": user_input})
  return {"messages": [response]}

def tool_conditions(state: MessagesState):
    messages = state["messages"]
    last_message = messages[-1]

    # Check if the last message has tool_calls
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "continue"  # Go to tools
    else:
        return "end"  # End the conversation

sqlite_conn = sqlite3.connect("checkpoint.sqlite", check_same_thread=False)

memory = SqliteSaver(sqlite_conn)

workflow = StateGraph(MessagesState)

workflow.add_node("agent", CustomerAgent)
workflow.add_node("tool_node", tool_node)


workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", tool_conditions, {
    "continue": "tool_node",
    "end": END
})

workflow.add_edge("tool_node", "agent")

graph = workflow.compile(checkpointer=memory)

