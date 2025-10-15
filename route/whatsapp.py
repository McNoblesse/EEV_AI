"""
WhatsApp Business API Integration
- Webhook receiver
- Message sender
- Media handling (images, voice notes, documents)
"""

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from typing import Annotated, Optional
import httpx
import logging
import os
from datetime import datetime

from config.database import get_db
from security.authentication import AuthenticateTier1Model
from model.database_models import Conversation
from utils.complexity_analyzer import complexity_analyzer
from config.access_keys import accessKeys

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])
logger = logging.getLogger(__name__)

# Configuration (add to config/access_keys.py)
WHATSAPP_API_TOKEN = accessKeys.WHATSAPP_API_TOKEN
WHATSAPP_PHONE_NUMBER_ID = accessKeys.WHATSAPP_PHONE_NUMBER_ID
WHATSAPP_VERIFY_TOKEN = accessKeys.WHATSAPP_VERIFY_TOKEN
WHATSAPP_API_URL = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"


@router.get("/webhook")
async def verify_webhook(request: Request):
    """
    Verify WhatsApp webhook (required by Meta)
    https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/setup
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified")
        return int(challenge)
    
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Receive messages from WhatsApp Business API
    
    Supported message types:
    - text
    - image
    - audio (voice notes)
    - document (PDF, etc.)
    """
    try:
        body = await request.json()
        logger.info(f"WhatsApp webhook received: {body}")
        
        # Extract message data
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return {"status": "no_messages"}
        
        for message in messages:
            sender = message["from"]
            message_type = message.get("type", "text")
            timestamp_unix = int(message.get("timestamp", 0))
            
            # Generate session ID
            session_id = f"whatsapp_{sender}_{datetime.now().strftime('%Y%m%d')}"
            
            # Process based on message type
            if message_type == "text":
                text = message.get("text", {}).get("body", "")
                background_tasks.add_task(
                    process_text_message,
                    sender=sender,
                    text=text,
                    session_id=session_id,
                    db=db
                )
            
            elif message_type == "image":
                image_id = message.get("image", {}).get("id")
                caption = message.get("image", {}).get("caption", "")
                background_tasks.add_task(
                    process_image_message,
                    sender=sender,
                    image_id=image_id,
                    caption=caption,
                    session_id=session_id,
                    db=db
                )
            
            elif message_type == "audio":
                audio_id = message.get("audio", {}).get("id")
                background_tasks.add_task(
                    process_voice_note,
                    sender=sender,
                    audio_id=audio_id,
                    session_id=session_id,
                    db=db
                )
            
            elif message_type == "document":
                doc_id = message.get("document", {}).get("id")
                filename = message.get("document", {}).get("filename", "document")
                background_tasks.add_task(
                    process_document_message,
                    sender=sender,
                    doc_id=doc_id,
                    filename=filename,
                    session_id=session_id,
                    db=db
                )
        
        return {"status": "ok"}
    
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {str(e)}")
        return {"status": "error", "message": str(e)}


async def process_text_message(sender: str, text: str, session_id: str, db: Session):
    """Process text message with tier routing"""
    try:
        # Analyze complexity
        complexity = complexity_analyzer.analyze_fast(text)
        
        # Route to appropriate tier
        if complexity.tier == 'tier1':
            from route.tier_1_model import tier_1_handler
            from model.schema import RequestPayload
            
            payload = RequestPayload(
                user_query=text,
                session_id=session_id,
                channel="whatsapp"
            )
            # Note: Simplified - in production, handle async properly
            response_text = f"Processing your query: {text}"
        else:
            response_text = f"Your query is being analyzed by our AI system. Complexity: {complexity.score}"
        
        # Send reply
        await send_whatsapp_message(sender, response_text)
        
    except Exception as e:
        logger.error(f"Text processing error: {e}")
        await send_whatsapp_message(sender, "Sorry, I encountered an error. Please try again.")


async def process_image_message(sender: str, image_id: str, caption: str, session_id: str, db: Session):
    """Handle image uploads"""
    try:
        # Download image
        image_url = await get_media_url(image_id)
        
        # Process caption if provided
        if caption:
            response = f"I received your image with caption: {caption}. Image processing is not yet implemented."
        else:
            response = "I received your image. Image analysis is not yet implemented."
        
        await send_whatsapp_message(sender, response)
        
    except Exception as e:
        logger.error(f"Image processing error: {e}")
        await send_whatsapp_message(sender, "I couldn't process your image.")


async def process_voice_note(sender: str, audio_id: str, session_id: str, db: Session):
    """Handle voice notes with transcription"""
    try:
        # Download audio
        audio_url = await get_media_url(audio_id)
        
        # TODO: Transcribe with OpenAI Whisper
        response = "I received your voice note. Voice transcription will be integrated soon."
        
        await send_whatsapp_message(sender, response)
        
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        await send_whatsapp_message(sender, "I couldn't process your voice note.")


async def process_document_message(sender: str, doc_id: str, filename: str, session_id: str, db: Session):
    """Handle document uploads (PDFs, etc.)"""
    try:
        # Download document
        doc_url = await get_media_url(doc_id)
        
        # TODO: Process with document_processor
        response = f"I received your document: {filename}. Document processing will be integrated soon."
        
        await send_whatsapp_message(sender, response)
        
    except Exception as e:
        logger.error(f"Document processing error: {e}")
        await send_whatsapp_message(sender, "I couldn't process your document.")


async def send_whatsapp_message(phone_number: str, message: str):
    """
    Send text message via WhatsApp Business API
    """
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            WHATSAPP_API_URL,
            headers=headers,
            json=payload,
            timeout=10.0
        )
        
        if response.status_code != 200:
            logger.error(f"WhatsApp send failed: {response.text}")
            raise Exception(f"Failed to send message: {response.status_code}")
        
        logger.info(f"WhatsApp message sent to {phone_number}")


async def send_whatsapp_image(phone_number: str, image_url: str, caption: Optional[str] = None):
    """Send image via WhatsApp"""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption or ""
        }
    }
    
    async with httpx.AsyncClient() as client:
        await client.post(WHATSAPP_API_URL, headers=headers, json=payload)


async def get_media_url(media_id: str) -> str:
    """
    Get media URL from WhatsApp API
    https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media
    """
    headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://graph.facebook.com/v18.0/{media_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()["url"]
        
        raise Exception(f"Failed to get media URL: {response.status_code}")