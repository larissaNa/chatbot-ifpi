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

_STOP_WORDS = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "por", "para", "com", "sem", "sob", "sobre",
    "que", "e", "ou", "mas", "se", "como", "qual", "quais", "quando", "onde", "quem",
    "é", "são", "foi", "eram", "está", "estão", "tem", "têm", "há", "ser", "ter",
    "ao", "à", "pelo", "pela", "pelos", "pelas", "isso", "isto", "aquilo", "me", "te",
    "lhe", "nos", "se", "já", "não", "sim", "muito", "mais", "menos", "bem", "mal",
    "também", "ainda", "só", "até", "desde", "entre", "depois", "antes",
    "qual", "quais", "quanto", "quantos", "quanta", "quantas",
}

# Palavras de sentimento/avaliação genéricas — removidas da query para melhorar busca
_SENTIMENT_WORDS = {
    "bom", "boa", "bons", "boas", "ruim", "ruins", "mau", "má", "maus", "más",
    "ótimo", "ótima", "ótimos", "ótimas", "péssimo", "péssima", "péssimos", "péssimas",
    "excelente", "excelentes", "terrível", "terríveis", "horrível", "horríveis",
    "legal", "bacana", "incrível", "incríveis", "maravilhoso", "maravilhosa",
    "chato", "chata", "difícil", "fácil", "melhor", "pior",
}

# Termos que indicam conteúdo relacionado ao IFPI
_IFPI_TERMS = {"ifpi", "instituto federal", "piauí", "piauí", "federal do piauí"}


def _results_are_ifpi_related(results: list[dict[str, Any]]) -> bool:
    """Retorna True se pelo menos um resultado menciona o IFPI nos metadados."""
    for result in results:
        text = (
            (result.get("url") or "") + " " +
            (result.get("title") or "") + " " +
            (result.get("content") or "")
        ).lower()
        if any(term in text for term in _IFPI_TERMS):
            return True
    return False

_QUESTION_STARTERS = re.compile(
    r"^(?:o que\s+|quem\s+|como\s+(?:é|está|são|estão|fica|ficam|funciona)?\s*|"
    r"quando\s+|onde\s+|qual\s+(?:é|são)?\s*|quais\s+(?:são)?\s*|"
    r"me\s+(?:fala|diga|explica|conta)\s+(?:sobre\s+)?"
    r"|você\s+(?:sabe|pode|conhece)\s+(?:me\s+dizer\s+)?"
    r"|(?:poderia?\s+)?(?:me\s+)?(?:dizer|informar|falar)\s+(?:sobre\s+|se\s+)?)",
    re.IGNORECASE,
)


def _build_search_query(question: str) -> str:
    """Convert a natural language question into a keyword-based search query."""
    q = (question or "").strip()
    if not q:
        return q

    # Strip leading question phrases ("como é", "me fala sobre", etc.)
    q_clean = _QUESTION_STARTERS.sub("", q).strip()

    # Tokenize and drop stop words and sentiment/evaluative words
    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9]+", q_clean)
    excluded = _STOP_WORDS | _SENTIMENT_WORDS
    keywords = [t for t in tokens if t.lower() not in excluded and len(t) >= 3]

    if not keywords:
        keywords = [t for t in re.findall(r"[A-Za-zÀ-ÿ0-9]+", q)
                    if t.lower() not in excluded and len(t) >= 3]

    # Ensure IFPI is part of the query for institutional scope
    has_ifpi = any(t.upper() == "IFPI" for t in keywords)
    if not has_ifpi:
        keywords = ["IFPI"] + keywords

    # For questions about quality/reputation of a campus/location, add "avaliação"
    q_lower = q.lower()
    is_quality_question = any(w in q_lower for w in [
        "bom", "boa", "ruim", "vale a pena", "recomenda", "qualidade", "avaliação",
        "opinião", "reputação", "conceito", "nota", "enade",
    ])
    if is_quality_question and "avaliação" not in q_lower and "avaliacao" not in q_lower:
        keywords.append("avaliação")

    query = " ".join(keywords)
    print(f"[WEB][QUERY] original='{question[:80]}' → query='{query[:100]}'")
    return query

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
        print("[WEB][ERROR] Pergunta vazia.")
        return {"status": "error", "message": "Pergunta vazia.", "results": []}

    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        print("[WEB][ERROR] TAVILY_API_KEY não configurada — busca web desabilitada.")
        return {"status": "error", "message": "TAVILY_API_KEY ausente.", "results": []}

    query = _build_search_query(q)
    tavily_tool = _get_tavily_tool()
    raw = None
    try:
        if hasattr(tavily_tool, "max_results"):
            try:
                tavily_tool.max_results = int(max_results)
            except Exception:
                pass
        if hasattr(tavily_tool, "invoke"):
            raw = tavily_tool.invoke(query)
        else:
            raw = tavily_tool(query)
    except Exception as e:
        print(f"[WEB][ERROR] Falha na busca Tavily: {e}")
        return {"status": "error", "message": str(e), "results": []}

    results = _extract_results(raw)
    print(f"[WEB][SEARCH] {len(results)} resultado(s) retornado(s).")
    return {"status": "success", "results": results}


def responder_web(
    question: str,
    *,
    max_results: int = 4,
    conversation_context: str = "",
    user_profile: str = "",
) -> dict[str, Any]:
    search = web_search(question, max_results=max_results)
    results = search.get("results") or []

    if search.get("status") != "success" or not results:
        return {
            "status": "error",
            "answer": NOT_FOUND_WEB,
            "sources": [],
            "rendered": f"Resposta:\n{NOT_FOUND_WEB}",
        }

    # Rejeita resultados sem relação com o IFPI antes de chamar o LLM
    if not _results_are_ifpi_related(results):
        print(f"[WEB][SCOPE] Nenhum resultado relacionado ao IFPI — descartando {len(results)} resultado(s).")
        return {
            "status": "not_found",
            "answer": NOT_FOUND_ANSWER,
            "sources": [],
            "rendered": f"Resposta:\n{NOT_FOUND_ANSWER}",
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
