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
from utils.state_shapes import QueryComplexity, IntentType

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

logger = logging.getLogger(__name__)

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
                await self.client.ping()
                logger.info("Successfully connected to Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
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

async def get_conversation_context_async(ticket_id: int, message_type: str) -> str:
    """Get conversation context for the ticket"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        thread_pool, 
        _get_conversation_context_sync, 
        ticket_id, message_type
    )

def _get_conversation_context_sync(ticket_id: int, message_type: str) -> str:
    """Synchronous database operations for conversation context"""
    db = SessionLocal()
    try:
        # Get all messages for this ticket, ordered by creation time
        all_messages = db.query(Messages).filter(
            Messages.ticket_id == ticket_id
        ).order_by(Messages.created_at.asc()).all()
        
        if message_type == "new" or not all_messages:
            # For new tickets, just return the initial message
            if all_messages:
                return f"New Ticket: {all_messages[0].user_message}"
            return "New ticket - no previous messages"
        
        # For replies, build full conversation context
        conversation_context = ["Conversation History:"]
        for i, msg in enumerate(all_messages):
            if msg.user_message:
                role = "User" if msg.message_type == "reply" else "Customer"
                conversation_context.append(f"{role}: {msg.user_message}")
            if msg.agent_response and msg.is_processed:
                conversation_context.append(f"Agent: {msg.agent_response}")
        
        return "\n".join(conversation_context)
        
    except Exception as e:
        logger.error(f"Database error getting context for ticket {ticket_id}: {e}")
        return f"Error loading conversation context: {e}"
    finally:
        db.close()

async def update_db_with_results_async(message_id: int, session_id: str, 
                                     agent_response_text: str, analysis_result) -> None:
    """Async wrapper for database update"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        thread_pool,
        _update_db_with_results_sync,
        message_id, session_id, agent_response_text, analysis_result
    )

def _update_db_with_results_sync(message_id: int, session_id: str, 
                               agent_response_text: str, analysis_result) -> None:
    """Synchronous database update with enhanced analytics"""
    if not message_id:
        logger.warning("No message_id provided, cannot update database.")
        return

    db = SessionLocal()
    try:
        message_record = db.query(Messages).filter(Messages.id == message_id).first()
        if message_record:
            message_record.agent_response = agent_response_text
            message_record.is_processed = True
            message_record.session_id = session_id
            message_record.intent = analysis_result.intent.value
            message_record.sentiment = analysis_result.sentiment
            message_record.complexity_score = analysis_result.complexity_score
            
            # Update analytics fields
            if hasattr(analysis_result, 'intent_confidence'):
                # Store additional analytics if needed
                pass
                
            db.commit()
            logger.info(f"Successfully updated message record {message_id} in DB. "
                       f"Intent: {analysis_result.intent.value}, "
                       f"Complexity: {analysis_result.complexity_score}")
        else:
            logger.warning(f"Message record with ID {message_id} not found in DB.")
            raise WorkerError(f"Message record {message_id} not found")
    except Exception as e:
        logger.error(f"DB update failed for message {message_id}: {e}")
        db.rollback()
        raise WorkerError(f"Database update failed: {e}")
    finally:
        db.close()

async def invoke_agent_async(conversation_context: str, session_id: str, channel: str = "freshdesk"):
    """Async wrapper for AI agent invocation with multi-step reasoning"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        thread_pool,
        invoke_agent_with_analysis,
        conversation_context, session_id, channel
    )

async def send_freshdesk_reply(ticket_id: int, response_text: str, analysis_result) -> bool:
    """Send reply to Freshdesk with enhanced formatting and analytics"""
    try:
        credentials = f"{FRESHDESK_API_KEY}:X"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }
        
        # Enhanced response formatting
        formatted_response = format_llm_output_for_email(response_text)
        
        # Add analytics metadata as private note
        analytics_note = f"""
        AI Analysis:
        - Intent: {analysis_result.intent.value}
        - Complexity: {analysis_result.complexity.value}
        - Sentiment: {analysis_result.sentiment}
        - Confidence: {analysis_result.intent_confidence:.2f}
        - Requires Escalation: {analysis_result.requires_human_escalation}
        """
        
        reply_url = f"https://{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}/reply"
        reply_payload = {
            "body": formatted_response,
            "private": True  # Add analytics as private note
        }

        timeout = httpx.Timeout(30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            reply_response = await client.post(reply_url, headers=headers, json=reply_payload)
            reply_response.raise_for_status()
            
            # Add private note with analytics
            note_payload = {
                "body": analytics_note,
                "private": True
            }
            note_url = f"https://{FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}/notes"
            await client.post(note_url, headers=headers, json=note_payload)
            
            logger.info(f"Successfully replied to ticket {ticket_id} with analytics.")
            return True
            
    except httpx.TimeoutException:
        logger.error(f"Timeout sending reply to ticket {ticket_id}")
        return False
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error sending reply to ticket {ticket_id}: {e.response.status_code} - {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending reply to ticket {ticket_id}: {e}")
        return False

async def process_freshdesk_ticket_with_retry(message_data: Dict[str, Any]) -> bool:
    """Process ticket with retry logic and enhanced analytics"""
    ticket_id = message_data.get("ticket_id")
    session_id = message_data.get("session_id", f"ticket_{ticket_id}")
    
    for attempt in range(RETRY_ATTEMPTS):
        try:
            success = await process_freshdesk_ticket(message_data)
            if success:
                return True
            
            if attempt < RETRY_ATTEMPTS - 1:
                wait_time = RETRY_DELAY * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed for ticket {ticket_id}, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
                
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed for ticket {ticket_id}: {e}")
            if attempt < RETRY_ATTEMPTS - 1:
                wait_time = RETRY_DELAY * (2 ** attempt)
                await asyncio.sleep(wait_time)
    
    logger.error(f"All retry attempts failed for ticket {ticket_id}")
    return False

async def process_freshdesk_ticket(message_data: Dict[str, Any]) -> bool:
    """Process a single ticket with multi-step reasoning"""
    ticket_id = message_data.get("ticket_id")
    description_text = message_data.get("description_text", "")
    message_id = message_data.get("message_id")
    message_type = message_data.get("message_type", "new")
    session_id = message_data.get("session_id", f"ticket_{ticket_id}")

    start_time = time.time()
    logger.info(f"Starting processing for ticket {ticket_id}, type: {message_type}")

    try:
        # Step 1: Get conversation context
        conversation_context = await get_conversation_context_async(ticket_id, message_type)
        full_input = f"Ticket Context:\n{conversation_context}\n\nCurrent Message: {description_text}"

        # Step 2: Get AI response with multi-step reasoning
        final_agent_state = await invoke_agent_async(full_input, session_id, "freshdesk")
        
        if not final_agent_state or "analysis" not in final_agent_state:
            raise WorkerError("Invalid AI agent response structure")
        
        analysis_result = final_agent_state["analysis"]
        
        # Extract response from messages
        agent_response_text = ""
        messages = final_agent_state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, 'content') and msg.content:
                agent_response_text = msg.content
                break
        
        if not agent_response_text:
            raise WorkerError("AI agent returned empty response")

        # Step 3: Update database with enhanced analytics
        await update_db_with_results_async(message_id, session_id, agent_response_text, analysis_result)

        # Step 4: Send reply to Freshdesk (only if not escalation)
        if not analysis_result.requires_human_escalation:
            success = await send_freshdesk_reply(ticket_id, agent_response_text, analysis_result)
        else:
            # Handle escalation
            logger.info(f"Ticket {ticket_id} requires human escalation")
            success = True  # Escalation is handled separately

        processing_time = time.time() - start_time
        logger.info(f"Successfully processed ticket {ticket_id} in {processing_time:.2f}s. "
                   f"Intent: {analysis_result.intent.value}, "
                   f"Complexity: {analysis_result.complexity.value}")
        return True

    except WorkerError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing ticket {ticket_id}: {e}")
        raise WorkerError(f"Processing failed: {e}")

class TaskTracker:
    """Tracks running tasks and manages concurrency"""
    
    def __init__(self, max_tasks: int = MAX_CONCURRENT_TASKS):
        self.max_tasks = max_tasks
        self.running_tasks: set = set()
    
    async def add_task(self, coro):
        """Add a task if under the limit, otherwise wait"""
        while len(self.running_tasks) >= self.max_tasks:
            if self.running_tasks:
                done, self.running_tasks = await asyncio.wait(
                    self.running_tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    try:
                        await task
                    except Exception as e:
                        logger.error(f"Task failed: {e}")
        
        task = asyncio.create_task(coro)
        self.running_tasks.add(task)
        task.add_done_callback(self.running_tasks.discard)
    
    async def wait_all(self):
        """Wait for all running tasks to complete"""
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks, return_exceptions=True)
            self.running_tasks.clear()

async def main():
    """Main worker loop with enhanced monitoring"""
    task_tracker = TaskTracker()
    
    try:
        # Connect to Redis
        redis_client = await redis_manager.connect()
        logger.info(f"Worker started. Listening for messages in {TICKET_QUEUE}. "
                   f"Max concurrent tasks: {MAX_CONCURRENT_TASKS}")

        while True:
            try:
                # Non-blocking pop with timeout
                result = await redis_client.brpop(TICKET_QUEUE, timeout=5)

                if result:
                    _, message_data = result
                    message_json = json.loads(message_data.decode())
                    ticket_id = message_json.get('ticket_id')
                    
                    logger.info(f"Received message for ticket: {ticket_id}, "
                               f"type: {message_json.get('message_type', 'unknown')}")
                    
                    # Add task to tracker
                    await task_tracker.add_task(
                        process_freshdesk_ticket_with_retry(message_json)
                    )
                else:
                    # Timeout occurred, perform maintenance
                    await asyncio.sleep(0.1)

            except KeyboardInterrupt:
                logger.info("Shutdown signal received...")
                break
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in queue message: {e}")
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
    finally:
        # Cleanup
        logger.info("Waiting for running tasks to complete...")
        await task_tracker.wait_all()
        
        thread_pool.shutdown(wait=True)
        await redis_manager.close()
        logger.info("Worker shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Failed to start worker: {e}")