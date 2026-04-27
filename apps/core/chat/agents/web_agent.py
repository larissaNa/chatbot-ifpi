import os
import re
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from apps.core.chat.prompts import get_web_answer_prompt

def _get_tavily_tool():
    from langchain_tavily import TavilySearch
    tavily_api_key = os.getenv("TAVILY_API_KEY")

    if tavily_api_key:
        return TavilySearch(max_results=2, tavily_api_key=tavily_api_key)

    @tool
    def disabled_search(query: str) -> str:
        """Search tool disabled because API key is missing."""
        return "Web search disabled: missing TAVILY_API_KEY."

    return disabled_search


NOT_FOUND_WEB = "Não foi possível obter fontes confiáveis na web."
NOT_FOUND_ANSWER = "Não encontrei essa informação nos documentos oficiais do IFPI."

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        from apps.core.llm_config import get_llm

        _llm = get_llm()
    return _llm


def _extract_results(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, dict) and isinstance(raw.get("results"), list):
        raw = raw["results"]
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or item.get("link") or "").strip()
        title = (item.get("title") or item.get("name") or "").strip()
        content = (item.get("content") or item.get("snippet") or item.get("text") or "").strip()
        if not url:
            continue
        out.append({"title": title or url, "url": url, "content": content})
    return out


def _sources_text(results: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for i, result in enumerate(results, start=1):
        title = result.get("title") or ""
        url = result.get("url") or ""
        content = result.get("content") or ""
        blocks.append(
            "\n".join(
                [
                    f"[Fonte {i}]",
                    f"Título: {title}",
                    f"URL: {url}",
                    "Trecho:",
                    content,
                ]
            )
        )
    return "\n\n".join(blocks).strip()


def web_search(question: str, *, max_results: int = 4) -> dict[str, Any]:
    q = (question or "").strip()
    if not q:
        return {"status": "error", "message": "Pergunta vazia.", "results": []}

    tavily_tool = _get_tavily_tool()
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        return {"status": "error", "message": "TAVILY_API_KEY ausente.", "results": []}

    raw = None
    try:
        if hasattr(tavily_tool, "max_results"):
            try:
                tavily_tool.max_results = int(max_results)
            except Exception:
                pass
        if hasattr(tavily_tool, "invoke"):
            raw = tavily_tool.invoke(q)
        else:
            raw = tavily_tool(q)
    except Exception as e:
        return {"status": "error", "message": str(e), "results": []}

    results = _extract_results(raw)
    return {"status": "success", "results": results}


def responder_web(
    question: str,
    *,
    max_results: int = 4,
    conversation_context: str = "",
    user_profile: str = "",
) -> dict[str, Any]:
    tavily_tool = _get_tavily_tool()
    search = web_search(question, max_results=max_results)
    results = search.get("results") or []

    if search.get("status") != "success" or not results:
        return {
            "status": "error",
            "answer": NOT_FOUND_WEB,
            "sources": [],
            "rendered": f"Resposta:\n{NOT_FOUND_WEB}",
        }

    prompt = ChatPromptTemplate.from_template(get_web_answer_prompt())
    chain = prompt | _get_llm() | StrOutputParser()

    answer = chain.invoke(
        {
            "sources_text": _sources_text(results),
            "question": (question or "").strip(),
            "not_found_answer": NOT_FOUND_ANSWER,
            "conversation_context": (conversation_context or "").strip() or "Sem histórico relevante.",
            "user_profile": (user_profile or "").strip() or "Nenhuma informação adicional conhecida.",
        }
    )
    answer = (answer or "").strip()

    sources = [{"title": result.get("title") or result.get("url"), "url": result.get("url")} for result in results if result.get("url")]
    sources = sources[:5]

    if answer == NOT_FOUND_ANSWER:
        return {
            "status": "not_found",
            "answer": NOT_FOUND_ANSWER,
            "sources": [],
            "rendered": f"Resposta:\n{NOT_FOUND_ANSWER}",
        }

    rendered_lines = [f"Resposta:\n{answer}", "", "Fontes:"]
    for source in sources:
        rendered_lines.append(f"- {source.get('title')} - {source.get('url')}")
    rendered = "\n".join(rendered_lines).strip()

    if not re.search(r"https?://", rendered):
        return {
            "status": "error",
            "answer": NOT_FOUND_WEB,
            "sources": [],
            "rendered": f"Resposta:\n{NOT_FOUND_WEB}",
        }

    return {"status": "success", "answer": answer, "sources": sources, "rendered": rendered}
