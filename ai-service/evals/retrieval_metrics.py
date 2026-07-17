"""Standard deterministic retrieval metrics for RAG and product experiments."""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping


def retrieval_metrics_at_k(
    ranked_ids: Iterable[Any],
    relevance_grades: Mapping[str, float],
    *,
    k: int = 5,
) -> dict[str, float]:
    """Calculate Recall@K, MRR@K and NDCG@K from explicit relevance labels."""
    limit = max(1, int(k))
    ranked = list(dict.fromkeys(str(value) for value in ranked_ids))[:limit]
    grades = {str(key): max(0.0, float(value)) for key, value in relevance_grades.items()}
    relevant = {key for key, grade in grades.items() if grade > 0}
    hits = [item for item in ranked if item in relevant]
    recall = len(set(hits)) / len(relevant) if relevant else 0.0
    first_rank = next((index for index, item in enumerate(ranked, 1) if item in relevant), None)
    reciprocal_rank = 1.0 / first_rank if first_rank else 0.0
    actual_dcg = _dcg([grades.get(item, 0.0) for item in ranked])
    ideal_dcg = _dcg(sorted(grades.values(), reverse=True)[:limit])
    return {
        f"recall@{limit}": round(recall, 4),
        f"mrr@{limit}": round(reciprocal_rank, 4),
        f"ndcg@{limit}": round(actual_dcg / ideal_dcg if ideal_dcg else 0.0, 4),
    }


def summarize_retrieval_rows(rows: Iterable[dict[str, Any]], *, k: int = 5) -> dict[str, Any]:
    items = list(rows)
    scored: list[dict[str, float]] = []
    for row in items:
        grades = row.get("relevance_grades") or {}
        if not isinstance(grades, Mapping) or not grades:
            continue
        scored.append(retrieval_metrics_at_k(row.get("ranked_ids") or [], grades, k=k))
    keys = (f"recall@{k}", f"mrr@{k}", f"ndcg@{k}")
    return {
        "evaluated_case_count": len(scored),
        "skipped_unlabeled_case_count": len(items) - len(scored),
        "metrics": {
            key: round(sum(item[key] for item in scored) / len(scored), 4) if scored else None
            for key in keys
        },
    }


def _dcg(grades: Iterable[float]) -> float:
    return sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(grades))
