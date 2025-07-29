import os
import tempfile
import asyncio
from pathlib import Path
from typing import Optional, Tuple
import aiofiles
import aiohttp
from fastapi import UploadFile, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List
from utils.enhanced_nlp_pipeline import ExtractedEntity, EnhancedAnalyzedQuery

from config.access_keys import accessKeys
from utils.tier_3_utils import invoke_agent_with_analysis

# Configuration
client = OpenAI(api_key=accessKeys.OPENAI_API_KEY)

class VoiceRequest(BaseModel):
    session_id: str
    voice: Optional[str] = "alloy"  # OpenAI TTS voice
    transcription_model: Optional[str] = "gpt-4o-transcribe"
    tts_model: Optional[str] = "gpt-4o-mini-tts"
    
class VoiceResponse(BaseModel):
    session_id: str
    transcribed_text: str
    ai_response_text: str
    audio_file_path: str
    intent: str
    intent_confidence: float
    sub_intent: str
    sentiment: str
    sentiment_score: float
    complexity_score: int
    complexity_factors: List[str]
    entities: List[ExtractedEntity]  # Changed from List[dict] to the proper type
    keywords: List[str]
    user_type: str
    requires_tools: bool
    escalate: bool
    conversation_summary: str
    conversation_ended: bool
    transcription_model_used: str
    tts_model_used: str
    voice_used: str

class VoiceProcessor:
    def __init__(self):
        self.temp_dir = Path("static/temp_audio")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Updated: More comprehensive format checking
        self.supported_mime_types = {
            'audio/mp3', 'audio/mpeg', 'audio/wav', 'audio/m4a', 
            'audio/mp4', 'audio/mpga', 'audio/webm', 'audio/ogg',
            'audio/x-m4a', 'audio/mp4a-latm',  # Additional M4A variants
            'application/octet-stream'  # Some browsers send this for audio files
        }
        
        # Check by file extension as fallback
        self.supported_extensions = {
            '.mp3', '.mpeg', '.wav', '.m4a', '.mp4', '.mpga', '.webm', '.ogg'
        }
        
        # File size limits (25MB max - OpenAI limit)
        self.max_file_size = 25 * 1024 * 1024
        
        # Available transcription models
        self.transcription_models = {
            "gpt-4o-transcribe": "Highest quality, latest model",
            "gpt-4o-mini-transcribe": "Good quality, faster processing", 
            "whisper-1": "Original model with more format options"
        }
        
        # Available TTS models
        self.tts_models = {
            "gpt-4o-mini-tts": "High quality, cost-effective",
            "tts-1": "Standard quality, fastest",
            "tts-1-hd": "Higher quality, slower"
        }
        
        # Available OpenAI voices
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
        
        # Check file extension as primary validation
        if file.filename:
            file_extension = Path(file.filename).suffix.lower()
            if file_extension not in self.supported_extensions:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported file extension: {file_extension}. Supported: {', '.join(self.supported_extensions)}"
                )
        
        # Check MIME type as secondary validation (some browsers send incorrect MIME types)
        if file.content_type and file.content_type not in self.supported_mime_types:
            # Log the actual MIME type for debugging
            print(f"Warning: Unexpected MIME type '{file.content_type}' for file '{file.filename}'. Proceeding based on file extension.")
        
        # Check file size
        contents = await file.read()
        if len(contents) > self.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. OpenAI limit: {self.max_file_size // 1024 // 1024}MB"
            )
        
        # Reset file pointer
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
            # Validate model choice
            if model not in self.transcription_models:
                model = "gpt-4o-transcribe"  # Default to highest quality
            
            # Save uploaded file temporarily with correct extension
            if file.filename:
                file_extension = Path(file.filename).suffix.lower()
            else:
                file_extension = '.m4a'  # Default for unknown files
                
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                contents = await file.read()
                temp_file.write(contents)
                temp_file_path = temp_file.name
            
            # Debug: Print file info
            print(f"Processing audio file: {file.filename}, MIME: {file.content_type}, Size: {len(contents)} bytes")
            
            # Transcribe using OpenAI's client
            with open(temp_file_path, 'rb') as audio_file:
                
                if model in ["gpt-4o-transcribe", "gpt-4o-mini-transcribe"]:
                    # New models only support json or text format
                    transcription = client.audio.transcriptions.create(
                        model=model,
                        file=audio_file,
                        response_format=response_format  # "text" or "json"
                    )
                else:
                    # whisper-1 supports more formats
                    transcription = client.audio.transcriptions.create(
                        model=model,
                        file=audio_file,
                        response_format=response_format
                    )
            
            # Cleanup temp file
            os.unlink(temp_file_path)
            
            # Handle response based on format
            if response_format == "text":
                return transcription.strip()
            else:
                return transcription.text.strip()
            
        except Exception as e:
            # Cleanup on error
            if 'temp_file_path' in locals():
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
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
            # Validate voice choice
            if voice not in self.available_voices:
                voice = "coral"  # Default to customer service voice
            
            # Validate model choice
            if model not in self.tts_models:
                model = "gpt-4o-mini-tts"  # Default to cost-effective model
            
            # Generate filename
            audio_filename = f"response_{session_id}_{int(asyncio.get_event_loop().time())}.mp3"
            audio_file_path = self.temp_dir / audio_filename
            
            # Generate audio using OpenAI TTS with streaming
            with client.audio.speech.with_streaming_response.create(
                model=model,
                voice=voice,
                input=text,
                instructions=instructions,
                response_format="mp3"
            ) as response:
                response.stream_to_file(str(audio_file_path))
            
            return str(audio_file_path)
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")
    
    async def process_voice_request(
        self, 
        audio_file: UploadFile, 
        session_id: str, 
        voice: str = "coral",
        transcription_model: str = "gpt-4o-transcribe",
        tts_model: str = "gpt-4o-mini-tts",
        tts_instructions: str = "Speak like a friendly and knowledgeable customer support specialist"
    ) -> VoiceResponse:
        """Complete voice-to-voice pipeline with OpenAI models"""
        
        # Validate audio file
        await self.validate_audio_file(audio_file)
        
        # Transcribe speech to text using OpenAI models
        transcribed_text = await self.transcribe_audio(
            file=audio_file,
            model=transcription_model,
            response_format="text"
        )
        
        if not transcribed_text.strip():
            raise HTTPException(status_code=400, detail="No speech detected in audio")
        
        # Process with existing AI (Tier 3)
        loop = asyncio.get_event_loop()
        ai_analysis: EnhancedAnalyzedQuery = await loop.run_in_executor(
            None,  # Use the default thread pool executor
            invoke_agent_with_analysis,
            transcribed_text,
            session_id
        )

        # Convert AI response to speech using OpenAI TTS
        audio_file_path = await self.generate_tts_audio(
            text=ai_analysis.response,
            voice=voice,
            session_id=session_id,
            model=tts_model,
            instructions=tts_instructions
        )
        
        # Return complete response
        return VoiceResponse(
            session_id=session_id,
            transcribed_text=transcribed_text,
            ai_response_text=ai_analysis.response,
            audio_file_path=audio_file_path,
            intent=ai_analysis.intent,
            intent_confidence=ai_analysis.intent_confidence,
            sub_intent=ai_analysis.sub_intent,
            sentiment=ai_analysis.sentiment,
            sentiment_score=ai_analysis.sentiment_score,
            complexity_score=ai_analysis.complexity_score,
            complexity_factors=ai_analysis.complexity_factors,
            entities=ai_analysis.entities,
            keywords=ai_analysis.keywords,
            user_type=ai_analysis.user_type,
            requires_tools=ai_analysis.requires_tools,
            escalate=getattr(ai_analysis, 'escalate', False),
            conversation_summary=getattr(ai_analysis, 'conversation_summary', ""),
            conversation_ended=getattr(ai_analysis, 'conversation_ended', False),
            transcription_model_used=transcription_model,
            tts_model_used=tts_model,
            voice_used=voice
        )
    
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
                except:
                    pass

# Global instance
voice_processor = VoiceProcessor()