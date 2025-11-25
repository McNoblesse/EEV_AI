from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.schemas.agent_schemas import AgentSchema

import os
from app.eev_configurations.config import settings
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

def Tier2(state: AgentSchema):
    response_llm = ChatOpenAI(model="gpt-4o-mini")

    # ✅ Use chat_history already passed in from the endpoint
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
    
    return {
        "bot_response": response.content,
        "agent_used": "tier_2"
    }
