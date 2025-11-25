from enum import Enum
from typing import TypedDict, Literal, NotRequired
from pydantic import BaseModel, Field

class AgentSchema(TypedDict):
    user_query:str
    bot_response:str
    chat_history:str
    index_name:str
    agent_used:Literal["tier_1", "tier_2", "conversation"]
    session_id: str
    summary: NotRequired[str]
    
class RouterSchema(BaseModel):
    route:Literal["tier_1", "tier_2", "conversation"] = Field(..., description="Designated route for handling the user query")
    
class UserQueryAnalysisSchema(BaseModel):
    intent: str = Field(..., description="The determined intent of the user's query")
    sentiment: str = Field(..., description="The sentiment of the user's query (e.g., positive, negative, neutral)")
    complexity_score: float = Field(..., description="A score representing the complexity of the user's query, between 1 (simple) and 10 (very complex)")

def CategorizeChatFunc(category:list[str]):
    class CategorizeChat(BaseModel):
        chat_category: Enum("ChatCategory", {item: item for item in category})
    return CategorizeChat

class ConversationLogClassification(BaseModel):
    chat_log: Literal["conversation_ended", "conversation_not_ended"] = Field(..., description="Indicates whether the conversation has ended or not")
    
class ConversationSentimentClassification(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"] = Field(..., description="Sentiment classification of the conversation")

