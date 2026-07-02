from __future__ import annotations

from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import Tool

from apps.core.chat.prompts import get_feedback_rewrite_prompt, get_rag_answer_prompt

NOT_FOUND_ANSWER = "Não encontrei essa informação nos documentos oficiais do IFPI."

# Padrões de "soft not found": respostas que são essencialmente "não encontrei" mas
# o LLM ainda acrescentou explicação extra, quebrando a igualdade exata.
# Detectamos pelo início da resposta para escalar para a web normalmente.
import re as _re_nf
_SOFT_NOT_FOUND_RE = _re_nf.compile(
    r"^não\s+encontr[ei]\b"                          # "Não encontrei uma lista..."
    r"|^não\s+(?:há|existe|consta)\s+(?:informação|lista|dado|registro|nenhum)"
    r"|^os?\s+documentos?\s+(?:fornecidos?\s+)?não\s+(?:cont[eé]m|incluem|apresentam|detalham|possuem)"
    r"|^não\s+foi\s+possível\s+(?:encontrar|localizar|identificar)"
    r"|^não\s+tenho\s+(?:essa\s+informação|informações?\s+sobre)",
    _re_nf.IGNORECASE,
)


def _is_not_found_answer(answer: str) -> bool:
    """
    Retorna True quando a resposta do LLM é essencialmente 'não encontrei',
    seja a frase exata NOT_FOUND_ANSWER ou uma variante com explicação extra.
    Usado para garantir escalada para a busca web nesses casos.
    """
    a = (answer or "").strip()
    if not a:
        return True
    # Correspondência exata — caminho principal
    if a == NOT_FOUND_ANSWER:
        return True
    # Resposta que começa com NOT_FOUND_ANSWER mas tem texto adicional (ex: "...Os documentos tratam de...")
    if a.startswith(NOT_FOUND_ANSWER):
        return True
    # Padrões de "soft not found" — o LLM não usou a frase exata mas expressou o mesmo
    return bool(_SOFT_NOT_FOUND_RE.match(a))


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


def _expand_with_sibling_chunks(
    filtered: list[tuple[Any, float]],
    vectorstore: Any,
    already_seen: dict[str, tuple[Any, float]],
    max_doc_chunks: int = 30,
) -> list[tuple[Any, float]]:
    """
    Para cada documento pequeno (total_chunks_doc <= max_doc_chunks) encontrado
    no top-k, busca todos os chunks restantes do mesmo documento.
    Documentos grandes (manuais, regulamentos extensos) não são expandidos para
    evitar inundar o contexto do LLM com conteúdo irrelevante.
    """
    if not filtered:
        return filtered

    seen_chunk_ids: set[str] = set()
    for doc, _ in filtered:
        meta = getattr(doc, "metadata", {}) or {}
        seen_chunk_ids.add(str(meta.get("chunk_id", "") or id(doc)))

    # Coleta todos os documentos únicos no top-k que sejam "pequenos"
    expandable: dict[str, int] = {}  # id_crenca → posição em que apareceu
    seen_crencas: set[str] = set()
    for rank_pos, (doc, _) in enumerate(filtered):
        meta = getattr(doc, "metadata", {}) or {}
        crenca = str(meta.get("id_crenca", ""))
        if not crenca or crenca in seen_crencas:
            continue
        seen_crencas.add(crenca)
        total = int(meta.get("total_chunks_doc", 999))
        if total <= max_doc_chunks:
            expandable[crenca] = rank_pos
            print(f"[RAG][EXPAND] Documento elegível para expansão: '{meta.get('titulo', crenca)}' ({total} chunks)")
        else:
            print(f"[RAG][EXPAND] Documento grande ignorado: '{meta.get('titulo', crenca)}' ({total} chunks > {max_doc_chunks})")

    if not expandable:
        return filtered

    min_relevance = min(rel for _, rel in filtered)
    extra: list[tuple[Any, float]] = []

    collection = getattr(vectorstore, "_collection", None)
    if collection is None:
        return filtered

    for i, (id_crenca, rank_pos) in enumerate(sorted(expandable.items(), key=lambda x: x[1])):
        try:
            result = collection.get(
                where={"id_crenca": {"$eq": id_crenca}},
                include=["documents", "metadatas"],
            )
            sibling_docs = result.get("documents") or []
            sibling_metas = result.get("metadatas") or []

            for doc_text, meta in zip(sibling_docs, sibling_metas):
                chunk_id = str(meta.get("chunk_id", "") or hash(doc_text))
                if chunk_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk_id)

                from langchain_core.documents import Document
                sibling_doc = Document(page_content=doc_text, metadata=meta)
                ordem = int(meta.get("ordem_no_documento", 99))
                relevance = max(0.0, min_relevance - 0.001 * (i + 1) - 0.0001 * ordem)
                extra.append((sibling_doc, relevance))
        except Exception as e:
            print(f"[RAG][EXPAND] Erro ao buscar siblings de {id_crenca}: {e}")

    if extra:
        print(f"[RAG][EXPAND] {len(extra)} chunks adicionais de {len(expandable)} documentos expandidos.")

    combined = filtered + extra
    combined.sort(key=lambda x: x[1], reverse=True)
    return combined


_PROVA_KEYWORDS = frozenset({
    "prova", "avaliação", "avaliações", "bimestral", "bimestrais",
    "quantos dias", "quando foi", "data da prova", "teste", "exame",
})

# Regex com \b (word boundary) para evitar falso-positivo por substring,
# ex: "prova" casando dentro de "aprovado", "comprovada", "reprovado" etc.,
# o que injetava indevidamente chunks de "Avaliações Bimestrais" em perguntas
# sobre o Manual do Servidor (estágio probatório, acumulação de cargos...).
_PROVA_KEYWORDS_RE = _re_nf.compile(
    r"\b(?:" + "|".join(_re_nf.escape(kw) for kw in _PROVA_KEYWORDS) + r")\b",
    _re_nf.IGNORECASE,
)

# Stop words que NÃO são nomes próprios e devem ser ignoradas na extração de entidades
_ENTITY_STOP = frozenset({
    "quais", "qual", "como", "quando", "onde", "quem", "quanto", "quantos",
    "quantas", "isso", "este", "esta", "esse", "essa", "aquele", "aquela",
    "ifpi", "campus", "curso", "turma", "aula", "aulas", "disciplina",
    "disciplinas", "horário", "horarios", "professor", "professora", "professores",
    "prof", "docente", "docentes", "semestre", "período", "periodo",
})


def _extract_professor_names(question: str) -> list[str]:
    """
    Extrai APENAS nomes de professores da pergunta — palavras que aparecem
    logo após "professor(a)", "prof." ou "docente".

    Usada exclusivamente para injeção por busca textual, evitando que
    palavras maiúsculas genéricas (cidades, siglas, etc.) disparem injeção
    de chunks irrelevantes.

    Exemplos:
      "quais as disciplinas do professor Sekeff?" → ["Sekeff"]
      "o IFPI de Piripiri é bom?"                → []   (sem gatilho de professor)
      "prof. Maria Silva ministra o quê?"        → ["Maria", "Silva"]
    """
    import re

    names: list[str] = []

    for match in re.finditer(
        r'(?:professora?|prof\.?|docente)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ]{2,}(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ]{2,})?)',
        question, re.IGNORECASE
    ):
        candidate = match.group(1).strip()
        for token in candidate.split():
            if token.lower() not in _ENTITY_STOP and len(token) >= 3:
                names.append(token)

    # Remove duplicatas preservando ordem
    seen: set[str] = set()
    unique: list[str] = []
    for n in names:
        key = n.lower()
        if key not in seen:
            seen.add(key)
            unique.append(n)
    return unique


def _extract_entity_names(question: str) -> list[str]:
    """
    Extrai nomes próprios (prováveis nomes de pessoas ou entidades específicas)
    da pergunta. Inclui estratégia 1 (gatilho professor) e estratégia 2
    (palavras capitalizadas pelo usuário).

    ATENÇÃO: esta função NÃO é usada para injeção por busca textual — para
    isso usa-se _extract_professor_names(), que é mais conservadora e evita
    falsos positivos com nomes de cidades, siglas, etc.
    """
    import re

    names: list[str] = []

    # Estratégia 1: padrão "professor <Nome>"
    for match in re.finditer(
        r'(?:professora?|prof\.?|docente)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ]{2,}(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ]{2,})?)',
        question, re.IGNORECASE
    ):
        candidate = match.group(1).strip()
        for token in candidate.split():
            if token.lower() not in _ENTITY_STOP and len(token) >= 3:
                names.append(token)

    # Estratégia 2: palavras que o próprio usuário escreveu em maiúscula
    for word in re.findall(r'\b([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]{2,})\b', question):
        if word.lower() not in _ENTITY_STOP:
            names.append(word)

    # Remove duplicatas preservando ordem
    seen: set[str] = set()
    unique: list[str] = []
    for n in names:
        key = n.lower()
        if key not in seen:
            seen.add(key)
            unique.append(n)
    return unique


def _inject_by_text_search(
    question: str,
    vectorstore: Any,
    seen_map: dict[str, tuple[Any, float]],
    base_relevance: float = 0.80,
) -> list[tuple[Any, float]]:
    """
    Busca textual direta por nomes de PROFESSORES detectados na pergunta.
    Usa _extract_professor_names() (mais conservadora) em vez de
    _extract_entity_names() para evitar injetar chunks irrelevantes quando
    o usuário menciona cidades, siglas ou outras palavras maiúsculas que
    não são nomes de docentes (ex: "IFPI de Piripiri", "UAB").
    """
    entity_names = _extract_professor_names(question)
    if not entity_names:
        return []

    collection = getattr(vectorstore, "_collection", None)
    if collection is None:
        return []

    from langchain_core.documents import Document

    extra: list[tuple[Any, float]] = []
    already_added: set[str] = set(seen_map.keys())
    found_any = False

    for name in entity_names:
        # Tenta variações de capitalização para cobrir MAIÚSCULA, Title Case, lower
        variants = sorted({
            name,
            name.upper(),
            name.capitalize(),
            name.lower(),
        })
        for variant in variants:
            try:
                result = collection.get(
                    where_document={"$contains": variant},
                    include=["documents", "metadatas"],
                )
                docs_list = result.get("documents") or []
                metas_list = result.get("metadatas") or []

                if not docs_list:
                    continue

                print(f"[RAG][TEXT_INJECT] '{variant}' → {len(docs_list)} chunk(s) via busca textual.")
                found_any = True

                for doc_text, meta in zip(docs_list, metas_list):
                    chunk_id = str(meta.get("chunk_id", "") or hash(doc_text))
                    if chunk_id in already_added:
                        continue
                    already_added.add(chunk_id)
                    extra.append((Document(page_content=doc_text, metadata=meta), base_relevance))

                break  # variante funcionou, não precisa tentar outras
            except Exception as e:
                print(f"[RAG][TEXT_INJECT] Erro buscando '{variant}': {e}")
                continue

    if not found_any:
        print(f"[RAG][TEXT_INJECT] Nenhum chunk encontrado via busca textual para: {entity_names}")

    return extra



def _inject_eval_docs(
    question: str,
    vectorstore: Any,
    seen_map: dict[str, tuple[Any, float]],
    base_relevance: float = 0.75,
) -> list[tuple[Any, float]]:
    """
    Quando a pergunta menciona provas/avaliações, busca DIRETAMENTE todos os chunks
    de documentos de avaliação via metadados, contornando o gap semântico entre
    queries sobre datas de prova e o formato dos documentos indexados (grade/calendário).
    """
    if not _PROVA_KEYWORDS_RE.search(question or ""):
        return []

    collection = getattr(vectorstore, "_collection", None)
    if collection is None:
        return []

    try:
        all_data = collection.get(include=["metadatas"])
        all_metas = all_data.get("metadatas") or []

        eval_crencas: set[str] = set()
        for meta in all_metas:
            titulo = str(meta.get("titulo") or meta.get("documento_titulo") or "").lower()
            if any(kw in titulo for kw in ("avali", "prova", "bimestral")):
                crenca = str(meta.get("id_crenca", ""))
                if crenca:
                    eval_crencas.add(crenca)

        if not eval_crencas:
            print("[RAG][EVAL_INJECT] Nenhum documento de avaliação nos metadados.")
            return []

        print(f"[RAG][EVAL_INJECT] Injetando chunks de {len(eval_crencas)} documento(s) de avaliação.")
        from langchain_core.documents import Document

        extra: list[tuple[Any, float]] = []
        for crenca in eval_crencas:
            result = collection.get(
                where={"id_crenca": {"$eq": crenca}},
                include=["documents", "metadatas"],
            )
            for doc_text, meta in zip(result.get("documents") or [], result.get("metadatas") or []):
                chunk_id = str(meta.get("chunk_id", "") or hash(doc_text))
                if chunk_id in seen_map:
                    continue
                extra.append((Document(page_content=doc_text, metadata=meta), base_relevance))

        return extra

    except Exception as e:
        print(f"[RAG][EVAL_INJECT] Erro: {e}")
        return []


_TITLE_STOPWORDS = frozenset({
    "horário", "horario", "horários", "horarios", "de", "da", "do", "das", "dos",
    "e", "aulas", "aula", "letivos", "letivo", "sábados", "sabados", "sábado", "sabado",
})


def _inject_by_course_title_match(
    question: str,
    vectorstore: Any,
    seen_map: dict[str, tuple[Any, float]],
    base_relevance: float = 0.78,
) -> list[tuple[Any, float]]:
    """
    Documentos de grade horária (ex: "HORÁRIO DE VESTUÁRIO", "HORÁRIOS DE
    MATEMÁTICA") são curtos e dominados por nomes de disciplinas e professores
    que se repetem em outros documentos similares — isso faz com que a busca
    semântica pura confunda documentos de cursos diferentes (ex: uma pergunta
    sobre "Matemática no curso de Vestuário" pode ranquear o documento de
    "HORÁRIOS DE MATEMÁTICA" acima do documento certo, "HORÁRIO DE VESTUÁRIO",
    que cai fora do top-k). Aqui extraímos o nome do curso a partir do próprio
    título do documento e comparamos diretamente contra a pergunta, contornando
    esse gap lexical — mesma estratégia de _inject_eval_docs/_inject_by_text_search.
    """
    import re

    collection = getattr(vectorstore, "_collection", None)
    if collection is None:
        return []

    q_lower = (question or "").lower()
    if not q_lower:
        return []

    try:
        all_data = collection.get(include=["metadatas"])
    except Exception as e:
        print(f"[RAG][TITLE_INJECT] Erro ao listar metadados: {e}")
        return []

    all_metas = all_data.get("metadatas") or []
    titulos: set[str] = set()
    for meta in all_metas:
        titulo = str(meta.get("titulo") or meta.get("documento_titulo") or "").strip()
        if titulo:
            titulos.add(titulo)

    matched_crencas: set[str] = set()
    for titulo in titulos:
        tokens = [
            t for t in re.findall(r"[A-Za-zÀ-ÿ]+", titulo.lower())
            if t not in _TITLE_STOPWORDS and len(t) >= 3
        ]
        # Exige que TODAS as palavras significativas do título apareçam na pergunta,
        # para evitar falsos positivos com títulos curtos/genéricos.
        if tokens and all(token in q_lower for token in tokens):
            for meta in all_metas:
                meta_titulo = str(meta.get("titulo") or meta.get("documento_titulo") or "").strip()
                if meta_titulo == titulo:
                    crenca = str(meta.get("id_crenca", ""))
                    if crenca:
                        matched_crencas.add(crenca)

    if not matched_crencas:
        return []

    print(f"[RAG][TITLE_INJECT] Pergunta cita curso/documento — injetando {len(matched_crencas)} documento(s) por título.")
    from langchain_core.documents import Document

    extra: list[tuple[Any, float]] = []
    already_added: set[str] = set(seen_map.keys())
    for crenca in matched_crencas:
        try:
            result = collection.get(where={"id_crenca": {"$eq": crenca}}, include=["documents", "metadatas"])
        except Exception as e:
            print(f"[RAG][TITLE_INJECT] Erro buscando chunks de {crenca}: {e}")
            continue
        for doc_text, meta in zip(result.get("documents") or [], result.get("metadatas") or []):
            chunk_id = str(meta.get("chunk_id", "") or hash(doc_text))
            if chunk_id in already_added:
                continue
            already_added.add(chunk_id)
            extra.append((Document(page_content=doc_text, metadata=meta), base_relevance))

    return extra


def retrieve_with_threshold(
    question: str,
    *,
    k: int = 8,
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

    # Injeção direta de documentos de avaliação quando a pergunta menciona provas
    eval_extra = _inject_eval_docs(q, vectorstore, seen_map)
    for doc, rel in eval_extra:
        doc_id = str(
            getattr(doc, "id", None)
            or getattr(doc, "metadata", {}).get("chunk_id")
            or hash(getattr(doc, "page_content", ""))
        )
        if doc_id not in seen_map:
            seen_map[doc_id] = (doc, rel)

    # Injeção por busca textual: quando a pergunta menciona nomes próprios
    # (professores, disciplinas específicas, etc.), busca chunks que contêm
    # aquele termo diretamente no texto — contorna o domínio de documentos grandes
    # (ex: Manual do Servidor) na busca semântica.
    text_extra = _inject_by_text_search(q, vectorstore, seen_map)
    for doc, rel in text_extra:
        doc_id = str(
            getattr(doc, "id", None)
            or getattr(doc, "metadata", {}).get("chunk_id")
            or hash(getattr(doc, "page_content", ""))
        )
        if doc_id not in seen_map:
            seen_map[doc_id] = (doc, rel)

    # Injeção por título de curso: quando a pergunta cita o nome de um curso/grade
    # cujo documento existe na base, injeta os chunks daquele documento diretamente
    # — contorna a confusão entre documentos de horário com vocabulário similar.
    title_extra = _inject_by_course_title_match(q, vectorstore, seen_map)
    for doc, rel in title_extra:
        doc_id = str(
            getattr(doc, "id", None)
            or getattr(doc, "metadata", {}).get("chunk_id")
            or hash(getattr(doc, "page_content", ""))
        )
        if doc_id not in seen_map:
            seen_map[doc_id] = (doc, rel)

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

    # Expansão de documento: para cada documento único nos resultados, busca
    # todos os chunks restantes desse documento para garantir cobertura completa.
    filtered = _expand_with_sibling_chunks(filtered, vectorstore, seen_map)

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


_INJECTION_PATTERNS = [
    # Marcadores de seção de instrução (###, ***, ---)
    r"#{2,}\s*(?:instrução|instruction|ignore|override|system|priorit|aviso|alert|warning|comando|command)",
    # Verbos de controle típicos de injection
    r"(?:ignore|ignorar|desconsider|esqueça|forget)\s+(?:all\s+)?(?:previous|prior|above|anterior|tudo|as instruções)",
    # Frases que direcionam o comportamento do modelo
    r"(?:responda?\s+(?:apenas|somente|só)|you\s+(?:must|should|have\s+to)\s+(?:respond|say|answer))",
    r"(?:nunca\s+(?:diga|mencione|revele|fale|informe)|never\s+(?:say|mention|reveal))",
    r"(?:você\s+(?:deve|precisa|tem\s+que|vai|irá)\s+(?:dizer|responder|ignorar|falar|afirmar))",
    # Declarações de prioridade / escopo de instrução
    r"(?:esta?\s+(?:documento|instrução|texto|prompt|mensagem)\s+(?:possui|tem|é)\s+(?:prioridade|priority|máxima|superior))",
    r"(?:instrução\s+(?:prioritária|oculta|secreta|especial|de sistema|do sistema))",
    r"(?:prioridade\s+máxima|highest\s+priority|override\s+all)",
    # Delimitadores de sistema comuns em ataques
    r"(?:\[INST\]|\[SYS\]|<\|system\|>|<\|im_start\|>|\[SYSTEM\]|<<SYS>>)",
    # Pedidos de não divulgação da injeção
    r"(?:nunca\s+diga|não\s+(?:revele|mencione|diga)\s+que\s+(?:isso|este?a?)\s+veio)",
    r"(?:never\s+(?:reveal|mention|say)\s+(?:this|that)\s+came?\s+from)",
]

import re as _re
_COMPILED_INJECTION = [_re.compile(p, _re.IGNORECASE) for p in _INJECTION_PATTERNS]


def _sanitize_chunk_content(content: str, source_title: str = "") -> str:
    """
    Detecta e neutraliza tentativas de prompt injection em chunks de documentos.

    Substitui linhas/parágrafos suspeitos por um marcador neutro, preservando
    o restante do conteúdo legítimo do documento.

    Defende contra: instrução oculta em texto branco/minúsculo, marcadores ###,
    verbos de controle ('ignore', 'responda apenas', 'nunca diga'), declarações
    de prioridade, e delimitadores de sistema.
    """
    if not content:
        return content

    lines = content.splitlines()
    clean_lines: list[str] = []
    flagged = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            clean_lines.append(line)
            continue

        is_injection = any(pat.search(stripped) for pat in _COMPILED_INJECTION)
        if is_injection:
            flagged += 1
            clean_lines.append("[conteúdo removido por política de segurança]")
            print(f"[RAG][SECURITY] Possível prompt injection detectado em '{source_title}': {stripped[:80]!r}")
        else:
            clean_lines.append(line)

    return "\n".join(clean_lines)


def _format_context(docs: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for d in docs:
        src = d.get("source") or {}
        title = src.get("title") or "Documento Oficial"
        url = src.get("url") or ""
        page = src.get("page")
        page_part = f"Página: {page}" if page not in (None, "", 0) else "Página: n/d"
        raw_content = str(d.get("content") or "")
        safe_content = _sanitize_chunk_content(raw_content, source_title=title)
        blocks.append(
            "\n".join(
                [
                    f"[Fonte {d.get('rank', '')}]",
                    f"Título: {title}",
                    f"URL: {url}",
                    page_part,
                    "Trecho:",
                    safe_content,
                ]
            )
        )
    return "\n\n".join(blocks).strip()


_PRONOMES_VAGOS = _re_nf.compile(
    r"\b(isso|aquilo|aquela?|esse[sa]?|este[sa]?|ela|ele|eles|elas"
    r"|minha?\s+turma|meu\s+curso|minha?\s+disciplina|minha?\s+prova"
    r"|aquela\s+prova|esse\s+professor|aquele\s+professor"
    r"|já\s+passou|ainda\s+tem|quando\s+é)\b",
    _re_nf.IGNORECASE,
)


def _generate_search_query(question: str, context: str, profile: str) -> str:
    """
    Reescreve a pergunta do usuário para uma busca otimizada no banco vetorial,
    incorporando elementos do contexto (quem é o usuário, curso, turma, etc).

    Só chama o LLM quando a pergunta contém pronomes vagos ou referências
    ao contexto — caso contrário retorna a pergunta original diretamente,
    evitando uma chamada desnecessária ao LLM e economizando ~1-3s.
    """
    if not context and not profile:
        return question

    # Sem referências ambíguas → a pergunta é auto-suficiente, não precisa de reescrita
    if not _PRONOMES_VAGOS.search(question):
        print(f"[RAG][QUERY_REWRITE] Sem pronomes vagos — usando pergunta original direto.")
        return question

    llm = _get_llm()
    prompt = ChatPromptTemplate.from_template("""
Dada a conversa abaixo, gere uma consulta de busca otimizada para encontrar a resposta nos documentos do IFPI.

REGRAS:
1. Substitua APENAS pronomes e referências vagas ("minha turma", "isso", "aquela prova", "esse professor") por termos concretos mencionados no histórico.
2. Mantenha nomes de professores, disciplinas e cursos EXATAMENTE como estão na pergunta original — não troque por sinônimos.
3. NÃO adicione curso/turma se a pergunta não os mencionar explicitamente. Adicionar informação não pedida estreita a busca e pode fazer o sistema perder o documento correto.
4. Se a pergunta envolve provas ou avaliações, inclua os termos "avaliações bimestrais" ou "provas" na query.
5. Se a pergunta não tiver referências vagas, retorne-a quase intacta, ajustando apenas termos técnicos óbvios.

Perfil: {profile}
Histórico: {context}
Pergunta: {question}

Consulta de Busca (responda SOMENTE com a query, sem explicações):""")

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
    # Se o LLM não gerou resposta ou retornou explicitamente NOT_FOUND, não há o que renderizar
    if not a or a == NOT_FOUND_ANSWER:
        return f"Resposta:\n{NOT_FOUND_ANSWER}"

    # Resposta válida: apresenta o texto e, se houver fontes, lista-as
    if not sources:
        return f"Resposta:\n{a}"

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


def _extract_keywords(question: str) -> str:
    """
    Extrai os termos mais informativos da pergunta para formar uma query de busca ampla.
    Remove stop words e palavras interrogativas, mantendo nomes, substantivos e termos técnicos.
    Exemplo: "quais as disciplinas do professor sekeff?" → "disciplinas professor sekeff"
    """
    stop_words = {
        "quais", "qual", "o", "a", "os", "as", "de", "do", "da", "dos", "das",
        "em", "no", "na", "nos", "nas", "por", "para", "com", "que", "é", "são",
        "me", "meu", "minha", "meus", "minhas", "um", "uma", "uns", "umas",
        "isso", "este", "esta", "estes", "estas", "esse", "essa", "esses", "essas",
        "tem", "ter", "há", "foi", "ser", "como", "quando", "onde", "se", "seu",
        "sua", "seus", "suas", "quem", "quanto", "quantos", "quantas", "já",
    }
    import re
    tokens = re.sub(r"[^\w\sÀ-ÿ]", " ", (question or "").lower()).split()
    keywords = [t for t in tokens if t not in stop_words and len(t) > 2]
    return " ".join(keywords)


def consulta_institucional(
    question: str,
    *,
    k: int = 10,
    score_threshold: float = 0.40,
    conversation_context: str = "",
    user_profile: str = "",
    today: str = "",
) -> dict[str, Any]:
    from datetime import datetime
    today = today or datetime.now().strftime("%d/%m/%Y")

    try:
        search_query = _generate_search_query(question, conversation_context, user_profile)
    except Exception as e:
        print(f"[RAG][ERROR] Falha ao gerar query de busca: {e}")
        search_query = question
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
    try:
        answer = chain.invoke(
            {
                "context": context,
                "question": (question or "").strip(),
                "not_found_answer": NOT_FOUND_ANSWER,
                "conversation_context": (conversation_context or "").strip() or "Sem histórico relevante.",
                "user_profile": (user_profile or "").strip() or "Nenhuma informação adicional conhecida.",
                "today": today,
            }
        )
    except Exception as e:
        print(f"[RAG][ERROR] Falha na chamada ao LLM: {e}")
        return {
            "status": "error",
            "answer": NOT_FOUND_ANSWER,
            "sources": [],
            "docs": docs,
            "rendered": f"Resposta:\n{NOT_FOUND_ANSWER}",
        }

    answer = (answer or "").strip()
    if _is_not_found_answer(answer):
        # LLM sinalizou "não encontrado" — com frase exata ou variante com explicação extra.

        # Otimização: se o melhor score dos docs recuperados é baixo (< 0.55),
        # os documentos claramente não têm a informação — retries com queries
        # alternativas vão produzir os mesmos docs irrelevantes e perder tempo.
        # Pulamos os retries e escalamos direto para a web.
        top_score = max((d.get("relevance", 0.0) for d in docs), default=0.0)
        if top_score < 0.55:
            print(
                f"[RAG][SKIP_RETRY] Top relevance={top_score:.3f} < 0.55 e LLM NOT_FOUND. "
                "Docs claramente irrelevantes — escalando direto para a web."
            )
            return {
                "status": "not_found",
                "answer": NOT_FOUND_ANSWER,
                "sources": [],
                "docs": docs,
                "rendered": f"Resposta:\n{NOT_FOUND_ANSWER}",
            }

        # Só faz retries quando os docs tinham relevância razoável (≥ 0.55) mas o
        # LLM não encontrou a resposta — pode ser problema na formulação da query.

        # Retry 1: a query reescrita pode ter sido específica demais e perdeu o documento correto.
        retry_queries: list[str] = []

        if search_query.strip().lower() != question.strip().lower():
            retry_queries.append(question)

        # Retry 2: extrai os substantivos/termos-chave da pergunta para ampliar a busca.
        # Exemplo: "quais as disciplinas do professor sekeff?" → "professor sekeff disciplinas"
        keywords = _extract_keywords(question)
        if keywords and keywords.strip().lower() not in [q.strip().lower() for q in retry_queries + [search_query, question]]:
            retry_queries.append(keywords)

        for i, retry_q in enumerate(retry_queries, start=1):
            print(f"[RAG][RETRY {i}] LLM sinalizou NOT_FOUND (top_score={top_score:.3f}). Tentando query: '{retry_q[:80]}'")
            retrieval2 = retrieve_with_threshold(retry_q, k=k, score_threshold=score_threshold)
            if retrieval2.get("status") == "success":
                docs2 = retrieval2.get("docs") or []
                sources2 = retrieval2.get("sources") or []
                context2 = _format_context(docs2)
                try:
                    answer2 = chain.invoke(
                        {
                            "context": context2,
                            "question": (question or "").strip(),
                            "not_found_answer": NOT_FOUND_ANSWER,
                            "conversation_context": (conversation_context or "").strip() or "Sem histórico relevante.",
                            "user_profile": (user_profile or "").strip() or "Nenhuma informação adicional conhecida.",
                            "today": today,
                        }
                    )
                except Exception as e:
                    print(f"[RAG][RETRY {i}][ERROR] Falha na chamada ao LLM: {e}")
                    continue
                answer2 = (answer2 or "").strip()
                if answer2 and not _is_not_found_answer(answer2):
                    print(f"[RAG][RETRY {i}] Retry bem-sucedido.")
                    return {
                        "status": "success",
                        "answer": answer2,
                        "sources": sources2,
                        "docs": docs2,
                        "rendered": _render_answer(answer2, sources2),
                    }
                print(f"[RAG][RETRY {i}] Retry também retornou NOT_FOUND.")

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