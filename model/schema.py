from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class IntentType(str, Enum):
    greeting = "greeting"
    general_question = "general_question"
    technical_question = "technical_question"
    product_inquiry = "product_inquiry"
    complaint = "complaint"
    escalation_request = "escalation_request"
    follow_up = "follow_up"

class ComplexityType(str, Enum):
    simple = "simple"
    moderate = "moderate"
    complex = "complex"
    escalate = "escalate"

class ChannelType(str, Enum):
    chat = "chat"
    voice = "voice"
    email = "email"
    freshdesk = "freshdesk"
    whatsapp = "whatsapp"
    social = "social"

class EntityModel(BaseModel):
    text: str
    label: str
    confidence: float

class RequestPayload(BaseModel):
    user_query: str = Field(..., description="User's question or input")
    session_id: str = Field(..., description="Unique session identifier")
    channel: str = Field(default="chat", description="Communication channel: chat, voice, email, whatsapp")
    category: Optional[str] = Field(default=None, description="Document category for knowledge base lookup")  # ✅ ADD THIS
    
    # Optional fields for enhanced context
    message_history: Optional[List[Dict]] = Field(None, description="Previous messages in session")
    user_metadata: Optional[Dict] = Field(None, description="User profile information")
    context_data: Optional[Dict] = Field(None, description="Additional context data")
    
    class Config:
        schema_extra = {
            "example": {
                "user_query": "Tell me about our products",
                "session_id": "session_12345",
                "channel": "chat",
                "category": "Products"
            }
        }

class PayloadResponse(BaseModel):
    session_id: str
    response: str
    
    # Analysis results
    intent: str
    intent_confidence: float
    sub_intent: Optional[str]
    
    sentiment: str
    sentiment_score: float
    
    complexity_score: int
    complexity_factors: List[str]
    
    entities: List[EntityModel]
    keywords: List[str]
    user_type: str
    
    # Routing decisions
    escalate: bool
    conversation_summary: Optional[str]
    conversation_ended: bool
    
    # Enhanced analytics
    reasoning_steps: Optional[List[str]]
    retrieved_context: Optional[List[str]]
    tools_used: Optional[List[str]]
    processing_time_ms: Optional[int]
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "session_12345",
                "response": "To reset your password, please visit the account settings page...",
                "intent": "technical_question",
                "intent_confidence": 0.85,
                "sentiment": "neutral",
                "complexity_score": 3,
                "escalate": False
            }
        }

class VoiceRequest(BaseModel):
    session_id: str
    audio_data: Optional[str] = Field(None, description="Base64 encoded audio data")
    audio_file_url: Optional[str] = Field(None, description="URL to audio file")
    
    # Voice processing parameters
    voice: str = Field("coral", description="TTS voice to use")
    transcription_model: str = Field("gpt-4o-transcribe", description="Transcription model")
    tts_model: str = Field("gpt-4o-mini-tts", description="TTS model")
    channel: ChannelType = Field(ChannelType.voice, description="Voice channel")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "voice_session_123",
                "voice": "coral",
                "transcription_model": "gpt-4o-transcribe"
            }
        }

class VoiceResponse(BaseModel):
    session_id: str
    transcribed_text: str
    ai_response_text: str
    audio_file_path: str
    
    # Analysis results
    intent: str
    intent_confidence: float
    sentiment: str
    sentiment_score: float
    complexity_score: int
    
    # Technical details
    transcription_model_used: str
    tts_model_used: str
    voice_used: str
    
    # Enhanced analytics
    processing_time_ms: int
    audio_duration_seconds: Optional[float]
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "voice_session_123",
                "transcribed_text": "How do I update my billing information?",
                "ai_response_text": "You can update your billing information by...",
                "audio_file_path": "/path/to/audio.mp3"
            }
        }