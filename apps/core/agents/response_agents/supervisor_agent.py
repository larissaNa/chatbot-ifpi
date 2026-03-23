from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from .consulta_agent import consulta_institucional
from .tavily_agent import responder_web


def _last_user_message(messages: list[Any]) -> str:
    for msg in reversed(messages or []):
        if isinstance(msg, HumanMessage):
            return (msg.content or "").strip()
    return ""


def supervisor(state: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    messages = state.get("messages") or []
    question = _last_user_message(messages)

    rag = consulta_institucional(question)
    decision = {"route": "consulta_institucional", "rag_status": rag.get("status")}

    result = rag
    if rag.get("status") != "success":
        web = responder_web(question)
        decision = {
            "route": "tavily_web",
            "rag_status": rag.get("status"),
            "web_status": web.get("status"),
        }
        result = web if web.get("status") == "success" else web

    rendered = (result.get("rendered") or "").strip() or "Resposta:\nNão encontrei essa informação nos documentos oficiais do IFPI."
    structured = {
        "status": result.get("status") or "error",
        "answer": result.get("answer") or "",
        "sources": result.get("sources") or [],
    }

    thoughts = json.dumps(
        {
            "decision": decision,
            "rag_docs": (rag.get("docs") or [])[:6],
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
