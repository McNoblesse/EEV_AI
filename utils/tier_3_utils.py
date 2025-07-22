import os
import sqlite3
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage, ToolMessage
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from typing import TypedDict, List, Annotated
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_openai import ChatOpenAI

from config.access_keys import accessKeys

# DEFINE THE STRUCTURED OUTPUT MODEL
class AnalyzedQuery(BaseModel):
    """A model to hold the structured analysis of a user's query."""
    intent: str = Field(description="Classify the user's intent. Must be one of: 'technical_question', 'greeting', 'general_chat'.")
    sentiment: str = Field(description="The user's sentiment, e.g., 'positive', 'neutral', 'negative'.")
    complexity_score: int = Field(description="A score from 1-10 for query difficulty.")
    response: str = Field(description="A natural, human-like response to the user's message. This is what the user will see.")

os.environ["GOOGLE_API_KEY"] = accessKeys.GEMINI_API_KEY
os.environ["OPENAI_API_KEY"] = accessKeys.OPENAI_API_KEY

SQLITE_DB = accessKeys.SQLITE_DB_PATH

embed_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

pc = Pinecone(api_key=accessKeys.pinecone_api)
spec = ServerlessSpec(cloud="aws", region="us-east-1")
index_name = 'eev-ai-unstructured-data'
index = pc.Index(index_name)
vectorstore = PineconeVectorStore(index=index, embedding=embed_model, text_key="text")

# UPDATE THE GRAPH'S STATE
class MessagesState(TypedDict):
  messages: Annotated[List[AnyMessage], add_messages]
  analysis: AnalyzedQuery

llm = ChatOpenAI(model="gpt-4o-mini-2024-07-18")

@tool
def retriever_tool(query: str) -> str:
    """Retrieve FAQ data for Optimus or Branch systems."""
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

# DEFINE THE PROMPT TEMPLATE
# This single, detailed prompt will be used for both chains.
prompt = ChatPromptTemplate.from_messages([
    ("system", """
    You are Alex, a friendly and knowledgeable EEV AI customer support specialist. You have a warm, conversational personality and genuinely care about helping customers solve their problems.
    Your primary task is to analyze the user's message and provide a structured response containing your analysis (intent, sentiment) and a human-like reply.
    Based on the user's message, first determine the intent, sentiment, and complexity. Then, formulate a helpful, conversational response.
    If the user asks a specific technical question that requires looking up information, you MUST call the `retriever_tool`. For greetings or general chat, you should respond directly without using any tools.
    After the tool has been called and you have the information, you MUST then provide the final structured analysis and response.
    """),
    MessagesPlaceholder(variable_name="messages")
])


# A chain for the agent to decide whether to call a tool
tool_calling_chain = prompt | llm.bind_tools(tools)

# A chain for the final node to generate the structured output
structured_output_chain = prompt | llm.with_structured_output(AnalyzedQuery)

def customer_agent_node(state: MessagesState):
    """This node's only job is to decide if a tool is needed."""
    response_message = tool_calling_chain.invoke({"messages": state["messages"]})
    return {"messages": [response_message]}

def structured_output_node(state: MessagesState):
    """This node's only job is to generate the final structured response."""
    analysis_result = structured_output_chain.invoke({"messages": state["messages"]})
    # We add the bot's final text response to the message history
    # and the full analysis object to the 'analysis' field in the state.
    return {
        "messages": [AIMessage(content=analysis_result.response)],
        "analysis": analysis_result
    }

# DEFINE CONDITIONAL LOGIC
def tool_conditions(state: MessagesState):
    """A more robust conditional check."""
    last_message = state["messages"][-1]
    # If the last message has tool_calls, we route to the tool_node
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "continue_tool"
    # If the last message is a ToolMessage, it means the tool has just run.
    # We should go back to the agent to let it process the new info.
    if isinstance(last_message, ToolMessage):
        return "continue_agent"
    # Otherwise, we're ready to generate the final response.
    else:
        return "end"

# Use the synchronous SqliteSaver with a direct connection
conn = sqlite3.connect(SQLITE_DB, check_same_thread=False)
memory = SqliteSaver(conn=conn)

workflow = StateGraph(MessagesState)

workflow.add_node("agent", customer_agent_node)
workflow.add_node("tool_node", tool_node)
workflow.add_node("final_answer_node", structured_output_node)

workflow.set_entry_point("agent")

workflow.add_conditional_edges(
    "agent",
    tool_conditions,
    {
        "continue_tool": "tool_node",
        "end": "final_answer_node",
    },
)

workflow.add_edge("tool_node", "agent")
workflow.add_edge("final_answer_node", END)

graph = workflow.compile(checkpointer=memory)

def invoke_agent_with_analysis(user_input: str, session_id: str) -> AnalyzedQuery:
    """
    Invokes the LangGraph agent synchronously and returns the final structured analysis.
    """
    config = {"configurable": {"thread_id": session_id}}
    messages = [HumanMessage(content=user_input)]
    
    final_state = graph.invoke({"messages": messages}, config=config)
    
    analysis_result = final_state['analysis']
    return analysis_result