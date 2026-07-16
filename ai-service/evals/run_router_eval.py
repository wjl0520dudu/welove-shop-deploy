"""Run the Phase-2 router Golden Dataset.

Examples (from ``ai-service``):

    python -m evals.run_router_eval --mode rules
    python -m evals.run_router_eval --mode hybrid --output evals/reports/router.json

``hybrid`` uses the configured LLM only for cases not claimed by deterministic
rules. It calls the routing method directly and does not execute business agents.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from assistant.graph import AssistantGraph
from assistant.router import classify_high_confidence_rule
from core.config import config
from core.llm import get_llm
from evals.router_metrics import calculate_router_metrics

DEFAULT_DATASET = Path(__file__).parent / "datasets" / "router_cases.jsonl"


def _load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            item = json.loads(text)
            item.setdefault("id", f"line_{line_number}")
            cases.append(item)
    return cases


async def _evaluate(mode: str, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    graph = None
    if mode == "hybrid":
        llm = get_llm()
        if llm is None:
            raise RuntimeError("hybrid mode requires LLM_API_KEY/LLM_MODEL configuration")
        graph = AssistantGraph(llm)

    rows: list[dict[str, Any]] = []
    for case in cases:
        question = str(case.get("query") or "")
        image_url = "eval://image" if case.get("has_image") else ""
        if graph is None:
            rule = classify_high_confidence_rule(
                question,
                case.get("business_memory") or {},
                has_image=bool(image_url),
            )
            result = {
                "route": rule.route if rule.matched else "unknown",
                "route_confidence": rule.confidence,
                "route_source": "rule" if rule.matched else "fallback",
                "route_fallback_used": not rule.matched,
                "route_reason": rule.reason,
            }
        else:
            result = await graph._route({
                "question": question,
                "image_url": image_url,
                "messages": [],
                "conversation_id": f"router-eval-{case['id']}",
            })

        rows.append({
            "id": case["id"],
            "query": question,
            "expected_route": case["expected_route"],
            "predicted_route": result.get("route"),
            "route_confidence": result.get("route_confidence"),
            "route_source": result.get("route_source"),
            "fallback_used": bool(result.get("route_fallback_used")),
            "reason": result.get("route_reason"),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate low-cost Agent routing")
    parser.add_argument("--mode", choices=("rules", "hybrid"), default="rules")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    cases = _load_cases(args.dataset)
    rows = asyncio.run(_evaluate(args.mode, cases))
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "dataset": str(args.dataset),
        "model_name": config.LLM_MODEL if args.mode == "hybrid" else None,
        "router_config": {
            "rule_min_confidence": config.ROUTER_RULE_MIN_CONFIDENCE,
            "llm_low_confidence_threshold": config.ROUTER_LOW_CONFIDENCE_THRESHOLD,
            "orchestrator_hint_confidence": config.ROUTER_ORCHESTRATOR_HINT_CONFIDENCE,
        },
        "metrics": calculate_router_metrics(rows),
        "failures": [row for row in rows if row["predicted_route"] != row["expected_route"]],
        "cases": rows,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
