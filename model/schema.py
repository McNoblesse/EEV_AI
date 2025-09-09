from pydantic import BaseModel
from typing import List, Optional, Any

class RequestPayload(BaseModel):
    user_query: str
    session_id: str
    

class PayloadResponse(BaseModel):
    agent_response: str
    session_id: str
    intent: str
    intent_confidence: float
    sub_intent: str
    sentiment: str
    sentiment_score: float
    complexity_score: int
    complexity_factors: List[str]
    entities: List[str]
    keywords: List[str]
    user_type: str


class TicketResponse(BaseModel):
    data: dict[str, Any]
    message_status: str | None = str

