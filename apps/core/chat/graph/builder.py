graph = None


def build_graph():
    from langgraph.graph import START, StateGraph

    from ..agents.supervisor import supervisor
    from .state import StateSchema

    g = StateGraph(StateSchema)
    g.add_node("supervisor", supervisor)
    g.add_edge(START, "supervisor")
    return g.compile()


def get_graph():
    global graph
    if graph is None:
        graph = build_graph()
    return graph
