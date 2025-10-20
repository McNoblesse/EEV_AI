from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.toolkit.agent_toolkit import SendEmail
from app.memory.load_conversation import LoadConversations
from app.schemas.agent_schemas import AgentSchema, EmailSummaryAgentSchema

import os
from app.eev_configurations.config import settings
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

def Tier2(state: AgentSchema):
    summary_llm = ChatOpenAI(model="gpt-4o-mini")
    response_llm = ChatOpenAI(model="gpt-4o-mini")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a ticket summarization system for eevAI customer service. 
Your job is to create a clear, concise summary of the customer conversation for human support agents.

**SUMMARY FORMAT:**

**Customer Issue:**
[1-2 sentence description of the main problem or request]

**Conversation Context:**
[Brief overview of what was discussed, including any troubleshooting attempted]

**Customer Sentiment:**
[Negative/Positive/Neutral - with brief explanation]

**Customer Intent:**
[What the customer wants to achieve or the action they want to be taken]

**Escalation Reason:**
[Why this requires human intervention]

**Priority Level:**
[Low/Medium/High/Urgent based on issue severity and customer sentiment]

**Recommended Action:**
[Specific next steps the human agent should take]

**Key Details:**
- [Any account info, order numbers, error messages, or specific details mentioned]
- [Previous attempts to resolve the issue]
- [Customer preferences or special requests]

Keep the summary professional, factual, and actionable. Focus on information that helps the human agent resolve the issue quickly.

**OUTPUT INSTRUCTIONS:**
- Create a subject line that is concise (under 80 characters) and includes priority level
- Format the html field with proper HTML structure including headers, bold text, and lists for readability"""),
        ("user", """Please summarize this customer service conversation:
{chat_history}

Provide a structured summary for the human support agent.""")
    ])
    
    summary_chain = prompt | summary_llm.with_structured_output(EmailSummaryAgentSchema)
    chat_history = LoadConversations(session_id=state["session_id"])
    
    if chat_history.strip() == "Chat History (last 10 messages)\nNo recent Chat":
        chat_history = f"""Chat History
        Customer: {state['user_query']}
        """
    
    summary_output = summary_chain.invoke({"chat_history": chat_history})
    
    # Send email to support team
    SendEmail(
        from_email="onboarding@resend.dev",  
        to_email="edifonemmanuel14@gmail.com",  
        subject=summary_output.subject,
        html=summary_output.html
    )
    
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