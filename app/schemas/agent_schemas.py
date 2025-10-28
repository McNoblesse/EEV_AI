from typing import TypedDict, Literal
from pydantic import BaseModel, Field

class AgentSchema(TypedDict):
    user_query:str
    bot_response:str
    chat_history:str
    index_name:str
    agent_used:Literal["tier_1", "tier_2", "conversation"]

class EmailSummaryAgentSchema(BaseModel):
    subject: str = Field(..., description="Brief email subject line summarizing the escalated issue")
    html: str = Field(..., description="HTML-formatted email body containing the structured summary for human agents")
    
class RouterSchema(BaseModel):
    route:str=Literal["tier_1", "tier_2", "conversation"]
    
class UserQueryAnalysisSchema(BaseModel):
    intent: str = Field(..., description="The determined intent of the user's query")
    sentiment: str = Field(..., description="The sentiment of the user's query (e.g., positive, negative, neutral)")
    complexity_score: float = Field(..., description="A score representing the complexity of the user's query, between 1 (simple) and 10 (very complex)")