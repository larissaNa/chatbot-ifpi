import difflib
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from .builder import get_graph


def sanitize_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """
    Remove mensagens vazias e listas de mensagens vazias recursivamente.
    """
    sanitized = []

    for msg in messages:
        if isinstance(msg, (HumanMessage, AIMessage)):
            if isinstance(msg.content, str) and msg.content.strip():
                sanitized.append(msg)
            elif isinstance(msg.content, list):
                joined_content = " ".join(str(c).strip() for c in msg.content if c and str(c).strip())
                if joined_content:
                    msg.content = joined_content
                    sanitized.append(msg)
            elif isinstance(msg.content, dict) and "text" in msg.content:
                text = str(msg.content.get("text") or "").strip()
                if text:
                    msg.content = text
                    sanitized.append(msg)
        elif isinstance(msg, list):
            sanitized.extend(sanitize_messages(msg))

    return sanitized


def build_history_messages(history: list[dict[str, Any]] | None, *, limit: int = 12) -> list[BaseMessage]:
    items = history or []
    if limit > 0:
        items = items[-limit:]

    out: list[BaseMessage] = []
    for item in items:
        sender = str(item.get("sender") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if sender == "bot":
            out.append(AIMessage(content=content, id=str(item.get("id") or "")))
        else:
            out.append(HumanMessage(content=content, id=str(item.get("id") or "")))
    return out


def run_chatbot(
    user_input: str,
    thread_id: str = "1",
    *,
    history: list[dict[str, Any]] | None = None,
    user_profile: str = "",
):
    start_time = time.time()

    user_msg = HumanMessage(content=user_input.strip(), id=str(uuid.uuid4()))
    prior_messages = build_history_messages(history, limit=12)
    state = {
        "messages": prior_messages + [user_msg],
        "user_profile": (user_profile or "").strip(),
    }
    state["messages"] = sanitize_messages(state["messages"])

    logs = []
    answers = []
    structured = None

    print(f"--- Iniciando execução do grafo para: {user_input[:50]}... ---")
    _GRAPH_TIMEOUT = 120  # segundos — pipeline RAG+web+conv pode fazer até 3 chamadas LLM
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(get_graph().invoke, state)
        final_state = future.result(timeout=_GRAPH_TIMEOUT)
    except FuturesTimeoutError:
        executor.shutdown(wait=False)
        print(f"[RUNNER][TIMEOUT] Grafo não respondeu em {_GRAPH_TIMEOUT}s — retornando fallback.")
        return {
            "response": "Resposta:\nDesculpe, a resposta demorou mais do que o esperado. Tente novamente em instantes.",
            "status": "error",
            "answer": None,
            "sources": [],
            "thoughts": None,
        }
    except Exception as exc:
        executor.shutdown(wait=False)
        from apps.core.llm_config import BillingError
        if isinstance(exc.__cause__, BillingError) or isinstance(exc, BillingError):
            print("[RUNNER][BILLING] Saldo da API esgotado.")
            return {
                "response": "Resposta:\nO serviço de IA está temporariamente indisponível (saldo da API esgotado). Entre em contato com o administrador.",
                "status": "error",
                "answer": None,
                "sources": [],
                "thoughts": None,
            }
        raise
    executor.shutdown(wait=False)
    execution_time = time.time() - start_time
    print(f"--- Execução concluída em {execution_time:.2f} segundos ---")

    all_messages = sanitize_messages(final_state.get("messages", []))

    start_index = 0
    for i, msg in enumerate(all_messages):
        if isinstance(msg, HumanMessage) and msg.content == user_msg.content:
            if hasattr(msg, "id") and msg.id == user_msg.id:
                start_index = i + 1
                break
            if msg.content == user_msg.content:
                start_index = i + 1

    new_messages = all_messages[start_index:]

    for msg in new_messages:
        if not isinstance(msg, AIMessage):
            continue

        content = msg.content
        if msg.additional_kwargs and isinstance(msg.additional_kwargs.get("structured"), dict):
            structured = msg.additional_kwargs.get("structured")
        if msg.additional_kwargs and isinstance(msg.additional_kwargs.get("thoughts"), str):
            logs.append(msg.additional_kwargs.get("thoughts"))

        if isinstance(content, dict) and "text" in content:
            content = content["text"]
        elif isinstance(content, list):
            content = " ".join(str(c).strip() for c in content if c and str(c).strip())

        has_tool_calls = False
        if msg.tool_calls:
            has_tool_calls = True
            for tool_call in msg.tool_calls:
                logs.append(f"🛠️ Chamando ferramenta: {tool_call.get('name')} com argumentos: {tool_call.get('args')}")

        if not content:
            continue

        content_str = str(content)

        if has_tool_calls:
            logs.append(f"💭 Raciocínio: {content_str}")
            continue

        if any(
            keyword in content_str.lower()
            for keyword in [
                "transfer_to",
                "transferring back",
                "vou direcionar",
                "vejo que precisamos",
                "vou encaminhar",
                "encaminhando",
                "buscando",
                "pesquisando",
                "aguarde",
                "direcionar sua pergunta",
            ]
        ):
            logs.append(content_str)
            continue

        is_duplicate = False
        for prev_ans in answers:
            clean_prev = prev_ans.strip()
            clean_curr = content_str.strip()

            if len(clean_prev) > 50 and clean_prev in clean_curr:
                logs.append(f"🔄 Repetição filtrada (Supervisor - Contém): {content_str[:50]}...")
                is_duplicate = True
                break

            if len(clean_prev) > 30:
                similarity = difflib.SequenceMatcher(None, clean_prev, clean_curr).ratio()
                if similarity > 0.6:
                    logs.append(
                        f"🔄 Repetição filtrada (Supervisor - Similaridade {similarity:.2f}): {content_str[:50]}..."
                    )
                    is_duplicate = True
                    break

        if not is_duplicate:
            answers.append(content_str)

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

    payload["thoughts"] = pensamento if show_thoughts and pensamento else None
    return payload
