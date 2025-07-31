import uuid
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from langgraph_supervisor import create_supervisor
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict
from typing import Annotated

class StateSchema(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

def create_supervisor_graph(llm, agents):
    supervisor = create_supervisor(
        model=llm,
        agents=agents,
        prompt="""
        Você é um supervisor inteligente.

        Receba uma pergunta de um usuário e decida QUAL agente deve responder:

        - Se a pergunta for sobre o IFPI [...] → encaminhe para: consulta_institucional.
        - Se a pergunta for sobre assuntos gerais [...] → use Tavily.
        """,
        add_handoff_messages=True,
        add_handoff_back_messages=True,
        output_mode="full_history"
    )

    compiled_supervisor = supervisor.compile()
    graph = StateGraph(StateSchema)
    graph.add_node("supervisor", compiled_supervisor)
    graph.add_edge(START, "supervisor")

    return graph.compile(checkpointer=MemorySaver())

def run_interactive_loop(compiled_graph):
    print("Bem vindo ao chatbot IFPIA\n")
    while True:
        user_input = input("User: ")
        if user_input.lower() in ["exit", "quit", "q"]:
            print("Encerrando...")
            break

        thread_id = f"scheduler-{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        try:
            for chunk in compiled_graph.stream(
                {"messages": [{"role": "user", "content": user_input}]},
                config=config,
                stream_mode="values"
            ):
                for msg in chunk.get("messages", []):
                    content = getattr(msg, "content", None)
                    if isinstance(content, str) and content.strip():
                        msg.pretty_print()
        except Exception as e:
            print(f"\nErro na execução: {e}")
