import asyncio
import json
import httpx
import base64
import logging
import redis.asyncio as redis # Use the async version
import time
from utils.tier_3_utils import invoke_agent_with_analysis 
from config.database import SessionLocal
from model.freshdesk_model import Messages
from utils.format_ai_response import clean_ai_response, format_llm_output_for_email

# --- Configuration (no changes) ---
FRESHDESK_API_KEY = "Ojsifbdj7DwNuipIXQxs"
FRESHDESK_DOMAIN = "optimusai-assist.freshdesk.com"
TICKET_QUEUE = "freshdesk_tickets"
REDIS_HOST = "138.197.129.114"
REDIS_PORT = 5468
REDIS_PASSWORD = "2EGVdBboonI6Jzk6J3k04qPeyqharrZoYGMKClDhus74oWG5nYgDWSP4NyIpHS7q"
REDIS_USERNAME = "default"
REDIS_DB = 0

logging.basicConfig(level=logging.INFO)

# --- Redis Client (use async) ---
def get_redis_client():
    """Create and return an async Redis client"""
    try:
        client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, username=REDIS_USERNAME,
            password=REDIS_PASSWORD, db=REDIS_DB, decode_responses=False,
            socket_connect_timeout=10, socket_timeout=10, retry_on_timeout=True
        )
        return client
    except Exception as e:
        logging.error(f"Failed to connect to Redis: {e}")
        raise e

# --- Synchronous Blocking Functions ---

def get_ai_input_from_db(ticket_id: int, message_type: str, description_text: str) -> str:
    """
    BLOCKING: Connects to the DB to build the AI input string.
    For replies, it fetches conversation history.
    """
    if message_type != "reply":
        return f"Ticket ID: {ticket_id}\n\n{description_text}"

    db = SessionLocal()
    try:
        previous_messages = db.query(Messages).filter(
            Messages.ticket_id == ticket_id, Messages.is_processed == True
        ).order_by(Messages.created_at).all()

        full_context = f"Ticket ID: {ticket_id}\n\n"
        for prev in previous_messages:
            full_context += f"User: {prev.user_message}\n"
            if prev.agent_response:
                full_context += f"Assistant: {prev.agent_response}\n"
        
        full_context += f"User: {description_text}\n"
        logging.info(f"Built context with {len(previous_messages)} previous messages for ticket {ticket_id}")
        return full_context
    finally:
        db.close()

def update_db_with_results(message_id: int, session_id: str, agent_response_text: str, analysis_result) -> None:
    """BLOCKING: Connects to the DB to save the AI response and analytics."""
    if not message_id:
        logging.warning("No message_id provided, cannot update database.")
        return

    db = SessionLocal()
    try:
        message_record = db.query(Messages).filter(Messages.id == message_id).first()
        if message_record:
            message_record.agent_response = agent_response_text
            message_record.is_processed = True
            message_record.session_id = session_id
            message_record.intent = analysis_result.intent
            message_record.sentiment = analysis_result.sentiment
            message_record.complexity_score = analysis_result.complexity_score
            db.commit()
            logging.info(f"Successfully updated message record {message_id} in DB.")
        else:
            logging.warning(f"Message record with ID {message_id} not found in DB.")
    except Exception as e:
        logging.error(f"DB update failed for message {message_id}: {e}")
        db.rollback()
    finally:
        db.close()

# --- Asynchronous Orchestrator ---

async def process_freshdesk_ticket(message_data):
    """
    NON-BLOCKING: Orchestrates the processing of a ticket.
    """
    ticket_id = message_data.get("ticket_id")
    description_text = message_data.get("description_text", "")
    message_id = message_data.get("message_id")
    message_type = message_data.get("message_type", "new")

    loop = asyncio.get_event_loop()

    try:
        # Step 1: Get AI input (run blocking DB logic in thread)
        ai_input = await loop.run_in_executor(
            None, get_ai_input_from_db, ticket_id, message_type, description_text
        )

        # Step 2: Get AI response (run blocking AI logic in thread)
        session_id = f"freshdesk_ticket_{ticket_id}"
        final_agent_state = await loop.run_in_executor(
            None, invoke_agent_with_analysis, ai_input, session_id
        )
        analysis_result = final_agent_state["analysis"]
        agent_response_text = final_agent_state["messages"][-1].content

        # Step 3: Update DB with results (run blocking DB logic in thread)
        await loop.run_in_executor(
            None, update_db_with_results, message_id, session_id, agent_response_text, analysis_result
        )

        # Step 4: Send reply to Freshdesk (already non-blocking)
        credentials = f"{FRESHDESK_API_KEY}:X"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {"Authorization": f"Basic {encoded_credentials}", "Content-Type": "application/json"}
        reply_url = f"https://{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}/reply"
        reply_payload = {"body": format_llm_output_for_email(agent_response_text)}

        async with httpx.AsyncClient() as client:
            reply_response = await client.post(reply_url, headers=headers, json=reply_payload)
            reply_response.raise_for_status()
            logging.info(f"Successfully replied to ticket {ticket_id} via Freshdesk API.")

    except Exception as e:
        logging.error(f"Critical error in processing ticket {ticket_id}: {str(e)}")

# --- Main Worker Loop ---

async def main():
    """
    Start the worker to listen for messages from Redis
    """
    redis_client = get_redis_client()
    await redis_client.ping() # Ping async client
    logging.info(f"Connected to Redis. Waiting for messages in {TICKET_QUEUE}. To exit press CTRL+C")

    while True:
        try:
            result = await redis_client.brpop(TICKET_QUEUE, timeout=1) # Use await

            if result:
                _, message_data = result
                message_json = json.loads(message_data.decode())
                logging.info(f"Received message for ticket: {message_json.get('ticket_id')}")
                
                # Process the message without blocking the loop
                asyncio.create_task(process_freshdesk_ticket(message_json))

        except KeyboardInterrupt:
            logging.info("Shutting down worker...")
            break
        except Exception as e:
            logging.error(f"Error in main loop: {str(e)}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())