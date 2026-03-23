from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from .agents.response_agents.supervisor_agent import supervisor
from typing_extensions import TypedDict
from typing import Annotated
from langgraph.checkpoint.memory import MemorySaver  # ou InMemorySaver

# --- GRAFO PRINCIPAL ---
class StateSchema(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

graph = StateGraph(StateSchema)
graph.add_node("supervisor", supervisor)
graph.add_edge(START, "supervisor")

# memória de curto prazo 
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
            elif isinstance(msg.content, dict) and "text" in msg.content:
                text = str(msg.content.get("text") or "").strip()
                if text:
                    msg.content = text
                    sanitized.append(msg)

        # Se o item for uma lista de mensagens, processa recursivamente
        elif isinstance(msg, list):
            sanitized.extend(sanitize_messages(msg))

    return sanitized

import uuid
import time
import difflib

def run_chatbot(user_input: str, thread_id: str = "1"):
    start_time = time.time()
    config = {"configurable": {"thread_id": thread_id}}

    # Envia input do usuário
    user_msg = HumanMessage(content=user_input.strip(), id=str(uuid.uuid4()))
    
    # Pega o estado atual do grafo
    state = {"messages": [user_msg]}
    # Aplica sanitize_messages para filtrar mensagens vazias
    state["messages"] = sanitize_messages(state["messages"])

    logs = []
    answers  = []
    structured = None

    # Executa o grafo e coleta todas as mensagens finais
    print(f"--- Iniciando execução do grafo para: {user_input[:50]}... ---")
    final_state = graph.invoke(state, config)
    execution_time = time.time() - start_time
    print(f"--- Execução concluída em {execution_time:.2f} segundos ---")
    
    all_messages = sanitize_messages(final_state.get("messages", []))
    
    # Encontra o índice da mensagem do usuário atual
    start_index = 0
    for i, msg in enumerate(all_messages):
        if isinstance(msg, HumanMessage) and msg.content == user_msg.content:
             # Se usarmos IDs, seria melhor, mas content serve por enquanto se for único na janela recente
             # Com uuid no HumanMessage acima, podemos tentar comparar IDs se o grafo preservar
             if hasattr(msg, 'id') and msg.id == user_msg.id:
                 start_index = i + 1
                 break
             # Fallback: compara conteúdo
             if msg.content == user_msg.content:
                 start_index = i + 1
    
    # Processa apenas as mensagens geradas APÓS a mensagem do usuário atual
    new_messages = all_messages[start_index:]

    for msg in new_messages:
        if isinstance(msg, AIMessage):
            content = msg.content
            if msg.additional_kwargs and isinstance(msg.additional_kwargs.get("structured"), dict):
                structured = msg.additional_kwargs.get("structured")
            if msg.additional_kwargs and isinstance(msg.additional_kwargs.get("thoughts"), str):
                logs.append(msg.additional_kwargs.get("thoughts"))
            
            # Normaliza conteúdo
            if isinstance(content, dict) and "text" in content:
                content = content["text"]
            elif isinstance(content, list):
                content = " ".join(
                    str(c).strip() for c in content if c and str(c).strip()
                )
            
            # Se tiver chamadas de ferramenta, adiciona aos logs
            has_tool_calls = False
            if msg.tool_calls:
                has_tool_calls = True
                for tool_call in msg.tool_calls:
                     logs.append(f"🛠️ Chamando ferramenta: {tool_call.get('name')} com argumentos: {tool_call.get('args')}")

            if not content:
                continue

            content_str = str(content)

            # Se tem tool calls, o conteúdo é um pensamento -> LOG
            if has_tool_calls:
                 logs.append(f"💭 Raciocínio: {content_str}")
                 continue

            # Classifica o conteúdo
            if any(keyword in content_str.lower() for keyword in [
                "transfer_to", "transferring back", "vou direcionar", "vejo que precisamos",
                "vou encaminhar", "encaminhando", "buscando", "pesquisando", "aguarde",
                "direcionar sua pergunta"
            ]):
                logs.append(content_str)
            else:
                # Verificação de Duplicação:
                # Se esta mensagem contém integralmente uma resposta anterior (com tamanho relevante),
                # ou se é muito similar, assumimos que é uma repetição do Supervisor.
                is_duplicate = False
                for prev_ans in answers:
                    # Remove espaços extras para comparação mais robusta
                    clean_prev = prev_ans.strip()
                    clean_curr = content_str.strip()
                    
                    # 1. Checagem de contêm (existente)
                    if len(clean_prev) > 50 and clean_prev in clean_curr:
                        logs.append(f"🔄 Repetição filtrada (Supervisor - Contém): {content_str[:50]}...")
                        is_duplicate = True
                        break
                    
                    # 2. Checagem de similaridade (fuzzy matching)
                    # Se as mensagens forem > 60% similares, consideramos repetição
                    if len(clean_prev) > 30:
                        similarity = difflib.SequenceMatcher(None, clean_prev, clean_curr).ratio()
                        if similarity > 0.6:
                            logs.append(f"🔄 Repetição filtrada (Supervisor - Similaridade {similarity:.2f}): {content_str[:50]}...")
                            is_duplicate = True
                            break
                
                if not is_duplicate:
                    answers.append(content_str)

    # --- Saídas separadas ---
    pensamento = "\n".join(logs).strip()
    resposta = "\n".join(answers).strip()

    try:
        from flask import current_app, has_app_context
        show_thoughts = bool(current_app.config.get("SHOW_THOUGHTS")) if has_app_context() else False
    except Exception:
        show_thoughts = False

    payload = {"response": resposta}
    if structured:
        payload["status"] = structured.get("status")
        payload["answer"] = structured.get("answer")
        payload["sources"] = structured.get("sources")
        if structured.get("answer") and structured.get("sources") and resposta:
            payload["response"] = resposta

    if show_thoughts and pensamento:
        payload["thoughts"] = pensamento
    else:
        payload["thoughts"] = None

    return payload
