import json
import os
import sys
import uuid
from dataclasses import dataclass
from typing import Any

ENV = os.getenv("ENV", "dev")

current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

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


def embed_similarity(model: Any, a: str, b: str) -> float:
    if ENV == "prod":
        # Fallback simples em prod para evitar erro de import
        return 0.5
    
    from sentence_transformers import util
    ea = model.encode(a, convert_to_tensor=True)
    eb = model.encode(b, convert_to_tensor=True)
    return float(util.cos_sim(ea, eb).item())


def calculate_source_iou(expected: list[str], actual: list[str]) -> float:
    if not expected and not actual:
        return 1.0
    if not expected or not actual:
        return 0.0
    set_e = set(expected)
    set_a = set(actual)
    intersection = set_e.intersection(set_a)
    union = set_e.union(set_a)
    return len(intersection) / len(union)


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    total = len(rows)
    if total == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "avg_source_iou": 0.0}

    answered = [r for r in rows if r.get("status") == "success"]
    correct = [r for r in rows if r.get("is_correct") is True]

    precision = (len(correct) / len(answered)) if answered else 0.0
    recall = len(correct) / total
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    
    avg_source_iou = sum(r.get("source_iou", 0.0) for r in rows) / total
    
    return {
        "precision": precision, 
        "recall": recall, 
        "f1": f1,
        "avg_source_iou": avg_source_iou
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
    model = SentenceTransformer(model_name)

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
        
        has_sources = isinstance(sources, list) and len(sources) > 0
        # Critério aprimorado: similaridade + presença de fontes + overlap de fontes mínimo
        is_correct = bool(sim >= threshold and status == "success" and has_sources and source_iou > 0)

        rows.append(
            {
                "pergunta": item.pergunta,
                "status": status,
                "similarity": sim,
                "source_iou": source_iou,
                "has_sources": has_sources,
                "is_correct": is_correct,
            }
        )

    metrics = compute_metrics(rows)
    print(json.dumps({"threshold": threshold, "metrics": metrics, "rows": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
