from typing import Annotated
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from security.authentication import AuthenticateTier1Model
from utils.voice_ai_utils import voice_processor, VoiceResponse
from config.database import get_db
from model.database_models import Conversation
import os
import logging

router = APIRouter(prefix="/voice", tags=["Voice AI"])
logger = logging.getLogger(__name__)

@router.get("/models")
async def get_available_models(
    api_key: Annotated[str, Depends(AuthenticateTier1Model)] = None
):
    """Get available transcription models, TTS models, and voices"""
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    
    models_info = voice_processor.get_available_models()
    return {
        **models_info,
        "recommended_transcription": "gpt-4o-transcribe",
        "recommended_tts": "gpt-4o-mini-tts",
        "recommended_voice": "coral",
        "supported_formats": list(voice_processor.supported_extensions),
        "max_file_size_mb": voice_processor.max_file_size // 1024 // 1024
    }

@router.post("/chat", response_model=VoiceResponse)
async def voice_chat(
    audio_file: UploadFile = File(..., description="Audio file (MP3, WAV, M4A, etc.)"),
    session_id: str = Form(..., description="Unique session identifier"),
    voice: str = Form("coral", description="OpenAI TTS voice"),
    transcription_model: str = Form("gpt-4o-transcribe", description="OpenAI transcription model"),
    tts_model: str = Form("gpt-4o-mini-tts", description="OpenAI TTS model"),
    tts_instructions: str = Form("Speak like a friendly and knowledgeable customer support specialist", description="Instructions for TTS voice style"),
    api_key: Annotated[str, Depends(AuthenticateTier1Model)] = None,
    db: Session = Depends(get_db)
):
    """
    Complete voice-to-voice conversation with multi-step reasoning:
    1. Upload audio file (up to 25MB)
    2. Transcribe speech to text using OpenAI models
    3. Process with Tier 3 AI agent (multi-step reasoning)
    4. Convert response to speech using OpenAI TTS
    5. Return analysis + audio file
    """
    
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    
    try:
        # Process the voice request with multi-step reasoning
        voice_response = await voice_processor.process_voice_request(
            audio_file=audio_file,
            session_id=session_id,
            voice=voice,
            transcription_model=transcription_model,
            tts_model=tts_model,
            tts_instructions=tts_instructions
        )
        
        # Log to database
        new_conversation = Conversation(
            session_id=session_id,
            user_query=voice_response.transcribed_text,
            bot_response=voice_response.ai_response_text,
            intent=voice_response.intent,
            sentiment=voice_response.sentiment,
            complexity_score=voice_response.complexity_score,
            channel="voice",
            transcription_model=transcription_model,
            tts_model=tts_model,
            voice_used=voice,
            escalate=voice_response.requires_escalation
        )
        db.add(new_conversation)
        db.commit()
        db.refresh(new_conversation)
        
        logger.info(f"Voice chat completed for session {session_id}: "
                   f"Intent={voice_response.intent}, "
                   f"Complexity={voice_response.complexity_score}")
        
        return voice_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice chat failed for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {str(e)}")

@router.post("/transcribe-only")
async def transcribe_only(
    audio_file: UploadFile = File(...),
    model: str = Form("gpt-4o-transcribe", description="Transcription model"),
    response_format: str = Form("text", description="Response format (text or json)"),
    api_key: Annotated[str, Depends(AuthenticateTier1Model)] = None
):
    """Transcribe audio to text only using OpenAI's latest models"""
    
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    
    try:
        await voice_processor.validate_audio_file(audio_file)
        transcribed_text = await voice_processor.transcribe_audio(
            file=audio_file,
            model=model,
            response_format=response_format
        )
        
        return {
            "transcribed_text": transcribed_text,
            "word_count": len(transcribed_text.split()),
            "character_count": len(transcribed_text),
            "model_used": model,
            "response_format": response_format
        }
    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@router.post("/tts-only")
async def text_to_speech_only(
    text: str = Form(..., description="Text to convert to speech"),
    voice: str = Form("coral", description="OpenAI TTS voice"),
    model: str = Form("gpt-4o-mini-tts", description="TTS model"),
    instructions: str = Form("Speak like a friendly customer service agent", description="Voice instructions"),
    session_id: str = Form(..., description="Session ID for file naming"),
    api_key: Annotated[str, Depends(AuthenticateTier1Model)] = None
):
    """Convert text to speech only using OpenAI TTS"""
    
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    
    if len(text) > 4000:  # OpenAI TTS limit
        raise HTTPException(status_code=400, detail="Text too long (max 4000 characters)")
    
    try:
        audio_file_path = await voice_processor.generate_tts_audio(
            text=text,
            voice=voice,
            session_id=session_id,
            model=model,
            instructions=instructions
        )
        
        return FileResponse(
            path=audio_file_path,
            media_type="audio/mpeg",
            filename=f"tts_output_{session_id}.mp3"
        )
    except Exception as e:
        logger.error(f"TTS generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")

@router.get("/audio/{session_id}")
async def get_audio_response(
    session_id: str,
    api_key: Annotated[str, Depends(AuthenticateTier1Model)] = None
):
    """Download the generated audio response"""
    
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    
    try:
        # Find the most recent audio file for this session
        import glob
        audio_files = glob.glob(f"static/temp_audio/response_{session_id}_*.mp3")
        
        if not audio_files:
            raise HTTPException(status_code=404, detail="Audio file not found")
        
        # Get the most recent file
        latest_file = max(audio_files, key=lambda x: os.path.getctime(x))
        
        return FileResponse(
            path=latest_file,
            media_type="audio/mpeg",
            filename=f"ai_response_{session_id}.mp3"
        )
    except Exception as e:
        logger.error(f"Audio retrieval failed for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Audio retrieval failed: {str(e)}")

@router.get("/voices")
async def get_available_voices(
    api_key: Annotated[str, Depends(AuthenticateTier1Model)] = None
):
    """Get all available OpenAI TTS voices with descriptions"""
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    
    return {
        "voices": voice_processor.available_voices,
        "recommended_for_customer_service": "coral",
        "sample_usage": {
            "professional": ["echo", "onyx"],
            "friendly": ["coral", "alloy"], 
            "energetic": ["nova", "shimmer"],
            "storytelling": ["fable"]
        }
    }

@router.delete("/cleanup")
async def cleanup_old_files(
    max_age_hours: int = 24,
    api_key: Annotated[str, Depends(AuthenticateTier1Model)] = None
):
    """Clean up old temporary audio files"""
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    
    try:
        voice_processor.cleanup_old_files(max_age_hours)
        return {"message": f"Cleaned up files older than {max_age_hours} hours"}
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")