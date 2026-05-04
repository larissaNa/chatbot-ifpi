from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from .institutional_agent import consulta_institucional
from .web_agent import responder_web


def _last_user_message(messages: list[Any]) -> str:
    for msg in reversed(messages or []):
        if isinstance(msg, HumanMessage):
            return (msg.content or "").strip()
    return ""


def _conversation_context(messages: list[Any], *, limit: int = 12) -> str:
    lines: list[str] = []
    items = messages[:-1] if messages else []
    for msg in items[-limit:]:
        role = "Usuário" if isinstance(msg, HumanMessage) else "Assistente"
        content = str(getattr(msg, "content", "") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines).strip()


def _friendly_fallback(question: str, user_profile: str = "") -> str:
    q = (question or "").strip()
    profile_hint = ""
    if user_profile:
        profile_hint = " Considerei também as informações já conhecidas sobre você."
    return (
        "Resposta:\n"
        "Ainda não encontrei uma resposta confiável para isso nos documentos oficiais nem nas fontes web verificadas."
        f"{profile_hint} Se quiser, posso reformular a busca ou focar em um ponto mais específico da sua pergunta"
        f"{': ' + q if q else '.'}"
    )


def supervisor(state: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    messages = state.get("messages") or []
    question = _last_user_message(messages)
    conversation_context = _conversation_context(messages, limit=12)
    user_profile = str(state.get("user_profile") or "").strip()

    rag = consulta_institucional(
        question,
        conversation_context=conversation_context,
        user_profile=user_profile,
    )
    decision = {"route": "consulta_institucional", "rag_status": rag.get("status")}

    result = rag
    if rag.get("status") != "success":
        web = responder_web(
            question,
            conversation_context=conversation_context,
            user_profile=user_profile,
        )
        decision = {
            "route": "tavily_web",
            "rag_status": rag.get("status"),
            "web_status": web.get("status"),
        }
        result = web if web.get("status") == "success" else web

    if result.get("status") == "success":
        rendered = (result.get("rendered") or "").strip() or _friendly_fallback(question, user_profile)
    else:
        rendered = _friendly_fallback(question, user_profile)
    structured = {
        "status": result.get("status") or "error",
        "answer": result.get("answer") or rendered.replace("Resposta:\n", "", 1).strip(),
        "sources": result.get("sources") or [],
    }

    thoughts = json.dumps(
        {
            "decision": decision,
            "rag_docs": (rag.get("docs") or [])[:6],
            "conversation_context": conversation_context,
            "user_profile": user_profile,
        },
        ensure_ascii=False,
    )

    return {
        "messages": [
            AIMessage(
                content=rendered,
                additional_kwargs={"structured": structured, "thoughts": thoughts},
            )
        ]
    }