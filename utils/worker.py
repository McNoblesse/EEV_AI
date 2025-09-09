import asyncio
import json
import httpx
import base64
import logging
import redis.asyncio as redis
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from utils.tier_3_utils import invoke_agent_with_analysis 
from config.database import SessionLocal
from model.freshdesk_model import Messages
from utils.format_ai_response import clean_ai_response, format_llm_output_for_email

# --- Configuration ---
FRESHDESK_API_KEY = "Ojsifbdj7DwNuipIXQxs"
FRESHDESK_DOMAIN = "optimusai-assist.freshdesk.com"
TICKET_QUEUE = "freshdesk_tickets"
REDIS_HOST = "138.197.129.114"
REDIS_PORT = 5468
REDIS_PASSWORD = "2EGVdBboonI6Jzk6J3k04qPeyqharrZoYGMKClDhus74oWG5nYgDWSP4NyIpHS7q"
REDIS_USERNAME = "default"
REDIS_DB = 0

# Worker configuration
MAX_CONCURRENT_TASKS = 5
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('worker.log'),
        logging.StreamHandler()
    ]
)

class WorkerError(Exception):
    """Custom exception for worker errors"""
    pass

class RedisManager:
    """Manages Redis connection with proper async handling"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
    
    async def connect(self) -> redis.Redis:
        """Create and test Redis connection"""
        if self.client is None:
            try:
                self.client = redis.Redis(
                    host=REDIS_HOST, 
                    port=REDIS_PORT, 
                    username=REDIS_USERNAME,
                    password=REDIS_PASSWORD, 
                    db=REDIS_DB, 
                    decode_responses=False,
                    socket_connect_timeout=10, 
                    socket_timeout=10, 
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                # Test connection
                await self.client.ping()
                logging.info("Successfully connected to Redis")
            except Exception as e:
                logging.error(f"Failed to connect to Redis: {e}")
                raise WorkerError(f"Redis connection failed: {e}")
        return self.client
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.aclose()
            self.client = None

# Global Redis manager
redis_manager = RedisManager()

# Thread pool for blocking operations
thread_pool = ThreadPoolExecutor(max_workers=10, thread_name_prefix="worker_db")

async def get_ai_input_from_db_async(ticket_id: int, message_type: str, description_text: str) -> str:
    """Async wrapper for database operations"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        thread_pool, 
        _get_ai_input_from_db_sync, 
        ticket_id, message_type, description_text
    )

def _get_ai_input_from_db_sync(ticket_id: int, message_type: str, description_text: str) -> str:
    """Synchronous database operations"""
    if message_type != "reply":
        return f"Ticket ID: {ticket_id}\n\n{description_text}"

    db = SessionLocal()
    try:
        previous_messages = db.query(Messages).filter(
            Messages.ticket_id == ticket_id, 
            Messages.is_processed == True
        ).order_by(Messages.created_at).all()

        full_context = f"Ticket ID: {ticket_id}\n\n"
        for prev in previous_messages:
            full_context += f"User: {prev.user_message}\n"
            if prev.agent_response:
                full_context += f"Assistant: {prev.agent_response}\n"
        
        full_context += f"User: {description_text}\n"
        logging.info(f"Built context with {len(previous_messages)} previous messages for ticket {ticket_id}")
        return full_context
    except Exception as e:
        logging.error(f"Database error getting AI input for ticket {ticket_id}: {e}")
        raise WorkerError(f"Failed to get AI input: {e}")
    finally:
        db.close()

async def update_db_with_results_async(message_id: int, session_id: str, agent_response_text: str, analysis_result) -> None:
    """Async wrapper for database update"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        thread_pool,
        _update_db_with_results_sync,
        message_id, session_id, agent_response_text, analysis_result
    )

def _update_db_with_results_sync(message_id: int, session_id: str, agent_response_text: str, analysis_result) -> None:
    """Synchronous database update"""
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
            raise WorkerError(f"Message record {message_id} not found")
    except Exception as e:
        logging.error(f"DB update failed for message {message_id}: {e}")
        db.rollback()
        raise WorkerError(f"Database update failed: {e}")
    finally:
        db.close()

async def invoke_agent_async(ai_input: str, session_id: str):
    """Async wrapper for AI agent invocation"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        thread_pool,
        invoke_agent_with_analysis,
        ai_input, session_id
    )

async def send_freshdesk_reply(ticket_id: int, response_text: str) -> bool:
    """Send reply to Freshdesk with proper error handling"""
    try:
        credentials = f"{FRESHDESK_API_KEY}:X"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }
        reply_url = f"https://{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}/reply"
        reply_payload = {"body": format_llm_output_for_email(response_text)}

        timeout = httpx.Timeout(30.0)  # 30 second timeout
        async with httpx.AsyncClient(timeout=timeout) as client:
            reply_response = await client.post(reply_url, headers=headers, json=reply_payload)
            reply_response.raise_for_status()
            logging.info(f"Successfully replied to ticket {ticket_id} via Freshdesk API.")
            return True
    except httpx.TimeoutException:
        logging.error(f"Timeout sending reply to ticket {ticket_id}")
        return False
    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error sending reply to ticket {ticket_id}: {e.response.status_code} - {e.response.text}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error sending reply to ticket {ticket_id}: {e}")
        return False

async def process_freshdesk_ticket_with_retry(message_data: Dict[str, Any]) -> bool:
    """Process ticket with retry logic"""
    ticket_id = message_data.get("ticket_id")
    
    for attempt in range(RETRY_ATTEMPTS):
        try:
            success = await process_freshdesk_ticket(message_data)
            if success:
                return True
            
            if attempt < RETRY_ATTEMPTS - 1:
                wait_time = RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                logging.warning(f"Attempt {attempt + 1} failed for ticket {ticket_id}, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
                
        except Exception as e:
            logging.error(f"Attempt {attempt + 1} failed for ticket {ticket_id}: {e}")
            if attempt < RETRY_ATTEMPTS - 1:
                wait_time = RETRY_DELAY * (2 ** attempt)
                await asyncio.sleep(wait_time)
    
    logging.error(f"All retry attempts failed for ticket {ticket_id}")
    return False

async def process_freshdesk_ticket(message_data: Dict[str, Any]) -> bool:
    """Process a single ticket"""
    ticket_id = message_data.get("ticket_id")
    description_text = message_data.get("description_text", "")
    message_id = message_data.get("message_id")
    message_type = message_data.get("message_type", "new")

    start_time = time.time()
    logging.info(f"Starting processing for ticket {ticket_id}")

    try:
        # Step 1: Get AI input
        ai_input = await get_ai_input_from_db_async(ticket_id, message_type, description_text)

        # Step 2: Get AI response
        session_id = f"freshdesk_ticket_{ticket_id}"
        final_agent_state = await invoke_agent_async(ai_input, session_id)
        
        if not final_agent_state or "analysis" not in final_agent_state or "messages" not in final_agent_state:
            raise WorkerError("Invalid AI agent response structure")
        
        analysis_result = final_agent_state["analysis"]
        agent_response_text = final_agent_state["messages"][-1].content

        if not agent_response_text:
            raise WorkerError("AI agent returned empty response")

        # Step 3: Update database
        await update_db_with_results_async(message_id, session_id, agent_response_text, analysis_result)

        # Step 4: Send reply to Freshdesk
        success = await send_freshdesk_reply(ticket_id, agent_response_text)
        
        if not success:
            raise WorkerError("Failed to send reply to Freshdesk")

        processing_time = time.time() - start_time
        logging.info(f"Successfully processed ticket {ticket_id} in {processing_time:.2f}s")
        return True

    except WorkerError:
        raise  # Re-raise worker errors
    except Exception as e:
        logging.error(f"Unexpected error processing ticket {ticket_id}: {e}")
        raise WorkerError(f"Processing failed: {e}")

class TaskTracker:
    """Tracks running tasks and manages concurrency"""
    
    def __init__(self, max_tasks: int = MAX_CONCURRENT_TASKS):
        self.max_tasks = max_tasks
        self.running_tasks: set = set()
    
    async def add_task(self, coro):
        """Add a task if under the limit, otherwise wait"""
        while len(self.running_tasks) >= self.max_tasks:
            # Wait for a task to complete
            if self.running_tasks:
                done, self.running_tasks = await asyncio.wait(
                    self.running_tasks, return_when=asyncio.FIRST_COMPLETED
                )
                # Log completed tasks
                for task in done:
                    try:
                        await task  # This will raise any exceptions
                    except Exception as e:
                        logging.error(f"Task failed: {e}")
        
        # Create new task
        task = asyncio.create_task(coro)
        self.running_tasks.add(task)
        
        # Add callback to remove completed tasks
        task.add_done_callback(self.running_tasks.discard)
    
    async def wait_all(self):
        """Wait for all running tasks to complete"""
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks, return_exceptions=True)
            self.running_tasks.clear()

async def main():
    """Main worker loop with proper error handling and task management"""
    task_tracker = TaskTracker()
    
    try:
        # Connect to Redis
        redis_client = await redis_manager.connect()
        logging.info(f"Worker started. Listening for messages in {TICKET_QUEUE}. Max concurrent tasks: {MAX_CONCURRENT_TASKS}")

        while True:
            try:
                # Non-blocking pop with timeout
                result = await redis_client.brpop(TICKET_QUEUE, timeout=5)

                if result:
                    _, message_data = result
                    message_json = json.loads(message_data.decode())
                    ticket_id = message_json.get('ticket_id')
                    
                    logging.info(f"Received message for ticket: {ticket_id}")
                    
                    # Add task to tracker (this manages concurrency)
                    await task_tracker.add_task(
                        process_freshdesk_ticket_with_retry(message_json)
                    )
                else:
                    # Timeout occurred, perform maintenance
                    await asyncio.sleep(0.1)  # Brief pause

            except KeyboardInterrupt:
                logging.info("Shutdown signal received...")
                break
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON in queue message: {e}")
            except Exception as e:
                logging.error(f"Error in main loop: {e}")
                await asyncio.sleep(1)  # Brief pause before continuing

    except Exception as e:
        logging.error(f"Fatal error in main: {e}")
    finally:
        # Cleanup
        logging.info("Waiting for running tasks to complete...")
        await task_tracker.wait_all()
        
        thread_pool.shutdown(wait=True)
        await redis_manager.close()
        logging.info("Worker shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Worker interrupted by user")
    except Exception as e:
        logging.error(f"Failed to start worker: {e}")