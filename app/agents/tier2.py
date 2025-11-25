from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.schemas.agent_schemas import AgentSchema

import os
from app.eev_configurations.config import settings
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

def Tier2(state: AgentSchema):
    response_llm = ChatOpenAI(model="gpt-4o-mini")

    chat_history = state["chat_history"]

    # Fallback if no history
    if isinstance(chat_history, str) and "No recent Chat" in chat_history:
        chat_history = f"""Chat History
        Customer: {state['user_query']}
        """

    response_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are eevAI's customer service assistant. A customer's issue has been escalated to human support.
Your job is to politely inform them that their case has been escalated and set expectations.

Keep your response:
- Empathetic and reassuring
- Clear about what happens next
- Professional but warm
- Brief (2-3 sentences)

Acknowledge their issue without repeating extensive details."""),
        ("user", """The customer's issue has been escalated. Here's the conversation context:
{chat_history}

Provide a brief, empathetic response letting them know their case has been escalated to a human support agent.""")
    ])
    
    response_chain = response_prompt | response_llm
    response = response_chain.invoke({"chat_history": chat_history})
    
    summary_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are preparing a handoff summary for a human support agent.
Write a concise summary of the conversation so far.

Format exactly like this:

Issue:
Key details:
Steps already attempted / advice given:
Customer sentiment:
What the customer wants now:
Suggested next action for agent:

Rules:
- Be specific; use facts from the chat history only.
- Keep it short but complete.
- If details are missing, say what’s missing."""),

        ("user", """Conversation context:
{chat_history}

Latest customer message:
{user_query}

Generate the handoff summary now.""")
    ])

    summary_chain = summary_prompt | response_llm
    summary_resp = summary_chain.invoke({
        "chat_history": chat_history,
        "user_query": state["user_query"]
    })

    return {
        "bot_response": response.content,
        "agent_used": "tier_2",
        "summary": summary_resp.content 
    }