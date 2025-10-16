from langgraph.graph import StateGraph, START, END

from agents.tier1 import Tier1
from agents.tier2 import Tier2
from agents.router_agent import AgentRouter
from schemas.agent_schemas import AgentSchema
from agents.conversation import ConversationAgent

agent_graph = StateGraph(AgentSchema)

agent_graph.add_node("AgentRouter", AgentRouter)
agent_graph.add_node("Tier1", Tier1)
agent_graph.add_node("Tier2", Tier2)
agent_graph.add_node("ConversationAgent", ConversationAgent)

agent_graph.add_conditional_edges(START, AgentRouter, {
    "tier_1": "Tier1",
    "tier_2": "Tier2",
    "conversation":"ConversationAgent"
})

agent_graph.add_edge("Tier1",   END)
agent_graph.add_edge("Tier2", END)
agent_graph.add_edge("ConversationAgent", END)

compiled_agent = agent_graph.compile()