from langgraph.graph import START, StateGraph

from ..agents.supervisor import supervisor
from .state import StateSchema


def build_graph():
    graph = StateGraph(StateSchema)
    graph.add_node("supervisor", supervisor)
    graph.add_edge(START, "supervisor")
    return graph.compile()


graph = build_graph()
