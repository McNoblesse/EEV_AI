from typing import TypedDict, List, Annotated, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from enum import Enum

class QueryComplexity(str, Enum):
    simple = "simple"  # Greetings, basic questions
    moderate = "moderate"  # FAQ, product inquiries
    complex = "complex"  # Technical issues, multi-step
    escalate = "escalate"  # Requires human intervention

class IntentType(str, Enum):
    greeting = "greeting"
    general_question = "general_question"
    technical_question = "technical_question"
    product_inquiry = "product_inquiry"
    complaint = "complaint"
    escalation_request = "escalation_request"
    follow_up = "follow_up"

class Entity(BaseModel):
    text: str
    label: str
    confidence: float

class ComprehensiveAnalysis(BaseModel):
    """Complete analysis of user query with routing decisions"""
    # Core classification
    intent: IntentType = Field(description="Primary intent classification")
    intent_confidence: float = Field(description="Confidence score 0.0-1.0")
    sub_intent: str = Field(description="More specific intent category")
    
    # Sentiment and complexity
    sentiment: str = Field(description="positive, negative, or neutral")
    sentiment_score: float = Field(description="Sentiment intensity -1.0 to 1.0")
    complexity: QueryComplexity = Field(description="Query complexity level")
    complexity_score: int = Field(description="Query complexity 1-10")
    complexity_factors: List[str] = Field(description="What makes query complex")

    # Content analysis
    entities: List[Entity] = Field(description="Key entities: products, technologies, issues")
    keywords: List[str] = Field(description="Important keywords from query")
    user_type: str = Field(description="technical, business, or general")

    # Routing decisions
    requires_knowledge_base: bool = Field(default=False)
    requires_human_escalation: bool = Field(default=False)
    can_respond_directly: bool = Field(default=False)
    suggested_tools: List[str] = Field(default_factory=list)
    
    # Response generation
    response: str = Field(description="The actual response to send to user", default="")
    reasoning: str = Field(description="Why these classifications were made", default="")
    conversation_summary: Optional[str] = Field(default=None)
    conversation_ended: bool = Field(default=False)

class AgentState(TypedDict):
    # Core message flow
    messages: Annotated[List[AnyMessage], add_messages]
    current_input: str
    
    # Analysis and reasoning
    analysis: Optional[ComprehensiveAnalysis]
    reasoning_steps: List[str]
    current_tool_calls: List[Dict[str, Any]]
    
    # Memory and context
    conversation_history: List[AnyMessage]
    knowledge_base_results: Optional[str]
    retrieved_context: List[str]
    
    # Control flow
    next_step: str  # "analyze", "reason", "retrieve", "respond", "escalate"
    max_steps: int
    current_step: int
    
    # Channel-specific
    channel: str  # "voice", "chat", "email", "freshdesk"
    session_id: str

class MessagesState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    analysis: Optional[ComprehensiveAnalysis]
    memory: Optional[List[AnyMessage]]
    kb_results: Optional[str]
    escalate: Optional[bool]
    conversation_summary: Optional[str]