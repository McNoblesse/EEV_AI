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
from  model import freshdesk_model


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_session = Annotated[Session, Depends(get_db)]

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

router = APIRouter(tags=["Freshdesk"])

# Configuration
FRESHDESK_API_KEY = "G8YaoKsBFMHMx72qrL"
FRESHDESK_DOMAIN = "optimusai-support.freshdesk.com"
TICKET_QUEUE = "freshdesk_tickets"

# Redis Configuration
REDIS_HOST = "138.197.129.114"
REDIS_PORT = 5468
REDIS_PASSWORD = "2EGVdBboonI6Jzk6J3k04qPeyqharrZoYGMKClDhus74oWG5nYgDWSP4NyIpHS7q"
REDIS_USERNAME = "default"
REDIS_DB = 0

logging.basicConfig(level=logging.INFO)


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
        
        # Test the connection
        client.ping()
        logging.info("Successfully connected to Redis")
        return client
        
    except Exception as e:
        logging.error(f"Failed to connect to Redis: {e}")
        raise e


class FreshdeskWebhook(BaseModel):
    ticket_id: int
    ticket_subject: Optional[str] = None


@router.post("/webhook/tickets", response_model=Any)
async def freshdesk_webhook_handler(request: Request, db: db_session):
    """
    Handle incoming webhook notifications from Freshdesk and process ticket data
    """
    try:
        # Log and parse the raw webhook payload
        body = await request.json()
        logging.info(f"Received Freshdesk webhook: {body}")

        # Extracts the ticket_id from the webhook payload
        ticket_data = body.get("freshdesk_webhook", {})
        ticket_id = ticket_data.get("ticket_id")

        if ticket_id is None:
            raise ValueError("Missing 'ticket_id' in webhook payload")

        logging.info(f"Processing webhook for ticket ID: {ticket_id}")

        # Create the authorization header for Freshdesk API
        credentials = f"{FRESHDESK_API_KEY}:X"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }

        # Fetch complete ticket details from Freshdesk API
        url = f"https://{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}"
        logging.info(f"Fetching ticket details from: {url}")

        result = {}

        # Get the ticket from Freshdesk
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            logging.info(f"Freshdesk API response: {response.status_code}")
            response.raise_for_status()

            full_ticket_data = response.json()
            result["data"] = full_ticket_data

            # saving messages in my database
            new_message = freshdesk_model.Messages(ticket_id=ticket_id,
                                          user_message=full_ticket_data.get("description_text", ""),
                                          agent_response=None,
                                          message_type="new",
                                          is_processed=False,
                                          session_id=None,
                                          intent=None,
                                          sentiment=None,
                                          complexity_score=None
                                          )

            db.add(new_message)
            db.commit()
            db.refresh(new_message)

            # message structure to be passed into redis
            message_body = {
                "ticket_id": ticket_id,
                "description_text": full_ticket_data.get("description_text", ""),
                "message_id": new_message.id
            }

            # Send to Redis queue for processing
            redis_client = get_redis_client()
            redis_client.lpush(TICKET_QUEUE, json.dumps(message_body).encode())

            logging.info(f"Ticket {ticket_id} queued for processing")
            result["message_status"] = f"Ticket {ticket_id} queued for processing"

            return result

    except ValueError as e:
        logging.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        error_detail = f"Freshdesk API error: {e.response.text}"
        logging.error(f"HTTP error {status_code}: {error_detail}")
        raise HTTPException(status_code=status_code, detail=error_detail)
    except httpx.RequestError as e:
        error_message = f"Error connecting to Freshdesk: {str(e)}"
        logging.error(error_message)
        raise HTTPException(status_code=503, detail=error_message)
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/webhook/updated/tickets", response_model=Any)
async def updated_tickets_webhook(request: Request, db: db_session):
    """
        Handle updated webhook notifications from Freshdesk and process ticket data
    """
    try:
        body = await request.json()
        logging.info(f"Received Freshdesk webhook: {body}")

        # Extract ticket_id from the webhook payload
        ticket_data = body.get("freshdesk_webhook", {})
        ticket_id = ticket_data.get("ticket_id")

        if ticket_id is None:
            raise ValueError("Missing 'ticket_id' in webhook payload")

        logging.info(f"Processing webhook for ticket ID: {ticket_id}")

        # Create the authorization header for Freshdesk API
        credentials = f"{FRESHDESK_API_KEY}:X"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }

        # Fetch complete ticket details including conversations from Freshdesk API
        url = f"https://{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}?include=conversations"
        logging.info(f"Fetching ticket details from: {url}")

        result = {}

        # Get the ticket with conversations from Freshdesk
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            logging.info(f"Freshdesk API response: {response.status_code}")
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

            # Check if it's from the user
            if latest_message.get("incoming") == True:
                user_message = latest_message.get("body_text", "")

                # Check if we've already processed this exact message
                existing_message = db.query(freshdesk_model.Messages).filter(
                    freshdesk_model.Messages.ticket_id == ticket_id,
                    freshdesk_model.Messages.user_message == user_message,
                    freshdesk_model.Messages.message_type == "reply"
                ).first()

                # If already processed, skip
                if existing_message:
                    return {"status": "Message already processed"}

                # Save message to database
                new_message = freshdesk_model.Messages(
                    ticket_id=ticket_id,
                    user_message=user_message,
                    agent_response=None,
                    message_type="reply",  # This is a reply, not a new ticket
                    is_processed=False,
                    session_id=None,
                    intent=None,
                    sentiment=None,
                    complexity_score=None
                )

                db.add(new_message)
                db.commit()
                db.refresh(new_message)

                # Prepare message with ticket info and message_id
                message_body = {
                    "ticket_id": ticket_id,
                    "description_text": user_message,
                    "message_id": new_message.id,
                    "message_type": "reply"
                }

                # Send to Redis queue for processing
                redis_client = get_redis_client()
                redis_client.lpush(TICKET_QUEUE, json.dumps(message_body).encode())

                logging.info(f"Reply for ticket {ticket_id} queued for processing")
                result["message_status"] = f"Reply for ticket {ticket_id} queued for processing"

                return result
            else:
                return {"status": "Latest message is not from user"}

    except ValueError as e:
        logging.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        error_detail = f"Freshdesk API error: {e.response.text}"
        logging.error(f"HTTP error {status_code}: {error_detail}")
        raise HTTPException(status_code=status_code, detail=error_detail)
    except httpx.RequestError as e:
        error_message = f"Error connecting to Freshdesk: {str(e)}"
        logging.error(error_message)
        raise HTTPException(status_code=503, detail=error_message)
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")