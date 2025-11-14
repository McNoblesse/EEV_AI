from typing import Annotated
from fastapi import APIRouter, HTTPException, status, Depends

from app.api.logger.api_logs import logger
from app.api.auth.api_auth import endpoint_auth
from app.memory.load_conversation import LoadConversations
from app.toolkit.agent_toolkit import ClassifyConversationLog
from app.api.model.schema import ConversationCategoryPayload, ConversationClassifyResponse


router = APIRouter(prefix="/conversation_category",
                 tags=["Conversation End Check Endpoint"])

@router.post("/check_conversation_end")
async def get_conversation_categories(
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
    
    logger.info(f"Fetching conversation categories for session_id: {payload.session_id}")
    categories = await ClassifyConversationLog(chat_log=chatlog)
    
    return ConversationClassifyResponse(
        session_id=payload.session_id,
        is_chat_end=True if categories.chat_log == "conversation_ended" else False
    )