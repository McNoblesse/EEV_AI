from psycopg_pool import ConnectionPool

from eev_configurations.config import settings
from api.logger.api_logs import logger

def StoreChat(session_id, user_message, ai_response, intent, sentiment, complexity_score, agent_used):
    try:
        with ConnectionPool(conninfo=settings.MEMORY_DB).connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                """
                INSERT INTO conversations 
                (session_id, user_query, bot_response, intent, sentiment, complexity_score, agent_used)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (session_id, user_message, ai_response, intent, sentiment, complexity_score, agent_used)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error storing chat: {e}")
