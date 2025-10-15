from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage
import time

from security.authentication import AuthenticateTier1Model
from model.schema import RequestPayload, PayloadResponse
from utils.tier_3_utils import invoke_agent_with_analysis
from config.database import get_db
from model.database_models import Conversation
import logging
from utils.state_shapes import QueryComplexity, IntentType

router = APIRouter(prefix="/model", tags=["Tier 3 model"])

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@router.post("/tier_3_model", response_model=PayloadResponse)
def tier_3_model_handler(
    data: RequestPayload,
    api_key: Annotated[str, Depends(AuthenticateTier1Model)],
    db: Session = Depends(get_db),
):
    """
    Main endpoint for Tier 3 AI model with multi-step reasoning and ReAct logic
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Missing or invalid API key"
        )

    start_time = time.time()  # Start timing

    try:
        # Retrieve conversation history
        history = (
            db.query(Conversation)
            .filter(Conversation.session_id == data.session_id)
            .order_by(Conversation.timestamp.desc())
            .limit(10)
            .all()
        )

        # Convert history to LangChain messages format
        messages = []
        for turn in reversed(history):
            messages.append(HumanMessage(content=turn.user_query))
            if turn.bot_response:
                messages.append(AIMessage(content=turn.bot_response))

        logger.info(f"Processing query for session {data.session_id}, history: {len(history)} turns")

        # Invoke the agent with multi-step reasoning
        final_agent_state = invoke_agent_with_analysis(
            user_input=data.user_query, 
            session_id=data.session_id, 
            channel=data.channel if hasattr(data, 'channel') else "chat",
            messages=messages
        )

        if not final_agent_state:
            raise HTTPException(status_code=500, detail="Agent returned no state")

        # Extract analysis and response
        analysis_result = final_agent_state.get("analysis")
        if analysis_result is None:
            logger.warning("No analysis returned from agent; using default analysis")
            from utils.state_shapes import ComprehensiveAnalysis
            
            analysis_result = ComprehensiveAnalysis(
                intent=IntentType.general_question,
                intent_confidence=0.5,
                sub_intent="unknown",
                sentiment="neutral",
                sentiment_score=0.0,
                complexity=QueryComplexity.moderate,
                complexity_score=5,
                complexity_factors=["Unable to analyze"],
                entities=[],
                keywords=[],
                user_type="general",
                response="",
                reasoning="Fallback analysis"
            )

        # Extract final response from messages
        final_response = getattr(analysis_result, "response", "") or ""
        if not final_response:
            messages_out = final_agent_state.get("messages", [])
            for msg in reversed(messages_out):
                if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", False):
                    final_response = getattr(msg, "content", "") or ""
                    break

        # Fallback response
        if not final_response or not final_response.strip():
            final_response = "Hello! How can I assist you today?"

        logger.info(f"Session {data.session_id}: Intent={analysis_result.intent.value}, "
                   f"Complexity={analysis_result.complexity.value}, "
                   f"Response length={len(final_response)}")

        processing_time_ms = int((time.time() - start_time) * 1000)  # Calculate processing time

        # Save to conversations table (core data only)
        new_conversation = Conversation(
            session_id=data.session_id,
            user_query=data.user_query,
            bot_response=final_response,
            intent=analysis_result.intent.value,
            intent_confidence=analysis_result.intent_confidence,
            sentiment=analysis_result.sentiment,
            complexity_score=analysis_result.complexity_score,
            channel=getattr(data, 'channel', 'chat'),
            requires_escalation=analysis_result.requires_human_escalation
        )
        db.add(new_conversation)
        db.commit()
        db.refresh(new_conversation)
        
        # Save analytics data (separate table)
        from model.database_models import ConversationAnalytics
        
        analytics = ConversationAnalytics(
            conversation_id=new_conversation.id,
            entities=[entity.dict() for entity in analysis_result.entities],
            keywords=analysis_result.keywords,
            complexity_factors=analysis_result.complexity_factors,
            reasoning_steps=final_agent_state.get("reasoning_steps", []),
            tool_calls_used=final_agent_state.get("current_tool_calls", []),
            retrieval_context=final_agent_state.get("retrieved_context", []),
            processing_time_ms=processing_time_ms,
            tokens_used=final_agent_state.get("tokens_used", 0),
            model_used="gpt-4o-mini"
        )
        db.add(analytics)
        db.commit()
        
        # Prepare response
        return PayloadResponse(
            session_id=data.session_id,
            response=final_response,
            intent=analysis_result.intent.value,  # Keep .value for response (lowercase if needed)
            intent_confidence=analysis_result.intent_confidence,
            sub_intent=analysis_result.sub_intent,
            sentiment=analysis_result.sentiment,
            sentiment_score=analysis_result.sentiment_score,
            complexity_score=analysis_result.complexity_score,
            complexity_factors=analysis_result.complexity_factors,
            entities=[entity.dict() for entity in analysis_result.entities],
            keywords=analysis_result.keywords,
            user_type=analysis_result.user_type,
            escalate=analysis_result.requires_human_escalation,  # Fixed to match PayloadResponse schema
            conversation_summary=analysis_result.conversation_summary,
            conversation_ended=analysis_result.conversation_ended,
            reasoning_steps=final_agent_state.get("reasoning_steps", []),
            retrieved_context=final_agent_state.get("retrieved_context", []),
            tools_used=final_agent_state.get("current_tool_calls", []),  # Added
            processing_time_ms=processing_time_ms  # Added
        )

    except Exception as e:
        logger.error(f"Error processing request for session {data.session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}"
        )

@router.get("/session/{session_id}/history")
def get_session_history(
    session_id: str,
    api_key: Annotated[str, Depends(AuthenticateTier1Model)],
    db: Session = Depends(get_db),
):
    """Get conversation history for a session"""
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")

    history = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id)
        .order_by(Conversation.timestamp.asc())
        .all()
    )
    
    return {
        "session_id": session_id,
        "total_turns": len(history),
        "conversation": [
            {
                "timestamp": turn.timestamp.isoformat(),
                "user_query": turn.user_query,
                "bot_response": turn.bot_response,
                "intent": turn.intent,
                "sentiment": turn.sentiment,
                "complexity_score": turn.complexity_score
            }
            for turn in history
        ]
    }