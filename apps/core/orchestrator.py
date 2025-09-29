import uuid
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from .agents.supervisor_agent import compiled_supervisor
from typing_extensions import TypedDict
from typing import Annotated
from langgraph.checkpoint.memory import MemorySaver

# --- GRAFO PRINCIPAL ---
class StateSchema(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

graph = StateGraph(StateSchema)
graph.add_node("supervisor", compiled_supervisor)
graph.add_edge(START, "supervisor")

memory = MemorySaver()
graph = graph.compile(checkpointer=memory)

def run_chatbot(user_input: str):
    config = {"configurable": {"thread_id": "1"}}
    
    candidate_responses = []

    # processa o fluxo
    for chunk in graph.stream(
        {"messages": [{"role": "user", "content": user_input}]},
        config,
        stream_mode="values",
    ):
        for msg in chunk.get("messages", []):
            if isinstance(msg.content, str) and msg.content.strip():
                # imprime todas as mensagens no terminal
                print(msg.content)

                # detecta mensagens que parecem ser respostas do agente
                lower = msg.content.lower()
                if not any(kw in lower for kw in [
                    "transferred", "successfully", "❌", "erro"
                ]) and len(msg.content.split()) > 5:  # ignora mensagens curtas de log
                    candidate_responses.append(msg.content)

    # retorna a última mensagem “real” do agente
    if candidate_responses:
        return candidate_responses[-1]
    return None