import uuid
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from apps.core.agents.supervisor_agent import compiled_supervisor
from typing_extensions import TypedDict
from typing import Annotated

# --- GRAFO PRINCIPAL ---
class StateSchema(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

graph = StateGraph(StateSchema)
graph.add_node("supervisor", compiled_supervisor)
graph.add_edge(START, "supervisor")
compiled = graph.compile(checkpointer=MemorySaver())

def _get_text_from_msg(msg) -> str | None:
    """
    Normaliza diferentes formatos de mensagem para uma string.
    Aceita: dicts {'content': ...}, objetos BaseMessage, e content como lista.
    Retorna None se não houver texto útil.
    """
    content = None
    # dict-like
    if isinstance(msg, dict):
        content = msg.get("content")
    # objeto com atributo content (BaseMessage)
    elif hasattr(msg, "content"):
        content = msg.content
    else:
        # não reconhecido
        return None

    # se for lista, juntar os elementos não vazios
    if isinstance(content, list):
        parts = [str(c).strip() for c in content if c and str(c).strip()]
        content = " ".join(parts) if parts else None

    # garantir string e não vazia
    if isinstance(content, str):
        content = content.strip()
        if content == "":
            return None
        return content

    return None

def sanitize_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Remove mensagens vazias antes de enviar à API."""
    cleaned = []
    for msg in messages:
        if isinstance(msg, (HumanMessage, AIMessage)):
            if isinstance(msg.content, str) and msg.content.strip():
                cleaned.append(msg)
            elif isinstance(msg.content, list):
                parts = [str(c).strip() for c in msg.content if c and str(c).strip()]
                if parts:
                    msg.content = " ".join(parts)
                    cleaned.append(msg)
        else:
            cleaned.append(msg)
    return cleaned


def run_chatbot(user_input: str):
    # valida entrada do utilizador
    if not isinstance(user_input, str) or not user_input.strip():
        return "Não entendi"  # evita enviar payload vazio

    # prefira enviar um BaseMessage (HumanMessage) em vez de dict cru
    initial_messages = [HumanMessage(content=user_input.strip())]

    config = {"configurable": {"thread_id": "thread_id-01"}}
    candidate_responses = []

    try:
        # se a API/graph espera exatamente list[BaseMessage], passar HumanMessage evita conversões estranhas
        for chunk in compiled.stream({"messages": sanitize_messages(initial_messages)}, config=config, stream_mode="values"):
            if "messages" in chunk:
                for idx, raw_msg in enumerate(chunk["messages"]):
                    text = _get_text_from_msg(raw_msg)
                    print(f"[DEBUG] idx={idx} role={getattr(raw_msg, 'type', getattr(raw_msg, 'role', '??'))} content={repr(text)}")


                if not text:
                    # pula mensagens vazias (não processar)
                    continue

                # imprime todas as mensagens no terminal
                print(text)

                # detecta mensagens que parecem ser respostas do agente
                lower = text.lower()
                if not any(kw in lower for kw in ["transferred", "successfully", "❌", "erro"]) and len(text.split()) > 5:
                    candidate_responses.append(text)

    except Exception as e:
        # captura e loga o erro retornado da Anthropic (ou outro)
        print("Erro durante compiled.stream:", type(e), e)
        # opcional: re-raise se quiser que a exceção suba
        raise

    # retorna a última mensagem “real” do agente
    if candidate_responses:
        return candidate_responses[-1]
    return 'Não entendi'
