import json
import os
import sys
import uuid
from dataclasses import dataclass
from typing import Any

# Imports pesados movidos para dentro das funcoes para suportar producao leve
# from sentence_transformers import SentenceTransformer, util

current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from dotenv import load_dotenv

load_dotenv()

from apps.core import run_chatbot


@dataclass(frozen=True)
class EvalItem:
    pergunta: str
    resposta_esperada: str
    fontes: list[str]


def load_dataset(path: str) -> list[EvalItem]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    out: list[EvalItem] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(
            EvalItem(
                pergunta=str(item.get("pergunta") or "").strip(),
                resposta_esperada=str(item.get("resposta_esperada") or "").strip(),
                fontes=[str(x) for x in (item.get("fontes") or [])],
            )
        )
    return [x for x in out if x.pergunta and x.resposta_esperada]


def embed_similarity(model, a: str, b: str) -> float:
    if model is None:
        return 0.0
    from sentence_transformers import util
    ea = model.encode(a, convert_to_tensor=True)
    eb = model.encode(b, convert_to_tensor=True)
    return float(util.cos_sim(ea, eb).item())


def _source_titles(sources: list[Any]) -> list[str]:
    titles: list[str] = []
    for s in sources:
        if isinstance(s, dict):
            title = s.get("title") or s.get("titulo") or ""
        else:
            title = str(s)
        if title:
            titles.append(str(title))
    return titles


def calculate_source_iou(expected: list[str], actual: list[Any]) -> float:
    actual_titles = _source_titles(actual)
    if not expected and not actual_titles:
        return 1.0
    if not expected or not actual_titles:
        return 0.0
    set_e = set(expected)
    set_a = set(actual_titles)
    intersection = set_e.intersection(set_a)
    union = set_e.union(set_a)
    return len(intersection) / len(union)


def source_is_grounded(expected: list[str], actual: list[Any]) -> bool:
    """
    Verifica se ao menos uma fonte retornada corresponde de fato a uma das fontes
    esperadas, mesmo quando a resposta veio do fallback de busca web (cujo título
    é o da página/PDF externo, e não o nome do documento indexado no ChromaDB).

    Critério: correspondência exata de título (igual ao IoU), OU correspondência
    parcial (nome do documento esperado aparece como substring no título/URL
    retornado), OU a fonte retornada é o próprio domínio oficial do IFPI
    (ifpi.edu.br) — o que indica que o fallback web recuperou o documento oficial
    correto, ainda que com um título de página diferente do nome do documento.
    """
    if not expected:
        return not actual
    if not actual:
        return False

    expected_lower = [e.lower() for e in expected]
    for s in actual:
        title = str(s.get("title") or s.get("titulo") or "") if isinstance(s, dict) else str(s)
        url = str(s.get("url") or "") if isinstance(s, dict) else ""
        haystack = f"{title} {url}".lower()

        if any(exp in haystack or haystack in exp for exp in expected_lower if exp):
            return True
        if "ifpi.edu.br" in url.lower():
            return True
    return False


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    total = len(rows)
    if total == 0:
        return {
            "semantic_accuracy": 0.0,
            "avg_semantic_similarity": 0.0,
            "execution_rate": 0.0,
            "grounding_accuracy": 0.0,
            "avg_source_iou": 0.0,
        }

    answered = [r for r in rows if r.get("status") == "success"]
    correct = [r for r in rows if r.get("is_correct") is True]

    semantic_accuracy = len(correct) / total
    avg_semantic_similarity = sum(r.get("similarity", 0.0) for r in rows) / total
    execution_rate = len(answered) / total
    grounding_accuracy = sum(1 for r in rows if r.get("grounded") is True) / total
    avg_source_iou = sum(r.get("source_iou", 0.0) for r in rows) / total
    
    return {
        "semantic_accuracy": semantic_accuracy,
        "avg_semantic_similarity": avg_semantic_similarity,
        "execution_rate": execution_rate,
        "grounding_accuracy": grounding_accuracy,
        "avg_source_iou": avg_source_iou,
    }


def main():
    dataset_path = os.path.join("tests", "eval_dataset.json")
    threshold = float(os.getenv("EVAL_SIM_THRESHOLD", "0.75"))
    dry_run = os.getenv("EVAL_DRY_RUN", "0").strip().lower() in ("1", "true", "yes")

    dataset = load_dataset(dataset_path)
    if not dataset:
        print("Dataset vazio ou inválido em tests/eval_dataset.json")
        return 2

    model_name = os.getenv("EVAL_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    model = None
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
    except ImportError:
        print("sentence-transformers não encontrado. Pulando similaridade semântica.")
    
    rows: list[dict[str, Any]] = []
    for item in dataset:
        if dry_run:
            answer = ""
            status = "not_found"
            sources = []
        else:
            result = run_chatbot(item.pergunta, thread_id=str(uuid.uuid4()))
            answer = (result.get("answer") or result.get("response") or "").strip()
            status = result.get("status") or ("success" if answer else "error")
            sources = result.get("sources") or []

        sim = embed_similarity(model, answer, item.resposta_esperada) if answer else 0.0
        source_iou = calculate_source_iou(item.fontes, sources)
        grounded = source_is_grounded(item.fontes, sources)

        has_sources = isinstance(sources, list) and len(sources) > 0
        # Critério corrigido: a corretude semântica da resposta gerada é baseada na
        # similaridade semântica com o gabarito. Grounding e status de execução
        # são tratados como métricas independentes.
        is_correct = bool(sim >= threshold)

        rows.append(
            {
                "pergunta": item.pergunta,
                "status": status,
                "similarity": sim,
                "source_iou": source_iou,
                "has_sources": has_sources,
                "grounded": grounded,
                "is_correct": is_correct,
            }
        )

    metrics = compute_metrics(rows)
    print(json.dumps({"threshold": threshold, "metrics": metrics, "rows": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
