from app.schemas.agent_schemas import AgentSchema
from app.toolkit.agent_toolkit import InitializeVectorStore

def Tier1(state:AgentSchema):
    retriever_qa = InitializeVectorStore(index_name=state['index_name'])
    return {
        "bot_response":retriever_qa.invoke({"query":state['user_query']})["result"],
        "agent_used": "tier_1"
    }