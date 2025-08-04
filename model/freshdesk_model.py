from config.database import Base
from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime
from datetime import datetime


class Messages(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, nullable=False, index=True)
    user_message = Column(String, nullable=False)
    agent_response = Column(String, nullable=True)  # Allow NULL initially
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)  # Tracks when response is added
    message_type = Column(String, nullable=False, default="new")
    is_processed = Column(Boolean, default=False)  # Flag to track processing status
    session_id = Column(String, index=True, nullable=True)
    intent = Column(String, nullable=True)
    sentiment = Column(String, nullable=True)
    complexity_score = Column(Integer, nullable=True)
