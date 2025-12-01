from fastapi import Body
from typing import Annotated
from pydantic import BaseModel, Field
from typing import Optional

class ChatAgentPayload(BaseModel):
    user_query: Annotated[str, Body(..., description="User's current query.")]
    session_id: Annotated[str, Body(..., description="User's session ID.")]
    index_name: Annotated[str, Body(..., description="Name of the Pinecone index to use for retrieval.")]
    agent_name: Optional[str] = Field(default=None)
    confidence_level: Optional[float] = Field(default=None, ge=0, le=90)

class ChatAgentResponse(BaseModel):
    bot_response: str
    session_id: str
    is_escalated: bool
    summary: Optional[str] = None

    confidence_score: float
    #confidence_level: Optional[float] = None
    #below_confidence_threshold: Optional[bool] = None
    #agent_name: Optional[str] = None
    
class DeleteKnowledgeBaseResponse(BaseModel):
    message: str

class CreateKnowledgeBaseResponse(BaseModel):
    results: list[dict]
    
class ConversationCategoryPayload(BaseModel):
    session_id: Annotated[str, Body(..., description="User's session ID.")]
    
class ConversationCategoryResponse(BaseModel):
    session_id: Annotated[str, Body(..., description="User's session ID.")]
    category: Annotated[str, Body(..., description="Category assigned to the chat.")]
    sentiment: Annotated[str, Body(..., description="Sentiment assigned to the chat.")]
    
class ConversationClassifyResponse(BaseModel):
    session_id: Annotated[str, Body(..., description="User's session ID.")]
    is_chat_end: Annotated[bool, Body(..., description="Indicates if the chat has ended.")]
