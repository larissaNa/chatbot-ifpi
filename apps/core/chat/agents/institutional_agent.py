from __future__ import annotations

from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import Tool

from apps.core.chat.prompts import get_feedback_rewrite_prompt, get_rag_answer_prompt

NOT_FOUND_ANSWER = "Não encontrei essa informação nos documentos oficiais do IFPI."

_llm = None

def _get_llm():
    global _llm
    if _llm is None:
        from apps.core.llm_config import get_llm
        _llm = get_llm()
    return _llm

def _get_vectorstore():
    from apps.core.documents.services.vectorstore_service import get_vectorstore
    return get_vectorstore()


def _score_to_relevance(score: float) -> float:
    try:
        s = float(score)
    except Exception:
        return 0.0

    if 0.0 <= s <= 1.0:
        return s
    if s > 1.0:
        return 1.0 / (1.0 + s)
    return 0.0


def _extract_source(metadata: dict[str, Any]) -> dict[str, Any]:
    title = (
        metadata.get("documento_titulo")
        or metadata.get("titulo")
        or metadata.get("documento")
        or "Documento Oficial"
    )
    url = metadata.get("fonte") or metadata.get("url") or ""
    page = (
        metadata.get("page")
        or metadata.get("page_number")
        or metadata.get("pagina")
        or metadata.get("paginas_estimadas")
        or None
    )
    return {"title": str(title), "url": str(url), "page": page}


def retrieve_with_threshold(
    question: str,
    *,
    k: int = 6,
    score_threshold: float = 0.60,
) -> dict[str, Any]:
    q = (question or "").strip()
    if not q:
        return {"status": "not_found", "docs": [], "sources": []}

    docs_with_scores: list[tuple[Any, float]] = []
    vectorstore = _get_vectorstore()
    if vectorstore is None:
        return {"status": "not_found", "docs": [], "sources": []}

    pairs1: list[tuple[Any, float]] = []
    if hasattr(vectorstore, "similarity_search_with_relevance_scores"):
        try:
            pairs1 = vectorstore.similarity_search_with_relevance_scores(q, k=k)
        except Exception:
            pairs1 = []

    pairs2: list[tuple[Any, float]] = []
    if hasattr(vectorstore, "similarity_search_with_score"):
        try:
            pairs2 = vectorstore.similarity_search_with_score(q, k=k)
        except Exception:
            pairs2 = []

    combined: list[tuple[Any, float]] = []
    for doc, rel in pairs1:
        try:
            r = float(rel)
        except Exception:
            r = 0.0
        if r < 0.0 or r > 1.0:
            r = 1.0 / (1.0 + abs(r))
        combined.append((doc, r))
    for doc, score in pairs2:
        combined.append((doc, _score_to_relevance(float(score))))

    seen_map: dict[str, tuple[Any, float]] = {}
    for doc, relevance in combined:
        doc_id = (
            getattr(doc, "id", None)
            or getattr(doc, "metadata", {}).get("chunk_id")
            or str(hash(getattr(doc, "page_content", "")))
        )
        prev = seen_map.get(str(doc_id))
        if not prev or relevance > prev[1]:
            seen_map[str(doc_id)] = (doc, relevance)

    docs_with_scores = list(seen_map.values())

    filtered = [(doc, score) for doc, score in docs_with_scores if score >= float(score_threshold)]
    filtered.sort(key=lambda item: item[1], reverse=True)

    if not filtered and docs_with_scores:
        filtered = sorted(docs_with_scores, key=lambda item: item[1], reverse=True)[:k]

    docs_out: list[dict[str, Any]] = []
    sources_out: list[dict[str, Any]] = []
    seen_sources: set[tuple[str, str]] = set()

    for idx, (doc, relevance) in enumerate(filtered, start=1):
        metadata = getattr(doc, "metadata", {}) or {}
        content = getattr(doc, "page_content", "") or ""

        docs_out.append(
            {
                "rank": idx,
                "relevance": float(relevance),
                "content": str(content),
                "metadata": metadata,
                "source": _extract_source(metadata),
            }
        )

        src = docs_out[-1]["source"]
        key = (str(src.get("title", "")), str(src.get("url", "")))
        if key not in seen_sources:
            seen_sources.add(key)
            sources_out.append(src)

    if not docs_out:
        return {"status": "not_found", "docs": [], "sources": []}

    return {"status": "success", "docs": docs_out, "sources": sources_out}


def _format_context(docs: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for d in docs:
        src = d.get("source") or {}
        title = src.get("title") or "Documento Oficial"
        url = src.get("url") or ""
        page = src.get("page")
        page_part = f"Página: {page}" if page not in (None, "", 0) else "Página: n/d"
        blocks.append(
            "\n".join(
                [
                    f"[Fonte {d.get('rank', '')}]",
                    f"Título: {title}",
                    f"URL: {url}",
                    page_part,
                    "Trecho:",
                    str(d.get("content") or ""),
                ]
            )
        )
    return "\n\n".join(blocks).strip()


def _render_answer(answer: str, sources: list[dict[str, Any]]) -> str:
    a = (answer or "").strip()
    if not a:
        a = NOT_FOUND_ANSWER

    if not sources:
        return f"Resposta:\n{NOT_FOUND_ANSWER}"

    lines = [f"Resposta:\n{a}", "", "Fontes:"]
    for source in sources:
        title = (source.get("title") or "Documento Oficial").strip()
        url = (source.get("url") or "").strip()
        page = source.get("page")
        page_part = f" (p. {page})" if page not in (None, "", 0) else ""
        if url:
            lines.append(f"- {title} - {url}{page_part}")
        else:
            lines.append(f"- {title}{page_part}")
    return "\n".join(lines).strip()


def consulta_institucional(
    question: str,
    *,
    k: int = 6,
    score_threshold: float = 0.60,
    conversation_context: str = "",
    user_profile: str = "",
) -> dict[str, Any]:
    retrieval = retrieve_with_threshold(question, k=k, score_threshold=score_threshold)
    if retrieval.get("status") != "success":
        rendered = f"Resposta:\n{NOT_FOUND_ANSWER}"
        return {
            "status": "not_found",
            "answer": NOT_FOUND_ANSWER,
            "sources": [],
            "docs": [],
            "rendered": rendered,
        }

    docs = retrieval.get("docs") or []
    sources = retrieval.get("sources") or []
    context = _format_context(docs)

    llm = _get_llm()
    chain = ChatPromptTemplate.from_template(get_rag_answer_prompt()) | llm | StrOutputParser()
    answer = chain.invoke(
        {
            "context": context,
            "question": (question or "").strip(),
            "not_found_answer": NOT_FOUND_ANSWER,
            "conversation_context": (conversation_context or "").strip() or "Sem histórico relevante.",
            "user_profile": (user_profile or "").strip() or "Nenhuma informação adicional conhecida.",
        }
    )

    answer = (answer or "").strip()
    if answer == NOT_FOUND_ANSWER:
        rendered = f"Resposta:\n{NOT_FOUND_ANSWER}"
        return {
            "status": "not_found",
            "answer": NOT_FOUND_ANSWER,
            "sources": [],
            "docs": docs,
            "rendered": rendered,
        }

    return {
        "status": "success",
        "answer": answer,
        "sources": sources,
        "docs": docs,
        "rendered": _render_answer(answer, sources),
    }


def melhorar_resposta_com_feedback(
    question: str,
    previous_answer: str,
    *,
    conversation_context: str = "",
    user_profile: str = "",
    k: int = 8,
    score_threshold: float = 0.45,
) -> dict[str, Any]:
    retrieval = retrieve_with_threshold(question, k=k, score_threshold=score_threshold)
    docs = retrieval.get("docs") or []
    sources = retrieval.get("sources") or []
    has_rag_context = retrieval.get("status") == "success" and bool(docs)
    context = _format_context(docs) if docs else "Nenhum trecho relevante foi recuperado dos documentos oficiais."

    llm = _get_llm()
    chain = ChatPromptTemplate.from_template(get_feedback_rewrite_prompt()) | llm | StrOutputParser()
    answer = chain.invoke(
        {
            "context": context,
            "question": (question or "").strip(),
            "previous_answer": (previous_answer or "").strip() or "Sem resposta anterior registrada.",
            "conversation_context": (conversation_context or "").strip() or "Sem histórico relevante.",
            "user_profile": (user_profile or "").strip() or "Nenhuma informação adicional conhecida.",
        }
    )

    answer = (answer or "").strip()
    if not answer:
        answer = (
            "Revendo sua pergunta, não encontrei base documental suficiente para responder com segurança "
            "de forma mais específica neste momento."
        )

    return {
        "status": "success" if answer else "not_found",
        "answer": answer,
        "sources": sources,
        "docs": docs,
        "has_rag_context": has_rag_context,
        "rendered": _render_answer(answer, sources) if sources else f"Resposta:\n{answer}",
    }


consulta_tool = Tool(
    name="consulta_institucional",
    func=lambda q: consulta_institucional(q),
    description="FONTE DE VERDADE. Responde perguntas baseadas nos documentos oficiais do IFPI, com threshold e fontes.",
)
