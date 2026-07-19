"""Evaluate preference-aware reranking without external services or LLM calls."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.preference_metrics import (
    ndcg_at_k,
    preference_compliance_at_k,
    summarize_preference_eval,
)
from app.domain.shopping.personalization import apply_user_preferences
from app.domain.shopping.ranking import ProductRanker
from app.domain.shopping.schemas import ShoppingNeed

DEFAULT_DATASET = Path(__file__).parent / "datasets" / "preference_cases.jsonl"


def _load(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text and not text.startswith("#"):
                rows.append(json.loads(text))
    return rows


def evaluate(cases: list[dict[str, Any]], *, k: int) -> dict[str, Any]:
    ranker = ProductRanker()
    rows: list[dict[str, Any]] = []
    for case in cases:
        baseline_need = ShoppingNeed(category=case.get("category"))
        personalized_need, applied = apply_user_preferences(
            baseline_need, case.get("user_preferences") or {},
        )
        baseline = ranker.rank(case.get("candidates") or [], baseline_need)
        personalized = ranker.rank(case.get("candidates") or [], personalized_need)
        baseline_ids = [item.product_id for item in baseline]
        personalized_ids = [item.product_id for item in personalized]
        grades = {str(key): float(value) for key, value in (case.get("preference_grades") or {}).items()}
        rows.append({
            "id": case.get("id"),
            "baseline_ids": baseline_ids[:k],
            "personalized_ids": personalized_ids[:k],
            "baseline_compliance": preference_compliance_at_k(baseline_ids, grades, k=k),
            "personalized_compliance": preference_compliance_at_k(personalized_ids, grades, k=k),
            "baseline_ndcg": ndcg_at_k(baseline_ids, grades, k=k),
            "personalized_ndcg": ndcg_at_k(personalized_ids, grades, k=k),
            "applied_preferences": applied,
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(DEFAULT_DATASET),
        "metrics": summarize_preference_eval(rows, k=k),
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate preference-aware product reranking")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(_load(args.dataset), k=max(1, args.k))
    report["dataset"] = str(args.dataset)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
