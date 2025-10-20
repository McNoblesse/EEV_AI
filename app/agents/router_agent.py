from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.schemas.agent_schemas import AgentSchema, RouterSchema

import os
from app.eev_configurations.config import settings
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

def AgentRouter(state:AgentSchema):
    route_llm = ChatOpenAI(model="gpt-5-mini")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an intelligent routing system for eevAI, a customer service chatbot. 
Your job is to analyze the user's intent and route to the appropriate handler.

**ROUTING LOGIC:**

**CONVERSATION** - Route to "conversation" for:
- Casual greetings (hi, hello, how are you)
- Small talk or chitchat
- General conversational responses (thanks, okay, I see, got it)
- Follow-up acknowledgments that don't contain a question or request
- Expressing emotions or sharing experiences without asking for help
- Any message where the user is simply maintaining dialogue
- Questions about eevAI itself (who are you, what can you do)

**TIER_1 (AI Q&A Agent)** - Route to "tier_1" for:
- Direct questions seeking specific information
- Password reset GUIDANCE (steps, troubleshooting - cannot actually reset)
- Login troubleshooting advice (clear cache, browser issues, etc.)
- Account balance inquiries or basic account information (read-only)
- FAQ questions (business hours, contact info, policies)
- Product information requests
- Order status checks with tracking numbers
- Basic troubleshooting steps (restart device, clear cache)
- Simple how-to questions
- Feature explanations
- General knowledge questions

**Important:** Tier 1 provides INFORMATION ONLY. It cannot perform actions like:
- Actually resetting passwords (only provides steps)
- Modifying account settings
- Processing transactions or refunds
- Making system changes

**TIER_2 (Human Escalation)** - Route to "tier_2" ONLY when:
- User EXPLICITLY requests human assistance ("I want to speak to a human", "connect me to an agent", "get me a real person")
- User expresses frustration with eevAI after multiple attempts
- Conversation agent has already asked if user wants human help AND user confirmed yes
- Issue requires actual system actions (real password reset, account changes, refunds)
- Complex technical issues beyond basic guidance
- Billing disputes or payment problems
- Complaints with negative sentiment
- Account security incidents
- Multiple interconnected problems
- Policy exceptions needed

**CRITICAL ESCALATION RULE:** 
Do NOT route to tier_2 just because an issue is complex. The conversation agent (eevAI) will first ask the user if they want human assistance. Only route to tier_2 if:
1. User explicitly requests human help, OR
2. The conversation history shows eevAI already asked about human assistance and user agreed

**Context from last 20 messages:**
{history}

**Current message:** {query}

Analyze the user's intent and route accordingly. If uncertain between tier_1 and conversation, prefer tier_1 for questions and conversation for non-questions."""),
        ("user", "{query}")
    ])

    agent_llm = route_llm.with_structured_output(RouterSchema)

    llm_chain = prompt|agent_llm

    return llm_chain.invoke({"query":state["user_query"], "history":state["chat_history"]}).route