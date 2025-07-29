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
from typing import TypedDict, List, Sequence, Annotated
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_openai import ChatOpenAI

from config.access_keys import accessKeys
from .enhanced_nlp_pipeline import enhanced_nlp, EnhancedAnalyzedQuery

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

# UPDATE THE GRAPH'S STATE to use enhanced analysis
class MessagesState(TypedDict):
    messages: Annotated[Sequence[AnyMessage], add_messages]
    analysis: EnhancedAnalyzedQuery

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

# ENHANCED PROMPT TEMPLATE with user type awareness
prompt = ChatPromptTemplate.from_messages([
    ("system", """
    You are Eev, a friendly, empathetic, and knowledgeable AI customer support specialist.
    - Always greet users by name if available, or use a warm greeting.
    - Respond in a natural, human-like, conversational style.
    - Use the user's intent, sentiment, and complexity to tailor your response.
    - If the complexity score is 9 or 10, or if the user expresses frustration or urgency, politely inform the user that a human agent will follow up and summarize the issue for escalation.
    - If the conversation seems to be ending (user says 'thank you', 'bye', etc.), provide a friendly closing and a brief summary of the conversation.
    - Always offer further assistance unless the user clearly ends the conversation.

    User Profile Information:
    - User Type: {user_type}
    - Intent: {intent} (confidence: {intent_confidence})
    - Sub-intent: {sub_intent}
    - Sentiment: {sentiment} (score: {sentiment_score})
    - Complexity Level: {complexity_score}/10
    - Key Entities: {entities}
    - Keywords: {keywords}

    Adapt your response style based on the user type:
    - Technical users: Provide detailed technical information, code examples, API references
    - Business users: Focus on features, benefits, ROI, implementation timelines
    - General users: Use simple language, provide step-by-step guidance

    Based on the analysis, the user's message requires {mode_string}.

    Your task is to provide a helpful, personalized response that matches the user's expertise level and addresses their specific intent.
    """),
    MessagesPlaceholder(variable_name="messages")
])

# A chain for the agent to decide whether to call a tool
tool_calling_chain = prompt | llm.bind_tools(tools)

# A chain for the final node to generate the structured output
structured_output_chain = prompt | llm.with_structured_output(AnalyzedQuery)

def customer_agent_node(state: MessagesState):
    analysis = state.get("analysis")
    if analysis:
        # Only greet if intent is a greeting
        if analysis.intent in ["greeting", "hello", "hi"]:
            analysis.response = (
                "Hello! 👋 I'm Eev, your friendly customer support agent. "
                "How can I assist you today?"
            )
            return {"messages": [AIMessage(content=analysis.response)], "analysis": analysis}

        # Empathetic response for troubleshooting/negative sentiment
        if analysis.intent in ["troubleshooting", "bug_report", "issue", "problem", "integration_help"] or analysis.sentiment == "negative":
            # analysis.response = (
            #     "I'm really sorry you're experiencing this critical issue with your integration. "
            #     "Let's work together to resolve it as quickly as possible. "
            #     "Could you please provide more details about the error messages or steps you've tried so far? "
            #     "I'm here to help you every step of the way."
            # )
            # return {"messages": [AIMessage(content=analysis.response)], "analysis": analysis}
            pass

        # For information-seeking intents, use the retriever tool
        # info_intents = [
        #     "technical_question", "product_inquiry", "general_information",
        #     "account_support", "integration_help", "feature_request", "pricing_query", "user_feedback"
        # ]
        # if analysis.intent in info_intents:
        #     kb_result = retriever_tool(state["messages"][-1].content)
        #     analysis.response = (
        #         f"As your support agent, here's what I found for you:\n\n{kb_result}\n\n"
        #         "If you need more details or have another question, just let me know!"
        #     )
        #     return {"messages": [AIMessage(content=analysis.response)], "analysis": analysis}

        # ...existing context-aware prompt logic for other cases...
        mode_string = "tool assistance" if analysis.requires_tools else "direct response"
        contextual_prompt = prompt.partial(
            user_type=analysis.user_type,
            intent=analysis.intent,
            intent_confidence=analysis.intent_confidence,
            sub_intent=analysis.sub_intent,
            sentiment=analysis.sentiment,
            sentiment_score=analysis.sentiment_score,
            complexity_score=analysis.complexity_score,
            entities=[e.text for e in analysis.entities],
            keywords=analysis.keywords,
            requires_tools=analysis.requires_tools,
            mode_string=mode_string,
        )
        chain = contextual_prompt | llm.bind_tools(tools)
        response_message = chain.invoke({"messages": state["messages"]})

        # Fallback: If response is empty, set a default message
        # content = getattr(response_message, "content", "")
        # if not content or not str(content).strip():
        #     content = "I'm Eev, your AI assistant. How can I help you today?"
        # analysis.response = str(content)
        return {"messages": [response_message], "analysis": analysis}
    else:
        # fallback logic
        fallback_msg = "I'm Eev, your AI assistant. How can I help you today?"
        return {"messages": [AIMessage(content=fallback_msg)], "analysis": analysis}

def structured_output_node(state: MessagesState):
    """
    This node takes the final response from the agent, populates it into the
    analysis object, and adds final metadata like escalation flags.
    """
    analysis = state["analysis"]
    
    # The final response from the agent is the last message in the state
    last_message = state["messages"][-1]
    
    # Get the text content from that final message
    final_response_content = ""
    if isinstance(last_message, AIMessage):
        final_response_content = last_message.content

    # If the content is empty for any reason, use a safe fallback
    if not final_response_content:
        final_response_content = "I seem to have lost my train of thought. Could you please ask again?"

    # **THIS IS THE KEY FIX**: Update analysis.response with the actual final answer
    analysis.response = final_response_content

    # Now, perform the final metadata checks using this final response
    escalate = False
    conversation_summary = ""
    conversation_ended = False

    # Escalation logic
    if analysis.complexity_score >= 9 or analysis.sentiment == "negative":
        escalate = True
        conversation_summary = (
            f"Escalation required. Intent: {analysis.intent}, "
            f"Complexity: {analysis.complexity_score}, "
            f"Sentiment: {analysis.sentiment}. "
            f"Summary: {analysis.response}"
        )

    # Conversation end detection (check the user's last message)
    last_user_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content.lower()
            break
            
    if any(phrase in last_user_message for phrase in ["thank you", "thanks", "bye", "goodbye", "that will be all"]):
        conversation_ended = True
        conversation_summary = (
            f"Conversation ended. Intent: {analysis.intent}, "
            f"Summary: {analysis.response}"
        )

    # Attach these to the analysis object for the final API response
    analysis.escalate = escalate
    analysis.conversation_summary = conversation_summary
    analysis.conversation_ended = conversation_ended

    # The state is now complete and correct
    return {"messages": state["messages"], "analysis": analysis}


# DEFINE CONDITIONAL LOGIC
def tool_conditions(state: MessagesState):
    """A more robust conditional check."""
    last_message = state["messages"][-1]
    # Only AIMessage may have tool_calls; check type before accessing
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
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

def invoke_agent_with_analysis(user_input: str, session_id: str) -> EnhancedAnalyzedQuery:
    """
    Enhanced invocation with comprehensive NLP analysis.
    """
    # Perform enhanced NLP analysis first
    analysis = enhanced_nlp.analyze_query(user_input, session_id)
    
    config = {"thread_id": session_id}
    messages = [HumanMessage(content=user_input)]
    
    # Include analysis in initial state, ensuring correct types for MessagesState
    initial_state: MessagesState = {
        "messages": messages,
        "analysis": analysis
    }
    
    final_state = graph.invoke(initial_state, config=config)
    
    analysis_result = final_state['analysis']
    return analysis_result