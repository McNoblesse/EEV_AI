from typing import Annotated
from psycopg_pool import AsyncConnectionPool
from fastapi import APIRouter, HTTPException, status, Depends

from app.api.logger.api_logs import logger
from app.api.auth.api_auth import endpoint_auth
from app.memory.load_conversation import LoadConversations
from app.toolkit.agent_toolkit import ChatSentimentClassifier
from app.api.model.schema import ConversationCategoryPayload, ChatSentimentClassification


router = APIRouter(prefix="/conversation_sentiment",
                 tags=["Conversation Sentiment Endpoint"])

@router.post("/get_sentiment")
async def get_conversation_sentiment(
    api_key: Annotated[str, Depends(endpoint_auth)],
    payload: ConversationCategoryPayload
):
    if not api_key:
        logger.warning("Unauthorized request: Missing or invalid API key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication key"
        )
    
    logger.info(f"Fetching conversation categories for session_id: {payload.session_id}")
    chatlog = await LoadConversations(session_id=payload.session_id, limit=None)
    
    logger.info(f"Fetching conversation sentiment for session_id: {payload.session_id}")
    sentiment = await ChatSentimentClassifier(Chatlog=chatlog)
    
    return ChatSentimentClassification(
        session_id=payload.session_id,
        sentiment=sentiment.sentiment
    )