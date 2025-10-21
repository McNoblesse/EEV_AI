from fastapi import Body
from typing import Annotated
from pydantic import BaseModel

class ChatAgentPayload(BaseModel):
    user_query: Annotated[str, Body(..., description="User's current query.")]
    session_id: Annotated[str, Body(..., description="User's session ID.")]
    index_name: Annotated[str, Body(..., description="Name of the Pinecone index to use for retrieval.")]
    
class ChatAgentResponse(BaseModel):
    bot_response: str
    session_id: str
    
class DeleteKnowledgeBaseResponse(BaseModel):
    message: str

class CreateKnowledgeBaseResponse(BaseModel):
    results: list[dict]