from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, func, Enum, CheckConstraint, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from config.database import Base
import enum
from typing import Dict, Any, List

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
    __tablename__ = "conversations"

    # Core fields (existing)
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    user_query = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=True)
    
    # Existing analysis fields
    intent = Column(Enum(IntentEnum), nullable=True)
    sentiment = Column(Enum(SentimentEnum), nullable=True)
    complexity_score = Column(Integer, nullable=True)
    
    # Existing timestamps
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Existing channel fields
    channel = Column(Enum(ChannelEnum), nullable=True)
    
    # NEW fields (nullable=True for migration)
    intent_confidence = Column(Float, nullable=True)
    sub_intent = Column(String, nullable=True)
    
    sentiment_score = Column(Float, nullable=True)
    
    complexity = Column(Enum(ComplexityEnum), nullable=True)
    complexity_factors = Column(JSON, nullable=True)
    
    entities = Column(JSON, nullable=True)
    keywords = Column(JSON, nullable=True)
    user_type = Column(String, nullable=True)
    
    # Voice-specific fields (nullable for migration)
    transcription_model = Column(String, nullable=True)
    tts_model = Column(String, nullable=True)
    voice_used = Column(String, nullable=True)
    audio_file_path = Column(String, nullable=True)

    # Enhanced conversation management (nullable for migration)
    requires_knowledge_base = Column(Boolean, default=False, nullable=True)
    requires_human_escalation = Column(Boolean, default=False, nullable=True)
    can_respond_directly = Column(Boolean, default=False, nullable=True)
    
    conversation_summary = Column(Text, nullable=True)
    conversation_ended = Column(Boolean, default=False, nullable=True)
    end_reason = Column(String, nullable=True)
    
    follow_up_required = Column(Boolean, default=False, nullable=True)
    follow_up_details = Column(Text, nullable=True)
    
    # Analytics fields (nullable for migration)
    reasoning_steps = Column(JSON, nullable=True)
    tool_calls_used = Column(JSON, nullable=True)
    retrieval_context = Column(JSON, nullable=True)
    
    processing_time_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    model_used = Column(String, nullable=True)

    # Constraints (updated to handle nullable fields during migration)
    __table_args__ = (
        CheckConstraint('complexity_score >= 1 AND complexity_score <= 10', name='complexity_range'),
    )

# NEW tables (will be created, won't affect existing data)
class AgentSession(Base):
    __tablename__ = "agent_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), onupdate=func.now())
    
    channel = Column(Enum(ChannelEnum), nullable=False)
    user_id = Column(String, nullable=True)
    device_info = Column(JSON, nullable=True)
    
    current_intent = Column(Enum(IntentEnum), nullable=True)
    current_complexity = Column(Enum(ComplexityEnum), nullable=True)
    conversation_turn_count = Column(Integer, default=0)
    
    total_tokens_used = Column(Integer, default=0)
    average_response_time = Column(Float, nullable=True)
    escalation_count = Column(Integer, default=0)
    
    is_active = Column(Boolean, default=True)
    requires_follow_up = Column(Boolean, default=False)
    satisfaction_score = Column(Integer, nullable=True)
    
    langgraph_thread_id = Column(String, nullable=True)
    checkpoint_data = Column(JSON, nullable=True)

class KnowledgeBaseUsage(Base):
    __tablename__ = "knowledge_base_usage"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    query_text = Column(Text, nullable=False)
    search_terms = Column(JSON, nullable=True)
    results_count = Column(Integer, nullable=True)
    
    retrieval_success = Column(Boolean, default=True)
    response_relevance = Column(Integer, nullable=True)
    tools_used = Column(JSON, nullable=True)
    
    retrieval_time_ms = Column(Integer, nullable=True)
    source_documents = Column(JSON, nullable=True)

class EscalationLog(Base):
    __tablename__ = "escalation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    ticket_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    escalation_reason = Column(Text, nullable=False)
    original_query = Column(Text, nullable=False)
    analysis_summary = Column(JSON, nullable=True)
    
    assigned_agent = Column(String, nullable=True)
    resolution_time = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    status = Column(String, default="pending")
    priority = Column(Integer, default=1)
    
    customer_satisfaction = Column(Integer, nullable=True)
    agent_feedback = Column(Text, nullable=True)