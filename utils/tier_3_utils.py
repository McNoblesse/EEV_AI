import os
import sqlite3
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage, ToolMessage
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from typing import TypedDict, List, Annotated, Optional, Any
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_openai import ChatOpenAI
from utils.tools import send_mail_to_human_agent_sync, retriever_tool
from langgraph.checkpoint.postgres import PostgresSaver 
from psycopg import Connection

from config.access_keys import accessKeys

# DEFINE THE STRUCTURED OUTPUT MODEL
class ComprehensiveAnalysis(BaseModel):
    """Complete analysis of user query in one structured output"""
    intent: str = Field(description="Primary intent: technical_question, product_inquiry, greeting, etc.")
    intent_confidence: float = Field(description="Confidence score 0.0-1.0")
    sub_intent: str = Field(description="More specific intent category")
    
    sentiment: str = Field(description="positive, negative, or neutral")
    sentiment_score: float = Field(description="Sentiment intensity -1.0 to 1.0")
    
    complexity_score: int = Field(description="Query complexity 1-10")
    complexity_factors: List[str] = Field(description="What makes the users query complex")
    
    entities: List[str] = Field(description="Key entities: products, technologies, issues")
    keywords: List[str] = Field(description="Important keywords from the users query")
    
    user_type: str = Field(description="technical, business, or general")
    
    response: str = Field(description="The actual response to send to user")
    
    reasoning: str = Field(description="Why these classifications were made")


os.environ["OPENAI_API_KEY"] = accessKeys.OPENAI_API_KEY

DB_URI = accessKeys.POSTGRES_MEMORY_URL

connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": 0,
}

conn = Connection.connect(DB_URI, **connection_kwargs)
checkpointer = PostgresSaver(conn)
checkpointer.setup()

# UPDATE THE GRAPH'S STATE to use enhanced analysis
class MessagesState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    analysis: Optional[ComprehensiveAnalysis]

llm = ChatOpenAI(model="gpt-4o-mini-2024-07-18", temperature=0.1)  

tools = [retriever_tool, send_mail_to_human_agent_sync ]
tool_node = ToolNode(tools=tools)

#customer agent prompt
agent_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are eev AI, a professional and helpful AI assistant. Your job is to provide clear, accurate, and concise answers to the user's query. Maintain a formal and respectful tone at all times.

Here is a pre-analysis of the user's latest message to help you decide what to do. Use this analysis to form a better response and decide if you need to use a tool.

[PRE-ANALYSIS OF USER'S QUERY]:
{analysis_summary}

You have access to two tools:
1. retriever_tool: Contains basic info about estrabillio, optimus ai and branch. Use this for information-based queries.
2. send_mail_to_human_agent_sync: Use this to escalate queries to a human agent if the information is not sufficient or the user's request is too complex.
"""),
    MessagesPlaceholder(variable_name="query")
])

finalizer_prompt = ChatPromptTemplate.from_messages([
    ("system", """
    You are a comprehensive query analyzer. Analyze the user's message and provide detailed structured output including:

    1. INTENT CLASSIFICATION: Determine primary intent (technical_question, product_inquiry, greeting, sales_inquiry, complaint, etc.) with confidence score
    2. SENTIMENT ANALYSIS: Classify sentiment (positive/negative/neutral) with intensity score (-1.0 to 1.0)
    3. COMPLEXITY ASSESSMENT: Rate complexity 1-10 and identify contributing factors
    4. ENTITY EXTRACTION: Identify key entities (products, technologies, issues, names)
    5. KEYWORD EXTRACTION: Extract important keywords and phrases
    6. USER TYPE: Classify as technical, business, or general user based on language
    7. RESPONSE GENERATION: Create a helpful, empathetic first-draft response.
    8. REASONING: Explain your classification decisions

    Be thorough and accurate in your analysis.
    """),
    MessagesPlaceholder(variable_name="message")
])

# A chain for the agent to decide whether to call a tool
tool_calling_chain = agent_prompt | llm.bind_tools(tools)

# A chain for the final node to generate the structured output
structured_output_chain = finalizer_prompt | llm.with_structured_output(ComprehensiveAnalysis)

def analyse_query(state: MessagesState):
    user_query = state["messages"]

    analysis_input = [user_query[-1]]

    final_response = structured_output_chain.invoke({"message": analysis_input})

    return {"analysis": final_response}

def customer_agent_node(state: MessagesState):
    # Get both the analysis object and the message history from the state
    analysis = state["analysis"]
    messages = state["messages"]

    # Format the analysis into a string for the prompt
    analysis_summary = f"""
    - Intent: {analysis.intent} (Confidence: {analysis.intent_confidence:.2f})
    - Sentiment: {analysis.sentiment} (Score: {analysis.sentiment_score:.2f})
    - Complexity: {analysis.complexity_score}/10
    - Key Entities: {', '.join(analysis.entities)}
    - AI's initial thought for a response: "{analysis.response}"
    """
    # Invoke the chain, passing BOTH the analysis and the message history
    agent_response = tool_calling_chain.invoke({
        "analysis_summary": analysis_summary,
        "query": messages
    })

    return {"messages": [agent_response]}

def tools_condition(state: MessagesState):
    messages = state.get("messages", [])
    if not messages:
        raise ValueError("No messages found in state")

    ai_message = messages[-1]

    # Check if the last message has tool calls
    if hasattr(ai_message, "tool_calls") and ai_message.tool_calls:
        # Count all previous tool calls in the conversation
        tool_call_count = sum(
            1 for msg in messages if hasattr(msg, "tool_calls") and msg.tool_calls
        )

        if tool_call_count < 3:
            return "tools"

    return "end"


workflow = StateGraph(MessagesState)

#creating the nodes
workflow.add_node("agent", customer_agent_node)
workflow.add_node("tools", tool_node)
workflow.add_node("analyse", analyse_query)

#edges
workflow.add_edge(START, "analyse")
workflow.add_edge("analyse", "agent")
workflow.add_conditional_edges("agent", tools_condition, {
    "tools": "tools",
    "end": END
})
workflow.add_edge("tools", "agent")

def invoke_agent_with_analysis(user_input: str, session_id: str):
    """
    Enhanced invocation with comprehensive NLP analysis.
    This function now compiles the graph on each call to ensure thread safety.
    """

    graph = workflow.compile(checkpointer=checkpointer)

    
    config = {"configurable": {"thread_id": session_id}}
    
    # The input for the graph includes the new message and the analysis object.
    graph_input = {
        "messages": [HumanMessage(content=user_input)]
    }
    
    # The graph is invoked with the new input and the config.
    final_state = graph.invoke(graph_input, config=config)
    return final_state