from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, func, Enum, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from config.database import Base
import enum

# Enums
class IntentEnum(enum.Enum):
    greeting = "greeting"
    technical_question = "technical_question"
    product_inquiry = "product_inquiry"
    complaint = "complaint"
    escalation_request = "escalation_request"
    general_question = "general_question"
    follow_up = "follow_up"

class SentimentEnum(enum.Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"

class ComplexityEnum(enum.Enum):
    simple = "simple"
    moderate = "moderate"
    complex = "complex"
    escalate = "escalate"

class ChannelEnum(enum.Enum):
    chat = "chat"
    voice = "voice"
    email = "email"
    freshdesk = "freshdesk"
    whatsapp = "whatsapp"
    social = "social"


class Conversation(Base):
    """
    Core conversation data - ALL columns used in the codebase
    This version includes all fields until full migration to split tables
    """
    __tablename__ = "conversations"

    # Core fields
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    user_query = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=True)
    
    # Classification
    intent = Column(String, nullable=True)  # Changed from Enum to String for flexibility
    intent_confidence = Column(Float, nullable=True)
    sub_intent = Column(String, nullable=True)
    sentiment = Column(String, nullable=True)  # Changed from Enum to String
    sentiment_score = Column(Float, nullable=True, default=0.0)
    complexity_score = Column(Integer, nullable=True)
    
    # Channel & Escalation
    channel = Column(String, nullable=True)  # Changed from Enum to String
    requires_escalation = Column(Boolean, default=False)
    
    # User info
    user_type = Column(String, nullable=True)
    
    # Conversation state
    conversation_summary = Column(Text, nullable=True)
    conversation_ended = Column(Boolean, default=False)
    
    # Analysis data (will be moved to conversation_analytics table eventually)
    entities = Column(JSONB, nullable=True)
    keywords = Column(JSONB, nullable=True)
    complexity_factors = Column(JSONB, nullable=True)
    
    # Reasoning trace (will be moved to conversation_analytics table eventually)
    reasoning_steps = Column(JSONB, nullable=True)
    tool_calls_used = Column(JSONB, nullable=True)
    retrieval_context = Column(JSONB, nullable=True)
    
    # Performance metrics (will be moved to conversation_analytics table eventually)
    processing_time_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    model_used = Column(String, nullable=True)
    
    # Voice-specific fields (will be moved to voice_metadata table eventually)
    transcription_model = Column(String, nullable=True)
    tts_model = Column(String, nullable=True)
    voice_used = Column(String, nullable=True)
    audio_file_path = Column(String, nullable=True)
    audio_duration_seconds = Column(Float, nullable=True)
    transcription_confidence = Column(Float, nullable=True)
    
    # Timestamps
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships (for future use with split tables)
    analytics = relationship(
        "ConversationAnalytics", 
        back_populates="conversation", 
        cascade="all, delete-orphan",
        uselist=False
    )
    voice_metadata = relationship(
        "VoiceMetadata", 
        back_populates="conversation", 
        cascade="all, delete-orphan",
        uselist=False
    )


class ConversationAnalytics(Base):
    """
    Separate analytics table for debug/analysis data
    Use this for new conversations instead of putting data in main table
    """
    __tablename__ = "conversation_analytics"
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(
        Integer, 
        ForeignKey('conversations.id', ondelete='CASCADE'), 
        nullable=False, 
        unique=True,
        index=True
    )
    
    # Extracted data
    entities = Column(JSONB, nullable=True)
    keywords = Column(JSONB, nullable=True)
    complexity_factors = Column(JSONB, nullable=True)
    
    # Reasoning trace
    reasoning_steps = Column(JSONB, nullable=True)
    tool_calls_used = Column(JSONB, nullable=True)
    retrieval_context = Column(JSONB, nullable=True)
    
    # Performance metrics
    processing_time_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    model_used = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    conversation = relationship("Conversation", back_populates="analytics")


class VoiceMetadata(Base):
    """
    Separate table for voice-specific metadata
    Use this for voice conversations instead of main table
    """
    __tablename__ = "voice_metadata"
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(
        Integer, 
        ForeignKey('conversations.id', ondelete='CASCADE'), 
        nullable=False, 
        unique=True,
        index=True
    )
    
    transcription_model = Column(String, nullable=True)
    tts_model = Column(String, nullable=True)
    voice_used = Column(String, nullable=True)
    audio_file_path = Column(String, nullable=True)
    audio_duration_seconds = Column(Float, nullable=True)
    transcription_confidence = Column(Float, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    conversation = relationship("Conversation", back_populates="voice_metadata")


class AgentSession(Base):
    __tablename__ = "agent_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), onupdate=func.now())
    
    channel = Column(String, nullable=False)
    user_id = Column(String, nullable=True)
    device_info = Column(JSON, nullable=True)
    
    current_intent = Column(String, nullable=True)
    current_complexity = Column(String, nullable=True)
    conversation_turn_count = Column(Integer, default=0)
    
    total_tokens_used = Column(Integer, default=0)
    average_response_time = Column(Float, nullable=True)
    escalation_count = Column(Integer, default=0)
    
    is_active = Column(Boolean, default=True)
    requires_follow_up = Column(Boolean, default=False)
    satisfaction_score = Column(Integer, nullable=True)


class DocumentUpload(Base):
    """Knowledge base document uploads with client isolation"""
    __tablename__ = "document_uploads"
    
    # Primary identification
    id = Column(Integer, primary_key=True, index=True)
    
    client_id = Column(String, nullable=False, index=True)  # NEW FIELD
    client_name = Column(String, nullable=True)  # Optional friendly name
    
    filename = Column(String, nullable=False, index=True)
    original_filename = Column(String, nullable=False)
    
    # Categorization
    category = Column(String, nullable=False, index=True)
    file_type = Column(String, nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    
    # Status tracking
    status = Column(String, nullable=False, default="pending", index=True)
    error_message = Column(Text, nullable=True)
    
    # Upload metadata
    upload_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    uploaded_by = Column(String, nullable=True)
    
    # Processing results
    chunk_count = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    text_preview = Column(Text, nullable=True)
    
    # Vector store metadata
    vector_ids = Column(JSON, nullable=True)
    namespace = Column(String, nullable=True)  # Format: "client_{client_id}_{category}"
    
    # Processing timing
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    
    # OCR metadata
    required_ocr = Column(Boolean, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    
    # Additional metadata - RENAMED from 'metadata'
    doc_metadata = Column(JSON, nullable=True)  # ✅ FIXED
    
    # Soft deletion
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class Client(Base):
    """Client/Tenant management for multi-tenancy"""
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String, unique=True, nullable=False, index=True)  # e.g., "acme_corp"
    client_name = Column(String, nullable=False)  # e.g., "Acme Corporation"
    
    # API Keys (each client has their own)
    api_key = Column(String, unique=True, nullable=False)
    api_key_hash = Column(String, nullable=False)  # Hashed for security
    
    # Pinecone namespace prefix
    namespace_prefix = Column(String, nullable=False)  # e.g., "client_acme"
    
    # Subscription details
    subscription_tier = Column(String, nullable=True)  # basic, premium, enterprise
    max_documents = Column(Integer, nullable=True, default=1000)
    max_storage_mb = Column(Integer, nullable=True, default=10000)  # 10GB
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Metadata
    contact_email = Column(String, nullable=True)
    company_domain = Column(String, nullable=True)
    client_metadata = Column(JSON, nullable=True)