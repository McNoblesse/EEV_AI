from pydantic import BaseModel

class RequestPayload(BaseModel):
    user_query:str
    session_id:str
    
class PayloadResponse(BaseModel):
    bot_response:str
    session_id:str
    
