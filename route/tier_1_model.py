"""
Tier 1: Simple Queries (Complexity < 30)
- Greetings
- Basic FAQs
- Simple product info
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Annotated
import logging

from security.authentication import AuthenticateTier1Model
from model.schema import RequestPayload, PayloadResponse
from config.database import get_db
from model.database_models import Conversation
from utils.complexity_analyzer import complexity_analyzer
from utils.tools import greeting_response_tool, retriever_tool
from utils.state_shapes import IntentType

router = APIRouter(prefix="/model", tags=["Tier 1 Model"])
logger = logging.getLogger(__name__)


@router.post("/tier_1_model", response_model=PayloadResponse)
async def tier_1_handler(
    data: RequestPayload,
    api_key: Annotated[str, Depends(AuthenticateTier1Model)],
    db: Session = Depends(get_db)
):
    """
    Tier 1: Handle simple queries with fast responses
    - Greetings
    - Basic FAQs
    - Simple product info
    
    Complexity threshold: 0-30
    """
    
    # Fast complexity check
    complexity_result = complexity_analyzer.analyze_fast(data.user_query)
    
    # Route to higher tier if needed
    if complexity_result.score > 30:
        logger.info(f"Routing to higher tier: score={complexity_result.score}")
        return {
            "session_id": data.session_id,
            "response": "Your query requires advanced analysis. Routing to specialist agent...",
            "escalate": True,
            "complexity_score": complexity_result.score,
            "intent": "escalation_request",
            "sentiment": "neutral"
        }
    
    # Handle simple queries
    try:
        # Check if greeting
        query_lower = data.user_query.lower()
        is_greeting = any(word in query_lower for word in ['hi', 'hello', 'hey', 'good morning', 'good afternoon'])
        
        if is_greeting:
            # Use greeting tool
            response = greeting_response_tool.invoke({"user_message": data.user_query})
        else:
            # Quick retrieval (1-2 results max)
            kb_results = retriever_tool.invoke({"query": data.user_query})
            
            if kb_results and len(kb_results) > 50:
                response = f"Based on our knowledge base: {kb_results[:500]}..."
            else:
                response = "I'm here to help! Could you provide more details about your question?"
        
        # Save to database
        conversation = Conversation(
            session_id=data.session_id,
            user_query=data.user_query,
            bot_response=response,
            intent=IntentType.greeting if is_greeting else IntentType.general_question,
            intent_confidence=0.9 if is_greeting else 0.7,
            sentiment="neutral",
            complexity_score=complexity_result.score,
            channel=data.channel,
            requires_escalation=False
        )
        db.add(conversation)
        db.commit()
        
        return PayloadResponse(
            session_id=data.session_id,
            response=response,
            intent="greeting" if is_greeting else "general_question",
            intent_confidence=0.9 if is_greeting else 0.7,
            sub_intent="simple_faq",
            sentiment="neutral",
            sentiment_score=0.0,
            complexity_score=complexity_result.score,
            complexity_factors=complexity_result.factors,
            entities=[],
            keywords=[],
            user_type="general",
            escalate=False,
            conversation_summary=None,
            conversation_ended=False,
            reasoning_steps=[f"Tier 1 fast path: {complexity_result.reasoning}"],
            retrieved_context=[],
            tools_used=["greeting_response_tool" if is_greeting else "retriever_tool"],
            processing_time_ms=50  # Approximate
        )
        
    except Exception as e:
        logger.error(f"Tier 1 error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")