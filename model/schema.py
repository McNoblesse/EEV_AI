from pydantic import BaseModel

class RequestPayload(BaseModel):
    user_query:str
    session_id:str
    
class PayloadResponse(BaseModel):
    agent_response:str
    session_id:str
    intent: str
    sentiment: str
    complexity_score: int
    
