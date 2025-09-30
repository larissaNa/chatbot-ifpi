from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from .agents.supervisor_agent import compiled_supervisor
from typing_extensions import TypedDict
from typing import Annotated
from langgraph.checkpoint.memory import MemorySaver  # ou InMemorySaver

# --- GRAFO PRINCIPAL ---
class StateSchema(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

graph = StateGraph(StateSchema)
graph.add_node("supervisor", compiled_supervisor)
graph.add_edge(START, "supervisor")

# memória de curto prazo (só vive enquanto o processo roda)
memory = MemorySaver()
graph = graph.compile(checkpointer=memory)

def sanitize_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """
    Remove mensagens vazias e listas de mensagens vazias recursivamente.
    """
    sanitized = []

    for msg in messages:
        if isinstance(msg, (HumanMessage, AIMessage)):
            # Se o conteúdo é uma string não vazia, mantém
            if isinstance(msg.content, str) and msg.content.strip():
                sanitized.append(msg)

            # Se o conteúdo é uma lista, junta os elementos em uma string
            elif isinstance(msg.content, list):
                joined_content = " ".join(
                    str(c).strip() for c in msg.content if c and str(c).strip()
                )
                if joined_content:
                    msg.content = joined_content
                    sanitized.append(msg)

        # Se o item for uma lista de mensagens, processa recursivamente
        elif isinstance(msg, list):
            sanitized.extend(sanitize_messages(msg))

    return sanitized

def run_chatbot(user_input: str):
    config = {"configurable": {"thread_id": "1"}}

    # Envia input do usuário
    user_msg = HumanMessage(content=user_input.strip())
    
    # Pega o estado atual do grafo
    state = {"messages": [user_msg]}
    
    # Aplica sanitize_messages para filtrar mensagens vazias
    state["messages"] = sanitize_messages(state["messages"])

    # Envia para o grafo
    candidate_responses = []
    for chunk in graph.stream(state, config, stream_mode="values"):
        messages = chunk.get("messages", [])
        messages = sanitize_messages(messages)  # Filtra mensagens vazias

        for msg in messages:
            candidate_responses.append(msg.content)
            print(msg.content)

    return candidate_responses[-1] if candidate_responses else None
