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
    """
    Converte o score do ChromaDB (Distância L2) para Relevância [0, 1].
    No Chroma/L2, 0.0 é uma correspondência perfeita (distância zero).
    Usamos uma função de decaimento inverso: 1 / (1 + d).
    """
    try:
        s = float(score)
    except Exception:
        return 0.0

    # Se a distância for 0, relevância é 1.0. 
    # Se a distância for 1.0, relevância é 0.5.
    # Com threshold de 0.60, aceitamos distâncias de até ~0.66.
    if s < 0:
        return 0.0
    
    return 1.0 / (1.0 + s)


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
    k: int = 12,
    score_threshold: float = 0.40,
) -> dict[str, Any]:
    q = (question or "").strip()
    if not q:
        return {"status": "not_found", "docs": [], "sources": []}

    docs_with_scores: list[tuple[Any, float]] = []
    vectorstore = _get_vectorstore()
    if vectorstore is None:
        print("[RAG][ERROR] Vectorstore não disponível.")
        return {"status": "not_found", "docs": [], "sources": []}

    pairs1: list[tuple[Any, float]] = []
    if hasattr(vectorstore, "similarity_search_with_relevance_scores"):
        try:
            pairs1 = vectorstore.similarity_search_with_score(q, k=k)
            print(f"[RAG][SEARCH] query='{q[:80]}' k={k} → {len(pairs1)} resultados brutos")
        except Exception as e:
            print(f"[RAG][ERROR] similarity_search_with_score falhou: {e}")
            pairs1 = []

    pairs2: list[tuple[Any, float]] = []
    # pairs2 removido para evitar duplicidade, já que pairs1 agora usa similarity_search_with_score
    
    combined: list[tuple[Any, float]] = []
    for doc, score in pairs1:
        # Normalização do score: o modelo retorna [-1, 1], mapeamos para [0, 1]
        # Se for distância L2 (Chroma padrão), o score pode ser > 1.
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

    docs_with_scores.sort(key=lambda item: item[1], reverse=True)

    # Log dos scores brutos para diagnóstico
    for rank_i, (doc_i, rel_i) in enumerate(docs_with_scores[:k], start=1):
        meta_i = getattr(doc_i, "metadata", {}) or {}
        titulo_i = meta_i.get("titulo") or meta_i.get("documento_titulo") or "?"
        ordem_i = meta_i.get("ordem_no_documento", "?")
        print(f"[RAG][SCORE] #{rank_i} rel={rel_i:.4f} doc='{titulo_i}' chunk={ordem_i}")

    filtered = [item for item in docs_with_scores if item[1] >= float(score_threshold)][:k]

    if not filtered and docs_with_scores:
        print(f"[RAG][FALLBACK] Nenhum chunk acima do threshold {score_threshold}. Usando top-{k} sem filtro.")
        filtered = sorted(docs_with_scores, key=lambda item: item[1], reverse=True)[:k]
    else:
        print(f"[RAG][FILTER] {len(filtered)} chunks acima do threshold {score_threshold}.")

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


def _generate_search_query(question: str, context: str, profile: str) -> str:
    """
    Reescreve a pergunta do usuário para uma busca otimizada no banco vetorial,
    incorporando elementos do contexto (quem é o usuário, curso, turma, etc).
    """
    if not context and not profile:
        return question

    llm = _get_llm()
    # Prompt ultra-rápido para contextualizar a busca
    prompt = ChatPromptTemplate.from_template("""
    Dada a conversa abaixo, gere uma consulta de busca otimizada para encontrar a resposta completa nos documentos.
    
    REGRAS:
    1. Substitua termos vagos ("minha turma", "horário de hoje") por termos específicos (ex: "ADS V Módulo").
    2. Se a pergunta pedir informações de um conjunto (ex: "horários", "prazos", "regras"), use termos que ajudem a recuperar o documento inteiro.
    
    Perfil: {profile}
    Histórico: {context}
    Pergunta: {question}
    
    Consulta de Busca:""")
    
    try:
        chain = prompt | llm | StrOutputParser()
        rewritten = chain.invoke({"question": question, "context": context, "profile": profile}).strip()
        print(f"[RAG][QUERY_REWRITE] original='{question[:80]}' → reescrita='{rewritten[:80]}'")
        return rewritten if rewritten else question
    except Exception as e:
        print(f"[RAG][QUERY_REWRITE] Falha ao reescrever query: {e}")
        return question


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
    k: int = 12,
    score_threshold: float = 0.35,
    conversation_context: str = "",
    user_profile: str = "",
) -> dict[str, Any]:
    # NOVO: Contextualiza a busca antes de ir ao banco vetorial
    search_query = _generate_search_query(question, conversation_context, user_profile)
    
    # Agora o retrieval usa a query expandida (ex: "horários aula ADS V módulo") 
    # em vez de "horários para minha turma"
    retrieval = retrieve_with_threshold(search_query, k=k, score_threshold=score_threshold)
    
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
    func=lambda q, **kwargs: consulta_institucional(
        q, 
        conversation_context=kwargs.get("conversation_context", ""),
        user_profile=kwargs.get("user_profile", "")
    ),
    description="FONTE DE VERDADE. Consulta normas e documentos do IFPI. Use esta ferramenta para qualquer dúvida institucional. Ela entende referências ao histórico da conversa.",
)