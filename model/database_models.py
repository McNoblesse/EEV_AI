from sqlalchemy import Column, Integer, String, DateTime, func
from config.database import Base

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    user_query = Column(String, nullable=False)
    bot_response = Column(String, nullable=True)
    intent = Column(String, nullable=True)
    sentiment = Column(String, nullable=True)
    complexity_score = Column(Integer, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())