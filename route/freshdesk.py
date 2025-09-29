from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.orm import Session
import httpx
import base64
import json
import redis
import logging
from pydantic import BaseModel
from typing import Optional, Any, Annotated
from config.database import SessionLocal
from model import freshdesk_model
from utils.state_shapes import QueryComplexity, IntentType
import uuid

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_session = Annotated[Session, Depends(get_db)]

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Freshdesk"])

# Configuration
FRESHDESK_API_KEY = "Ojsifbdj7DwNuipIXQxs"
FRESHDESK_DOMAIN = "optimusai-assist.freshdesk.com"
TICKET_QUEUE = "freshdesk_tickets"
REDIS_HOST = "138.197.129.114"
REDIS_PORT = 5468
REDIS_PASSWORD = "2EGVdBboonI6Jzk6J3k04qPeyqharrZoYGMKClDhus74oWG5nYgDWSP4NyIpHS7q"
REDIS_USERNAME = "default"
REDIS_DB = 0

class FreshdeskWebhook(BaseModel):
    ticket_id: int
    ticket_subject: Optional[str] = None

def get_redis_client():
    """Create and return a Redis client"""
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            username=REDIS_USERNAME,
            password=REDIS_PASSWORD,
            db=REDIS_DB,
            decode_responses=False,
            socket_connect_timeout=10,
            socket_timeout=10,
            retry_on_timeout=True
        )
        
        client.ping()
        logger.info("Successfully connected to Redis")
        return client
        
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise e

def analyze_ticket_content(content: str) -> dict:
    """Quick analysis of ticket content for routing decisions"""
    content_lower = content.lower()
    
    # Basic intent detection
    if any(word in content_lower for word in ['hello', 'hi', 'hey', 'greeting']):
        intent = IntentType.greeting
        complexity = QueryComplexity.simple
    elif any(word in content_lower for word in ['problem', 'issue', 'error', 'broken', 'not working']):
        intent = IntentType.technical_question
        complexity = QueryComplexity.complex
    elif any(word in content_lower for word in ['price', 'cost', 'plan', 'subscription']):
        intent = IntentType.product_inquiry
        complexity = QueryComplexity.moderate
    elif any(word in content_lower for word in ['angry', 'frustrated', 'disappointed', 'complaint']):
        intent = IntentType.complaint
        complexity = QueryComplexity.escalate
    else:
        intent = IntentType.general_question
        complexity = QueryComplexity.moderate

    return {
        "intent": intent.value,
        "complexity": complexity.value,
        "requires_knowledge_base": complexity in [QueryComplexity.moderate, QueryComplexity.complex],
        "requires_escalation": complexity == QueryComplexity.escalate
    }

@router.post("/webhook/tickets", response_model=Any)
async def freshdesk_webhook_handler(request: Request, db: db_session):
    """
    Handle incoming webhook notifications from Freshdesk and process ticket data
    with smart routing based on content analysis
    """
    try:
        # Log and parse the raw webhook payload
        body = await request.json()
        logger.info(f"Received Freshdesk webhook: {body}")

        # Extract ticket_id from the webhook payload
        ticket_data = body.get("freshdesk_webhook", {})
        ticket_id = ticket_data.get("ticket_id")

        if ticket_id is None:
            raise ValueError("Missing 'ticket_id' in webhook payload")

        logger.info(f"Processing webhook for ticket ID: {ticket_id}")

        # Create the authorization header for Freshdesk API
        credentials = f"{FRESHDESK_API_KEY}:X"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }

        # Fetch complete ticket details from Freshdesk API
        url = f"https://{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}"
        logger.info(f"Fetching ticket details from: {url}")

        result = {}

        # Get the ticket from Freshdesk
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            logger.info(f"Freshdesk API response: {response.status_code}")
            response.raise_for_status()

            full_ticket_data = response.json()
            result["data"] = full_ticket_data

            description_text = full_ticket_data.get("description_text", "")
            subject = full_ticket_data.get("subject", "")
            
            # Analyze ticket content for smart routing
            content_analysis = analyze_ticket_content(f"{subject} {description_text}")
            
            # Generate unique session ID for this ticket
            session_id = f"freshdesk_{ticket_id}_{uuid.uuid4().hex[:8]}"

            # Save message in database with initial analysis
            new_message = freshdesk_model.Messages(
                ticket_id=ticket_id,
                user_message=description_text,
                agent_response=None,
                message_type="new",
                is_processed=False,
                session_id=session_id,
                intent=content_analysis["intent"],
                sentiment="neutral",  # Will be updated by AI analysis
                complexity_score=5  # Default, will be updated
            )

            db.add(new_message)
            db.commit()
            db.refresh(new_message)

            # Enhanced message structure for worker
            message_body = {
                "ticket_id": ticket_id,
                "description_text": description_text,
                "subject": subject,
                "message_id": new_message.id,
                "message_type": "new",
                "session_id": session_id,
                "initial_analysis": content_analysis,
                "priority": full_ticket_data.get("priority", 1),
                "status": full_ticket_data.get("status", "open")
            }

            # Send to Redis queue for processing
            redis_client = get_redis_client()
            message_json = json.dumps(message_body)
            redis_client.lpush(TICKET_QUEUE, message_json)
            
            # Add verification log
            queue_length = redis_client.llen(TICKET_QUEUE)
            logger.info(f"Ticket {ticket_id} queued for processing. "
                       f"Intent: {content_analysis['intent']}, "
                       f"Complexity: {content_analysis['complexity']}, "
                       f"Queue length: {queue_length}")
            
            result["message_status"] = f"Ticket {ticket_id} queued for processing"
            result["initial_analysis"] = content_analysis
            result["session_id"] = session_id

            return result

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        error_detail = f"Freshdesk API error: {e.response.text}"
        logger.error(f"HTTP error {status_code}: {error_detail}")
        raise HTTPException(status_code=status_code, detail=error_detail)
    except httpx.RequestError as e:
        error_message = f"Error connecting to Freshdesk: {str(e)}"
        logger.error(error_message)
        raise HTTPException(status_code=503, detail=error_message)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.post("/webhook/updated/tickets", response_model=Any)
async def updated_tickets_webhook(request: Request, db: db_session):
    """
    Handle updated webhook notifications from Freshdesk and process ticket data
    with conversation context awareness
    """
    try:
        body = await request.json()
        logger.info(f"Received Freshdesk update webhook: {body}")

        # Extract ticket_id from the webhook payload
        ticket_data = body.get("freshdesk_webhook", {})
        ticket_id = ticket_data.get("ticket_id")

        if ticket_id is None:
            raise ValueError("Missing 'ticket_id' in webhook payload")

        logger.info(f"Processing update webhook for ticket ID: {ticket_id}")

        # Create the authorization header for Freshdesk API
        credentials = f"{FRESHDESK_API_KEY}:X"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }

        # Fetch complete ticket details including conversations
        url = f"https://{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}?include=conversations"
        logger.info(f"Fetching ticket details with conversations from: {url}")

        result = {}

        # Get the ticket with conversations from Freshdesk
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            logger.info(f"Freshdesk API response: {response.status_code}")
            response.raise_for_status()

            full_ticket_data = response.json()
            result["data"] = full_ticket_data

            # Get conversations
            conversations = full_ticket_data.get("conversations", [])

            # Skip if no conversations
            if not conversations:
                return {"status": "No conversations found"}

            # Get the most recent message (last in the array)
            latest_message = conversations[-1]

            # Check if it's from the user and not already processed
            if latest_message.get("incoming") == True:
                user_message = latest_message.get("body_text", "")
                
                # Analyze the new message
                content_analysis = analyze_ticket_content(user_message)
                
                # Generate session ID maintaining conversation context
                session_id = f"freshdesk_{ticket_id}_conversation"

                # Check if we've already processed this exact message
                existing_message = db.query(freshdesk_model.Messages).filter(
                    freshdesk_model.Messages.ticket_id == ticket_id,
                    freshdesk_model.Messages.user_message == user_message,
                    freshdesk_model.Messages.message_type == "reply"
                ).first()

                # If already processed, skip
                if existing_message:
                    logger.info(f"Message already processed for ticket {ticket_id}")
                    return {"status": "Message already processed"}

                # Save reply message to database
                new_message = freshdesk_model.Messages(
                    ticket_id=ticket_id,
                    user_message=user_message,
                    agent_response=None,
                    message_type="reply",
                    is_processed=False,
                    session_id=session_id,
                    intent=content_analysis["intent"],
                    sentiment="neutral",
                    complexity_score=5
                )

                db.add(new_message)
                db.commit()
                db.refresh(new_message)

                # Prepare message with enhanced context
                message_body = {
                    "ticket_id": ticket_id,
                    "description_text": user_message,
                    "message_id": new_message.id,
                    "message_type": "reply",
                    "session_id": session_id,
                    "initial_analysis": content_analysis,
                    "is_follow_up": True,
                    "conversation_turn": len([m for m in conversations if m.get("incoming") == True])
                }

                # Send to Redis queue for processing
                redis_client = get_redis_client()
                message_json = json.dumps(message_body)
                redis_client.lpush(TICKET_QUEUE, message_json)
                
                # Add verification log
                queue_length = redis_client.llen(TICKET_QUEUE)
                logger.info(f"Reply for ticket {ticket_id} queued for processing. "
                           f"Conversation turn: {message_body['conversation_turn']}, "
                           f"Queue length: {queue_length}")
                
                result["message_status"] = f"Reply for ticket {ticket_id} queued for processing"
                result["initial_analysis"] = content_analysis
                result["conversation_turn"] = message_body["conversation_turn"]

                return result
            else:
                logger.info(f"Latest message is not from user for ticket {ticket_id}")
                return {"status": "Latest message is not from user"}

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        error_detail = f"Freshdesk API error: {e.response.text}"
        logger.error(f"HTTP error {status_code}: {error_detail}")
        raise HTTPException(status_code=status_code, detail=error_detail)
    except httpx.RequestError as e:
        error_message = f"Error connecting to Freshdesk: {str(e)}"
        logger.error(error_message)
        raise HTTPException(status_code=503, detail=error_message)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/ticket/{ticket_id}/status")
async def get_ticket_status(ticket_id: int, db: db_session):
    """Get processing status of a ticket"""
    try:
        messages = db.query(freshdesk_model.Messages).filter(
            freshdesk_model.Messages.ticket_id == ticket_id
        ).order_by(freshdesk_model.Messages.created_at.desc()).all()
        
        if not messages:
            return {"status": "No messages found for ticket"}
        
        latest_message = messages[0]
        
        return {
            "ticket_id": ticket_id,
            "latest_message_id": latest_message.id,
            "is_processed": latest_message.is_processed,
            "processed_at": latest_message.updated_at,
            "intent": latest_message.intent,
            "sentiment": latest_message.sentiment,
            "complexity_score": latest_message.complexity_score,
            "total_messages": len(messages),
            "processed_messages": len([m for m in messages if m.is_processed])
        }
        
    except Exception as e:
        logger.error(f"Error getting ticket status for {ticket_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving ticket status: {str(e)}")