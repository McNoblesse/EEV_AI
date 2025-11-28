from typing import Annotated
from fastapi import HTTPException, status, APIRouter, Depends

from app.api.logger.api_logs import logger
from app.api.auth.api_auth import endpoint_auth
from app.memory.store_conversation import StoreChat
from app.eevAI_bot.compile_bot import compiled_agent
from app.memory.load_conversation import LoadConversations
from app.toolkit.agent_toolkit import GenerateDataFromUserQuery
from app.api.model.schema import ChatAgentPayload, ChatAgentResponse

router = APIRouter(prefix="/chat-agent",
                   tags=["Chat Agent Endpoint"])

@router.post("/eev-ai-chat", response_model=ChatAgentResponse)
async def chat_agent_endpoint(
    api_key: Annotated[str, Depends(endpoint_auth)],
    payload: ChatAgentPayload
):

    if not api_key:
        logger.warning("Unauthorized request: Missing or invalid API key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication key"
        )

    logger.info(f"Loading chat history for session_id: {payload.session_id}")
    chat_history = await LoadConversations(session_id=payload.session_id, limit=20)

    data = await GenerateDataFromUserQuery(payload.user_query)
    complexity = float(data.complexity_score)
    confidence_score = 100.0 - (complexity * 100.0 / 10.0)

    below_threshold = None
    force_escalation = False
    if payload.confidence_level is not None:
        below_threshold = confidence_score < float(payload.confidence_level)
        force_escalation = below_threshold

    logger.info(f"Invoking agent: {payload.session_id}")
    bot_response = compiled_agent.invoke({
        "user_query": payload.user_query,
        "chat_history": chat_history,
        "session_id": payload.session_id,
        "index_name": payload.index_name,
        "force_escalation": force_escalation,
        "agent_name": payload.agent_name,
    })

    logger.info(f"Agent response for session_id {payload.session_id}: {bot_response['bot_response']}")

    try:
        return ChatAgentResponse(
            bot_response=bot_response["bot_response"],
            session_id=payload.session_id,
            is_escalated=True if bot_response["agent_used"] == "tier_2" else False,
            summary=bot_response.get("summary", None),
            agent_name=payload.agent_name,
            confidence_score=confidence_score,
            confidence_level=payload.confidence_level,
            below_confidence_threshold=below_threshold,
            
        )
    except Exception as e:
        logger.error(f"Error in chat agent endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Index name does not exist."
        )
    finally:
        # Store chat and analysis data
        await StoreChat(
            session_id=payload.session_id,
            user_message=payload.user_query,
            ai_response=bot_response["bot_response"],
            intent=data.intent,
            sentiment=data.sentiment,
            complexity_score=data.complexity_score,
            agent_used=bot_response["agent_used"],
            channel_used="chat_channel"
        )

        logger.info(f"Chat stored for session_id: {payload.session_id}")
