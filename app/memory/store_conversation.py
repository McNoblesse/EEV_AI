from psycopg_pool import AsyncConnectionPool

from app.eev_configurations.config import settings
from app.api.logger.api_logs import logger

async def StoreChat(session_id, user_message, ai_response, intent, sentiment, complexity_score, agent_used, channel_used):
    try:
        async with AsyncConnectionPool(conninfo=settings.MEMORY_DB) as pool:
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                    """
                    INSERT INTO conversations 
                    (session_id, user_query, bot_response, intent, sentiment, complexity_score, agent_used, channel_used)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (session_id, user_message, ai_response, intent, sentiment, complexity_score, agent_used, channel_used)
                )
                    await conn.commit()
    except Exception as e:
        logger.error(f"Error storing chat: {e}")
        