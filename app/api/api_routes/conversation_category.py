from typing import Annotated
from psycopg_pool import AsyncConnectionPool
from fastapi import APIRouter, HTTPException, status, Depends

from app.api.logger.api_logs import logger
from app.api.auth.api_auth import endpoint_auth
from app.eev_configurations.config import settings
from app.toolkit.agent_toolkit import CategorizeChat
from app.memory.load_conversation import LoadConversations
from app.api.model.schema import ConversationCategoryPayload, ConversationCategoryResponse


router = APIRouter(prefix="/conversation_category",
                 tags=["Conversation Category Endpoint"])

@router.post("/get_categories")
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
    
    logger.info("Getting available categories")
    async with AsyncConnectionPool(conninfo=settings.MEMORY_DB) as pool:
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
            SELECT name FROM category_tbl
        """)
                    categories = [i[0] for i in await cur.fetchall()]
                    logger.info(f"Available categories: {categories}")
                    
    logger.info(f"Fetching conversation categories for session_id: {payload.session_id}")
    chatlog = await LoadConversations(session_id=payload.session_id, limit=None)
    
    logger.info(f"Fetching conversation categories for session_id: {payload.session_id}")
    categories = await CategorizeChat(category=categories, Chatlog=chatlog)
    
    return ConversationCategoryResponse(
        session_id=payload.session_id,
        category=categories.chat_category
    )