from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from security.authentication import AuthenticateTier1Model
from model.schema import RequestPayload, PayloadResponse, EntityResponse
# We will use the new invocation function instead of the raw graph
from utils.tier_3_utils import invoke_agent_with_analysis
# Import database dependencies
from config.database import get_db
from model.database_models import Conversation

router = APIRouter(
    prefix="/model", 
    tags=["Tier 3 model"]
)

@router.post("/tier_3_model", response_model=PayloadResponse)
def tier_1_model_handler(
    data: RequestPayload, 
    api_key: Annotated[str, Depends(AuthenticateTier1Model)],
    db: Session = Depends(get_db)
):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key"
        )

    # Invoke the enhanced agent
    analysis_result = invoke_agent_with_analysis(
        user_input=data.user_query,
        session_id=data.session_id
    )

    # Log to PostgreSQL with enhanced data
    new_conversation_turn = Conversation(
        session_id=data.session_id,
        user_query=data.user_query,
        bot_response=analysis_result.response,
        intent=analysis_result.intent,
        sentiment=analysis_result.sentiment,
        complexity_score=analysis_result.complexity_score
    )
    db.add(new_conversation_turn)
    db.commit()
    db.refresh(new_conversation_turn)

    # Return enhanced response
    return PayloadResponse(
        session_id=data.session_id,
        agent_response=analysis_result.response,
        intent=analysis_result.intent,
        intent_confidence=analysis_result.intent_confidence,
        sub_intent=analysis_result.sub_intent,
        sentiment=analysis_result.sentiment,
        sentiment_score=analysis_result.sentiment_score,
        complexity_score=analysis_result.complexity_score,
        complexity_factors=analysis_result.complexity_factors,
        entities=[EntityResponse(text=e.text, label=e.label, confidence=e.confidence) for e in analysis_result.entities],
        keywords=analysis_result.keywords,
        user_type=analysis_result.user_type,
        requires_tools=analysis_result.requires_tools,
        escalate=analysis_result.escalate,
        conversation_summary=analysis_result.conversation_summary,
        conversation_ended=analysis_result.conversation_ended
    )