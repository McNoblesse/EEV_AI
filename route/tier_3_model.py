from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from security.authentication import AuthenticateTier1Model
from model.schema import RequestPayload, PayloadResponse
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
    # Add the database session dependency
    db: Session = Depends(get_db)
):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key"
        )

    # 1. Invoke the agent to get the structured analysis.
    # This function will call the graph and return the AnalyzedQuery object.
    analysis_result = invoke_agent_with_analysis(
        user_input=data.user_query,
        session_id=data.session_id
    )

    # 2. Log the analysis results to your PostgreSQL database.
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

    # Return the final response to the frontend.
    return PayloadResponse(
        session_id=data.session_id,
        agent_response=analysis_result.response,
        intent=analysis_result.intent,
        sentiment=analysis_result.sentiment,
        complexity_score=analysis_result.complexity_score
    )