"""Offline personalization ranking metrics."""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping


def preference_compliance_at_k(
    ranked_ids: Iterable[Any],
    grades: Mapping[str, float],
    *,
    k: int = 5,
) -> float:
    ids = [str(value) for value in ranked_ids][: max(1, k)]
    if not ids:
        return 0.0
    compliant = sum(1 for pid in ids if float(grades.get(pid, 0.0)) > 0)
    return compliant / len(ids)


def ndcg_at_k(
    ranked_ids: Iterable[Any],
    grades: Mapping[str, float],
    *,
    k: int = 5,
) -> float:
    ids = [str(value) for value in ranked_ids][: max(1, k)]
    dcg = _dcg([float(grades.get(pid, 0.0)) for pid in ids])
    ideal = sorted((float(value) for value in grades.values()), reverse=True)[: max(1, k)]
    idcg = _dcg(ideal)
    return dcg / idcg if idcg > 0 else 0.0


def summarize_preference_eval(rows: Iterable[dict[str, Any]], *, k: int = 5) -> dict[str, Any]:
    items = list(rows)
    if not items:
        return {
            "case_count": 0,
            f"baseline_preference_compliance@{k}": 0.0,
            f"personalized_preference_compliance@{k}": 0.0,
            f"baseline_ndcg@{k}": 0.0,
            f"personalized_ndcg@{k}": 0.0,
            f"ndcg@{k}_delta": 0.0,
        }

    baseline_compliance = _avg(row["baseline_compliance"] for row in items)
    personalized_compliance = _avg(row["personalized_compliance"] for row in items)
    baseline_ndcg = _avg(row["baseline_ndcg"] for row in items)
    personalized_ndcg = _avg(row["personalized_ndcg"] for row in items)
    return {
        "case_count": len(items),
        f"baseline_preference_compliance@{k}": round(baseline_compliance, 4),
        f"personalized_preference_compliance@{k}": round(personalized_compliance, 4),
        f"preference_compliance@{k}_delta": round(personalized_compliance - baseline_compliance, 4),
        f"baseline_ndcg@{k}": round(baseline_ndcg, 4),
        f"personalized_ndcg@{k}": round(personalized_ndcg, 4),
        f"ndcg@{k}_delta": round(personalized_ndcg - baseline_ndcg, 4),
    }


def _dcg(grades: Iterable[float]) -> float:
    return sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(grades))


def _avg(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0
