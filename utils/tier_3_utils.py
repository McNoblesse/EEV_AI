import os
import logging
from typing import Any, List, Optional, Dict
from pydantic import BaseModel
from psycopg import Connection

from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langgraph.checkpoint.postgres import PostgresSaver

from utils.state_shapes import ComprehensiveAnalysis, AgentState, QueryComplexity, IntentType
from utils.tools import send_mail_to_human_agent_sync, retriever_tool, greeting_response_tool
from config.access_keys import accessKeys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add Reasoning model for structured output
class Reasoning(BaseModel):
    reasoning: str
    next_step: str  # e.g., "retrieve", "respond", "escalate"

# Postgres DSN resolution
def get_postgres_dsn():
    postgres_dsn = getattr(accessKeys, "POSTGRES_MEMORY_URL", None) or getattr(accessKeys, "POSTGRES_URL", None)
    if not postgres_dsn:
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USERNAME")
        db_password = os.getenv("DB_PASSWORD")
        if all([db_host, db_name, db_user, db_password]):
            postgres_dsn = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    if not postgres_dsn:
        raise RuntimeError("No PostgreSQL DSN found for PostgresSaver. Set POSTGRES_MEMORY_URL or DB_* env vars.")
    return postgres_dsn

# Initialize checkpointer
postgres_dsn = get_postgres_dsn()
connection_kwargs = {"autocommit": True, "prepare_threshold": 0}
conn = Connection.connect(postgres_dsn, **connection_kwargs)
checkpointer = PostgresSaver(conn)
checkpointer.setup()

# LLM and tools
llm = ChatOpenAI(model="gpt-4o-mini-2024-07-18", temperature=0.0)
tools = [retriever_tool, send_mail_to_human_agent_sync, greeting_response_tool]
tool_node = ToolNode(tools=tools)

# Prompts for different stages
reasoning_prompt = ChatPromptTemplate.from_messages([
    ("system", """As eeV Assistant, reason step-by-step with empathy about the analysis. Use history to inform decisions—recall patterns, past issues, or preferences.

Determine the next step: 'retrieve' if knowledge is needed, 'respond' for direct answers, 'escalate' if human help is required. Keep reasoning concise (under 100 words).

For summarization requests: Note that a summary is needed, but do not generate it here.
"""),
    ("human", "Analysis: {analysis}\n\nUser Query: {current_input}\n\nHistory Summary: {history_summary}")
])

analysis_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are eeV Assistant, a friendly and knowledgeable customer support agent for Optimus AI Lab. Analyze the user's input precisely, considering conversation history for context.

Detect specific intents (e.g., 'product_inquiry' for chefbot building, not just 'general_question'). Use history to refine analysis.

Available Tools: retriever_tool, send_mail_to_human_agent_sync, greeting_response_tool.
"""),
    MessagesPlaceholder(variable_name="messages")
])

response_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are eeV Assistant, a friendly customer support agent. Respond conversationally, empathetically, and proactively.

Guidelines:
- Use history for context: Reference past discussions naturally (e.g., "Building on our last chat...").
- For summaries: Provide a warm recap (e.g., "From what we've discussed so far...").
- Be engaging: End with questions to continue the conversation.
- Maintain persona: Friendly, knowledgeable, and supportive.

Context: {context}
Analysis: {analysis}
Reasoning: {reasoning}
History Summary: {history_summary}
"""),
    MessagesPlaceholder(variable_name="messages")
])

# Node functions
def analyze_query(state: AgentState) -> AgentState:
    """Analyze the user query and determine routing, with history summarization."""
    messages = state.get("messages", [])
    current_input = state.get("current_input", "")
    
    if not messages and not current_input:
        raise ValueError("No input to analyze")
    
    # Get the latest user message
    user_message = current_input
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break
    
    # Generate history summary for context using LLM for accuracy
    history_summary = ""
    if len(messages) > 1:  # More than just the current message
        past_messages = [msg.content for msg in messages[:-1] if isinstance(msg, (HumanMessage, AIMessage))]
        if past_messages:
            history_text = "\n".join(past_messages)
            # Use LLM to generate a concise summary
            summarization_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a helpful assistant. Summarize the conversation history concisely, focusing on key points, user issues, and resolutions. Keep it under 200 words."),
                ("human", "{history}")
            ])
            summarization_chain = summarization_prompt | llm
            summary_result = summarization_chain.invoke({"history": history_text})
            history_summary = summary_result.content
            # If summarization explicitly requested, enhance the summary
            if any(word in user_message.lower() for word in ['summarize', 'recall', 'what did we talk about', 'summary']):
                history_summary = f"Conversation recap: {history_summary}"
    # Create analysis chain
    analysis_chain = analysis_prompt | llm.with_structured_output(ComprehensiveAnalysis)
    
    # Prepare input for analysis, including history
    analysis_input = {
        "messages": [HumanMessage(content=user_message)],
        "history_summary": history_summary
    }
    analysis_result = analysis_chain.invoke(analysis_input)
    
    # Determine next step based on analysis
    next_step = determine_next_step(analysis_result, user_message)
    
    return {
        "analysis": analysis_result,
        "next_step": next_step,
        "current_step": 1,
        "reasoning_steps": [f"Analysis complete: {analysis_result.intent.value}, complexity: {analysis_result.complexity.value}"],
        "history_summary": history_summary  # Pass to other nodes
    }

def determine_next_step(analysis: ComprehensiveAnalysis, user_input: str) -> str:
    """Determine the next step based on analysis"""
    user_input_lower = user_input.lower()
    
    # Simple greetings and basic questions - use greeting tool or respond directly
    if (analysis.intent == IntentType.greeting or
        analysis.complexity == QueryComplexity.simple or
        any(word in user_input_lower for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'thank'])):
        return "respond"
    
    # Requires knowledge base lookup
    if analysis.requires_knowledge_base or analysis.complexity in [QueryComplexity.moderate, QueryComplexity.complex]:
        return "retrieve"
    
    # Immediate escalation
    if analysis.requires_human_escalation or analysis.complexity == QueryComplexity.escalate:
        return "escalate"
    
    # Default to retrieval for most cases
    return "retrieve"

def reason_and_plan(state: AgentState) -> Dict[str, Any]:
    """Reason about the analysis and plan next steps, using history."""
    analysis = state.get("analysis")
    current_input = state.get("current_input", "")
    history_summary = state.get("history_summary", "")
    
    if not analysis:
        raise ValueError("No analysis available for reasoning")
    
    reasoning_chain = reasoning_prompt | llm.with_structured_output(Reasoning)
    reasoning_input = {
        "analysis": analysis.model_dump_json(),
        "current_input": current_input,
        "history_summary": history_summary
    }
    
    reasoning_result = reasoning_chain.invoke(reasoning_input)
    reasoning_steps = state.get("reasoning_steps", [])
    reasoning_steps.append(f"Reasoning: {reasoning_result.reasoning}")
    
    # Use structured next_step
    next_step = reasoning_result.next_step
    if analysis.requires_human_escalation:
        next_step = "escalate"
    
    return {
        "reasoning_steps": reasoning_steps,
        "next_step": next_step,
        "current_step": state.get("current_step", 0) + 1
    }

def retrieve_knowledge(state: AgentState) -> AgentState:
    """Retrieve relevant knowledge from vector database"""
    analysis = state.get("analysis")
    current_input = state.get("current_input", "")
    
    if not analysis:
        raise ValueError("No analysis available for retrieval")
    
    # Build search query from analysis
    search_terms = analysis.keywords + [entity.text for entity in analysis.entities]
    search_query = " ".join(search_terms) if search_terms else current_input
    
    try:
        kb_results = retriever_tool.invoke({"query": search_query})
        retrieved_context = [kb_results] if isinstance(kb_results, str) else kb_results
    except Exception as e:
        logger.warning(f"Knowledge retrieval failed: {e}")
        retrieved_context = ["No relevant information found."]
    
    return {
        "knowledge_base_results": "\n".join(retrieved_context) if isinstance(retrieved_context, list) else retrieved_context,
        "retrieved_context": retrieved_context,
        "next_step": "respond",
        "reasoning_steps": state.get("reasoning_steps", []) + [f"Retrieved {len(retrieved_context)} context items"]
    }

def generate_response(state: AgentState) -> AgentState:
    """Generate final response based on analysis and context, with persona and history."""
    analysis = state.get("analysis")
    messages = state.get("messages", [])
    kb_results = state.get("knowledge_base_results", "")
    reasoning_steps = state.get("reasoning_steps", [])
    history_summary = state.get("history_summary", "")
    
    if not analysis:
        raise ValueError("No analysis available for response generation")
    
    # Set conversation_summary from history if available
    if history_summary:
        analysis.conversation_summary = history_summary
    
    # For simple greetings, use the greeting tool
    if analysis.intent == IntentType.greeting or analysis.complexity == QueryComplexity.simple:
        try:
            greeting_response = greeting_response_tool.invoke({"user_message": state.get("current_input", "")})
            analysis.response = greeting_response
        except Exception as e:
            logger.warning(f"Greeting tool failed, using default: {e}")
            analysis.response = "Hello! I'm eeV Assistant, here to help with all your questions. What can I assist you with today?"
    else:
        # Prepare context for response generation
        context = f"Knowledge Base: {kb_results}" if kb_results else "No additional context available."
        
        # Include history in context
        if history_summary:
            context += f"\nConversation History: {history_summary}"
        
        # Enhanced response generation with persona
        response_chain = response_prompt | llm
        response_input = {
            "context": context,
            "analysis": analysis.json(),
            "reasoning": "\n".join(reasoning_steps[-3:]),  # Last 3 reasoning steps
            "messages": messages,
            "history_summary": history_summary
        }
        
        response_result = response_chain.invoke(response_input)
        analysis.response = response_result.content
    
    # Update messages with response
    response_message = AIMessage(content=analysis.response)
    
    return {
        "analysis": analysis,
        "messages": messages + [response_message],
        "next_step": "end",
        "reasoning_steps": reasoning_steps + [f"Response generated: {len(analysis.response)} characters"]
    }

def escalate_to_human(state: AgentState) -> AgentState:
    """Escalate the conversation to a human agent"""
    analysis = state.get("analysis")
    current_input = state.get("current_input", "")
    session_id = state.get("session_id", "unknown")
    
    if not analysis:
        raise ValueError("No analysis available for escalation")
    
    # Prepare escalation email
    escalation_subject = f"Escalation Required: {analysis.intent.value} - Complexity: {analysis.complexity.value}"
    escalation_body = f"""
    <html>
    <body>
        <h2>Customer Support Escalation</h2>
        <p><strong>Session ID:</strong> {session_id}</p>
        <p><strong>Intent:</strong> {analysis.intent.value}</p>
        <p><strong>Complexity:</strong> {analysis.complexity.value}</p>
        <p><strong>Sentiment:</strong> {analysis.sentiment} (score: {analysis.sentiment_score})</p>
        <p><strong>User Query:</strong> {current_input}</p>
        <p><strong>Analysis:</strong> {analysis.reasoning}</p>
    </body>
    </html>
    """
    
    try:
        send_mail_to_human_agent_sync.invoke({
            "subject": escalation_subject,
            "body": escalation_body
        })
        escalation_status = "Escalation email sent successfully"
    except Exception as e:
        escalation_status = f"Escalation failed: {str(e)}"
    
    # Create response informing user of escalation
    escalation_response = f"""I understand this is a complex issue that requires specialized attention. I've escalated your query to our human support team. They'll contact you shortly.

Reference: {session_id}
Issue Type: {analysis.intent.value}

Thank you for your patience."""
    
    analysis.response = escalation_response
    analysis.requires_human_escalation = True
    
    return {
        "analysis": analysis,
        "messages": state.get("messages", []) + [AIMessage(content=escalation_response)],
        "next_step": "end",
        "reasoning_steps": state.get("reasoning_steps", []) + [f"Escalation: {escalation_status}"]
    }

def should_continue(state: AgentState) -> str:
    """Determine if we should continue or end"""
    current_step = state.get("current_step", 0)
    max_steps = state.get("max_steps", 5)
    next_step = state.get("next_step", "end")
    
    # Check if we've exceeded max steps
    if current_step >= max_steps:
        return "end"
    
    # Check if we should end based on analysis
    analysis = state.get("analysis")
    if analysis and analysis.conversation_ended:
        return "end"
    
    return next_step

# Build the workflow
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("analyze", analyze_query)
workflow.add_node("reason", reason_and_plan)
workflow.add_node("retrieve", retrieve_knowledge)
workflow.add_node("respond", generate_response)
workflow.add_node("escalate", escalate_to_human)

# Add edges
workflow.add_edge(START, "analyze")
workflow.add_edge("analyze", "reason")

# Conditional edges after reasoning
workflow.add_conditional_edges(
    "reason",
    should_continue,
    {
        "retrieve": "retrieve",
        "respond": "respond",
        "escalate": "escalate",
        "end": END
    }
)

workflow.add_edge("retrieve", "respond")
workflow.add_edge("respond", END)
workflow.add_edge("escalate", END)

# Integrated simple analysis for voice/real-time processing within the agent workflow
def analyze_query_simple(state: AgentState) -> AgentState:
    """
    Simplified analysis node for real-time/voice processing, integrated into the workflow.
    Skips full reasoning if analysis indicates simplicity.
    """
    messages = state.get("messages", [])
    current_input = state.get("current_input", "")
    
    if not messages and not current_input:
        raise ValueError("No input to analyze")
    
    # Get the latest user message
    user_message = current_input
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break
    
    # Quick keyword check for ultra-simple cases
    user_input_lower = user_message.lower()
    if any(word in user_input_lower for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'thank', 'bye', 'goodbye']):
        # Directly set simple analysis and response
        analysis_result = ComprehensiveAnalysis(
            intent=IntentType.greeting,
            intent_confidence=0.9,
            sub_intent="simple_greeting",
            sentiment="positive",
            sentiment_score=0.5,
            complexity=QueryComplexity.simple,
            complexity_score=1,
            complexity_factors=["keyword_match"],
            entities=[],
            keywords=["greeting"],
            user_type="general",
            response="Hello! How can I assist you today?",
            requires_human_escalation=False
        )
        return {
            "analysis": analysis_result,
            "next_step": "respond",
            "current_step": 1,
            "reasoning_steps": ["Simple keyword-based analysis: greeting detected"]
        }
    
    # Otherwise, fall back to full LLM analysis
    return analyze_query(state)

def invoke_agent_with_analysis(user_input: str, session_id: str, channel: str = "chat", messages: Optional[List[AnyMessage]] = None, use_simple: bool = False) -> AgentState:
    """Invoke the agent with proper state initialization, optionally using simple analysis for real-time channels."""
    # Compile workflow with optional simple analysis node for voice/real-time
    if use_simple and channel in ["voice", "real-time"]:
        # Swap analyze node for simple version
        temp_workflow = StateGraph(AgentState)
        temp_workflow.add_node("analyze", analyze_query_simple)
        temp_workflow.add_node("reason", reason_and_plan)
        temp_workflow.add_node("retrieve", retrieve_knowledge)
        temp_workflow.add_node("respond", generate_response)
        temp_workflow.add_node("escalate", escalate_to_human)
        temp_workflow.add_edge(START, "analyze")
        temp_workflow.add_edge("analyze", "reason")
        temp_workflow.add_conditional_edges(
            "reason",
            should_continue,
            {
                "retrieve": "retrieve",
                "respond": "respond",
                "escalate": "escalate",
                "end": END
            }
        )
        temp_workflow.add_edge("retrieve", "respond")
        temp_workflow.add_edge("respond", END)
        temp_workflow.add_edge("escalate", END)
        graph = temp_workflow.compile(checkpointer=checkpointer)
    else:
        graph = workflow.compile(checkpointer=checkpointer)
    
    if messages is None:
        messages = []
    
    # Add new user message
    messages.append(HumanMessage(content=user_input))
    
    # Initialize state
    initial_state = {
        "messages": messages,
        "current_input": user_input,
        "conversation_history": messages[:-1] if messages else [],
        "session_id": session_id,
        "channel": channel,
        "next_step": "analyze",
        "max_steps": 6,  # analyze -> reason -> (retrieve -> respond) or escalate
        "current_step": 0,
        "reasoning_steps": [],
        "current_tool_calls": [],
        "knowledge_base_results": None,
        "retrieved_context": []
    }
    
    config = {"configurable": {"thread_id": session_id}}
    final_state = graph.invoke(initial_state, config=config)
    
    return final_state