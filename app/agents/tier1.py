from app.schemas.agent_schemas import AgentSchema
from app.toolkit.agent_toolkit import InitializeVectorStore

def Tier1(state:AgentSchema):
    retriever_qa = InitializeVectorStore(index_name=state['index_name'])
    prompt_plus_history = f"""Chat History \n{state['chat_history']} Query: \n{state['user_query']}"""
    return {
        "bot_response":retriever_qa.invoke({"query":prompt_plus_history})["result"],
        "agent_used": "tier_1"
    }