# worker.py
import asyncio
import json
import httpx
import base64
import logging
import redis
import time
from utils.tier_3_utils import invoke_agent_with_analysis 
from config.database import SessionLocal
from model.freshdesk_model import Messages
from utils.format_ai_response import clean_ai_response

# Configuration
FRESHDESK_API_KEY = "xkD2P495jZmM2dmPxyO"
FRESHDESK_DOMAIN = "optimusai-support.freshdesk.com"
TICKET_QUEUE = "freshdesk_tickets"

# Redis Configuration
REDIS_HOST = "redis-10197.c81.us-east-1-2.ec2.redns.redis-cloud.com"
REDIS_PORT = 10197
REDIS_PASSWORD = "UIzWMNbnGY69jUQxiCwryywpZJ1xRNLh"

logging.basicConfig(level=logging.INFO)


def get_redis_client():
    """Create and return a Redis client"""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=False  # Keep as False since we're storing binary data
    )


async def process_freshdesk_ticket(message_data):
    """
    Process a ticket message from Redis and send AI response to Freshdesk
    """
    # Getting ticket info from message
    ticket_id = message_data.get("ticket_id")
    description_text = message_data.get("description_text", "")
    message_id = message_data.get("message_id")
    message_type = message_data.get("message_type", "new")  # Default to "new" if not specified

    # Creating database session
    db = SessionLocal()

    try:
        # Preparing the input for AI model
        if message_type == "reply":
            # Getting the previous messages for this ticket that have been processed
            previous_messages = db.query(Messages).filter(
                Messages.ticket_id == ticket_id,
                Messages.is_processed == True
            ).order_by(Messages.created_at).all()

            # Formatting conversation history as a single string
            full_context = f"Ticket ID: {ticket_id}\n\n"  # Include ticket ID at the beginning
            for prev in previous_messages:
                full_context += f"User: {prev.user_message}\n"
                if prev.agent_response:
                    full_context += f"Assistant: {prev.agent_response}\n"

            # Add current message
            full_context += f"User: {description_text}\n"

            # Log the context size
            logging.info(f"Using conversation history with {len(previous_messages)} previous messages")

            # Use full context as input
            ai_input = full_context
        else:
            # For new tickets, include ticket ID with the description
            ai_input = f"Ticket ID: {ticket_id}\n\n{description_text}"

        # Get AI response using tier_3_utils instead of papss_bot
        session_id = f"freshdesk_ticket_{ticket_id}"
        ai_analysis = invoke_agent_with_analysis(ai_input, session_id)
        ai_response_text = ai_analysis.response

        # Update the database with AI response and analytics
        if message_id:
            message_record = db.query(Messages).filter(Messages.id == message_id).first()
            if message_record:
                message_record.agent_response = ai_response_text
                message_record.is_processed = True
                
                # Add the analytics from your database_models.py
                message_record.session_id = session_id
                message_record.intent = ai_analysis.intent
                message_record.sentiment = ai_analysis.sentiment
                message_record.complexity_score = ai_analysis.complexity_score
                
                db.commit()
                logging.info(f"Updated message record {message_id} with AI response and analytics")
            else:
                logging.warning(f"Message record with ID {message_id} not found")
        else:
            logging.warning("No message_id provided in Redis message")

        # Set up Freshdesk auth
        credentials = f"{FRESHDESK_API_KEY}:X"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }

        # Send AI response back to Freshdesk as reply
        reply_url = f"https://{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}/reply"
        reply_payload = {
            "body": clean_ai_response(ai_response_text)
        }

        async with httpx.AsyncClient() as client:
            reply_response = await client.post(
                reply_url,
                headers=headers,
                json=reply_payload
            )

            reply_response.raise_for_status()
            logging.info(f"Successfully replied to ticket {ticket_id}")

    except Exception as e:
        logging.error(f"Error processing ticket {ticket_id}: {str(e)}")
        db.rollback()  # Rollback in case of error
    finally:
        db.close()  # Always close the database connection


async def main():
    """
    Start the worker to listen for messages from Redis
    """
    redis_client = get_redis_client()
    logging.info(f"Connected to Redis. Waiting for messages in {TICKET_QUEUE}. To exit press CTRL+C")

    while True:
        try:
            # Block until a message is available, with 1 second timeout
            # BRPOP returns [queue_name, message] if successful
            result = redis_client.brpop(TICKET_QUEUE, timeout=1)

            if result:
                # Extract the message (second element in the tuple)
                _, message_data = result

                # Decode and parse the JSON message
                message_json = json.loads(message_data.decode())
                logging.info(f"Received message for ticket: {message_json.get('ticket_id')}")

                # Process the message
                await process_freshdesk_ticket(message_json)

            # Small delay to prevent CPU spinning
            await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            logging.info("Shutting down worker...")
            break
        except Exception as e:
            logging.error(f"Error processing message: {str(e)}")
            # Wait a bit before trying again on error
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())