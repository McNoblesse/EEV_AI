import os
import tempfile
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException
from openai import OpenAI
from pydantic import BaseModel
from typing import List
from config.access_keys import accessKeys
import logging
from langchain_core.messages import HumanMessage

# Import the simple analysis function instead of full multi-step reasoning
from utils.tier_3_utils import analyze_query_simple

logger = logging.getLogger(__name__)

# Configuration
client = OpenAI(api_key=accessKeys.OPENAI_API_KEY)

class VoiceRequest(BaseModel):
    session_id: str
    voice: Optional[str] = "coral"
    transcription_model: Optional[str] = "gpt-4o-transcribe"
    tts_model: Optional[str] = "gpt-4o-mini-tts"
    channel: Optional[str] = "voice"

class VoiceResponse(BaseModel):
    session_id: str
    transcribed_text: str
    ai_response_text: str
    audio_file_path: str
    intent: str
    intent_confidence: float
    sentiment: str
    sentiment_score: float
    complexity_score: int
    transcription_model_used: str
    tts_model_used: str
    voice_used: str
    processing_time_ms: int

class VoiceProcessor:
    def __init__(self):
        self.temp_dir = Path("static/temp_audio")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.supported_mime_types = {
            'audio/mp3', 'audio/mpeg', 'audio/wav', 'audio/m4a', 
            'audio/mp4', 'audio/mpga', 'audio/webm', 'audio/ogg',
            'audio/x-m4a', 'audio/mp4a-latm', 'application/octet-stream'
        }
        
        self.supported_extensions = {
            '.mp3', '.mpeg', '.wav', '.m4a', '.mp4', '.mpga', '.webm', '.ogg'
        }
        
        self.max_file_size = 25 * 1024 * 1024
        
        self.transcription_models = {
            "gpt-4o-transcribe": "Highest quality, latest model",
            "gpt-4o-mini-transcribe": "Good quality, faster processing", 
            "whisper-1": "Original model with more format options"
        }
        
        self.tts_models = {
            "gpt-4o-mini-tts": "High quality, cost-effective",
            "tts-1": "Standard quality, fastest",
            "tts-1-hd": "Higher quality, slower"
        }
        
        self.available_voices = {
            "alloy": "Balanced, neutral voice",
            "echo": "Clear, professional voice", 
            "fable": "Warm, storytelling voice",
            "onyx": "Deep, authoritative voice",
            "nova": "Young, energetic voice",
            "shimmer": "Bright, cheerful voice",
            "coral": "Friendly, customer service voice"
        }
        
    async def validate_audio_file(self, file: UploadFile) -> bool:
        """Enhanced validation for uploaded audio files"""
        
        if file.filename:
            file_extension = Path(file.filename).suffix.lower()
            if file_extension not in self.supported_extensions:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported file extension: {file_extension}. Supported: {', '.join(self.supported_extensions)}"
                )
        
        if file.content_type and file.content_type not in self.supported_mime_types:
            logger.warning(f"Unexpected MIME type '{file.content_type}' for file '{file.filename}'")
        
        contents = await file.read()
        if len(contents) > self.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. OpenAI limit: {self.max_file_size // 1024 // 1024}MB"
            )
        
        await file.seek(0)
        return True
    
    async def transcribe_audio(
        self, 
        file: UploadFile, 
        model: str = "gpt-4o-transcribe",
        response_format: str = "text"
    ) -> str:
        """Convert speech to text using OpenAI's latest models"""
        
        try:
            if model not in self.transcription_models:
                model = "gpt-4o-transcribe"
            
            if file.filename:
                file_extension = Path(file.filename).suffix.lower()
            else:
                file_extension = '.m4a'
                
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                contents = await file.read()
                temp_file.write(contents)
                temp_file_path = temp_file.name
            
            logger.info(f"Transcribing audio: {file.filename}, Size: {len(contents)} bytes")
            
            with open(temp_file_path, 'rb') as audio_file:
                if model in ["gpt-4o-transcribe", "gpt-4o-mini-transcribe"]:
                    transcription = client.audio.transcriptions.create(
                        model=model,
                        file=audio_file,
                        response_format=response_format
                    )
                else:
                    transcription = client.audio.transcriptions.create(
                        model=model,
                        file=audio_file,
                        response_format=response_format
                    )
            
            os.unlink(temp_file_path)
            
            if response_format == "text":
                return transcription.strip()
            else:
                return transcription.text.strip()
            
        except Exception as e:
            if 'temp_file_path' in locals():
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            logger.error(f"Transcription failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    
    async def generate_tts_audio(
        self, 
        text: str, 
        voice: str, 
        session_id: str,
        model: str = "gpt-4o-mini-tts",
        instructions: str = "Speak like a friendly customer service agent"
    ) -> str:
        """Convert text to speech using OpenAI TTS"""
        
        try:
            if voice not in self.available_voices:
                voice = "coral"
            
            if model not in self.tts_models:
                model = "gpt-4o-mini-tts"
            
            audio_filename = f"response_{session_id}_{int(asyncio.get_event_loop().time())}.mp3"
            audio_file_path = self.temp_dir / audio_filename
            
            with client.audio.speech.with_streaming_response.create(
                model=model,
                voice=voice,
                input=text,
                instructions=instructions,
                response_format="mp3"
            ) as response:
                response.stream_to_file(str(audio_file_path))
            
            logger.info(f"Generated TTS audio: {audio_file_path}")
            return str(audio_file_path)
            
        except Exception as e:
            logger.error(f"TTS generation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")
    
    async def process_voice_simple(
        self, 
        audio_file: UploadFile, 
        session_id: str, 
        voice: str = "coral",
        transcription_model: str = "gpt-4o-transcribe",
        tts_model: str = "gpt-4o-mini-tts",
        tts_instructions: str = "Speak like a friendly and knowledgeable customer support specialist"
    ) -> VoiceResponse:
        """
        SIMPLIFIED voice processing for real-time responses
        Uses direct analysis without multi-step reasoning
        """
        import time
        start_time = time.time()
        
        await self.validate_audio_file(audio_file)
        
        # Transcribe speech to text
        transcribed_text = await self.transcribe_audio(
            file=audio_file,
            model=transcription_model,
            response_format="text"
        )
        
        if not transcribed_text.strip():
            raise HTTPException(status_code=400, detail="No speech detected in audio")
        
        logger.info(f"Session {session_id}: Transcribed text: {transcribed_text[:100]}...")
        
        # SIMPLE ANALYSIS - No multi-step reasoning for voice
        analysis_result = await analyze_query_simple(transcribed_text, session_id)
        
        # Generate simple response based on analysis
        ai_response = await self.generate_simple_response(transcribed_text, analysis_result)
        
        # Convert to speech
        audio_file_path = await self.generate_tts_audio(
            text=ai_response,
            voice=voice,
            session_id=session_id,
            model=tts_model,
            instructions=tts_instructions
        )
        
        processing_time = int((time.time() - start_time) * 1000)
        
        logger.info(f"Voice processing complete for session {session_id} in {processing_time}ms")
        
        return VoiceResponse(
            session_id=session_id,
            transcribed_text=transcribed_text,
            ai_response_text=ai_response,
            audio_file_path=audio_file_path,
            intent=analysis_result.intent.value,
            intent_confidence=analysis_result.intent_confidence,
            sentiment=analysis_result.sentiment,
            sentiment_score=analysis_result.sentiment_score,
            complexity_score=analysis_result.complexity_score,
            transcription_model_used=transcription_model,
            tts_model_used=tts_model,
            voice_used=voice,
            processing_time_ms=processing_time
        )
    
    async def generate_simple_response(self, user_input: str, analysis) -> str:
        """Generate simple, direct response for voice interactions"""
        
        # Simple greeting responses
        user_input_lower = user_input.lower()
        if any(word in user_input_lower for word in ['hello', 'hi', 'hey']):
            return "Hello! I'm here to help. What can I assist you with today?"
        
        if any(word in user_input_lower for word in ['thank', 'thanks']):
            return "You're welcome! Is there anything else I can help you with?"
        
        # Based on analysis, generate appropriate response
        if analysis.intent.value == "greeting":
            return "Hello! How can I assist you today?"
        elif analysis.intent.value == "technical_question":
            return f"I understand you have a technical question about {user_input}. Let me help you with that."
        elif analysis.requires_human_escalation:
            return "I understand this is important. Let me connect you with a human specialist who can help you better."
        else:
            return f"I'll help you with that. {user_input}"
    
    def get_available_models(self) -> dict:
        """Return available models and voices"""
        return {
            "transcription_models": self.transcription_models,
            "tts_models": self.tts_models,
            "voices": self.available_voices,
            "supported_extensions": list(self.supported_extensions),
            "supported_mime_types": list(self.supported_mime_types)
        }
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """Clean up old temporary audio files"""
        import time
        current_time = time.time()
        
        for file_path in self.temp_dir.glob("*.mp3"):
            if current_time - file_path.stat().st_mtime > (max_age_hours * 3600):
                try:
                    file_path.unlink()
                    logger.info(f"Cleaned up old audio file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up {file_path}: {e}")

# Global instance
voice_processor = VoiceProcessor()