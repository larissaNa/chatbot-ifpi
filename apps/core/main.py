from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from .agents.supervisor_agent import supervisor
from typing_extensions import TypedDict
from typing import Annotated
from langgraph.checkpoint.memory import MemorySaver  # ou InMemorySaver

# --- GRAFO PRINCIPAL ---
class StateSchema(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

graph = StateGraph(StateSchema)
graph.add_node("supervisor", supervisor)
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

last_messages_count = 0

def run_chatbot(user_input: str):
    global last_messages_count
    config = {"configurable": {"thread_id": "1"}}

    # Envia input do usuário
    user_msg = HumanMessage(content=user_input.strip())
    # Pega o estado atual do grafo
    state = {"messages": [user_msg]}
    # Aplica sanitize_messages para filtrar mensagens vazias
    state["messages"] = sanitize_messages(state["messages"])

    logs = []
    answers  = []

    new_message_index = 0

    for chunk in graph.stream(state, config, stream_mode="values"):
        messages = sanitize_messages(chunk.get("messages", []))  # Filtra mensagens vazias

        if len(messages) > last_messages_count:
            new_messages = messages[last_messages_count:]
            last_messages_count = len(messages)
        else:
            new_messages = []

        for msg in messages:
            
            if isinstance(msg, AIMessage):
                content = msg.content

                if isinstance(content, dict) and "text" in content:
                    content = content["text"]
                elif isinstance(content, list):
                    content = " ".join(
                        str(c).strip() for c in content if c and str(c).strip()
                    )
                if not content:
                    continue

                # Classifica o conteúdo
                if any(keyword in content.lower() for keyword in [
                    "transfer_to", "transferring back", "vou direcionar", "vejo que precisamos"
                ]):
                    logs.append(content)
                else:
                    answers.append(content)

    # --- Saídas separadas ---
    pensamento = "\n".join(logs).strip()
    resposta = "\n".join(answers).strip()

    # Retorna um dicionário
    return {
        "response": resposta or "Sem resposta gerada.",
        "thoughts": pensamento or "Sem registros de raciocínio para esta pergunta."
    }