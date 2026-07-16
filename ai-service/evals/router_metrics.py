"""Deterministic metrics for router regression reports."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable


def calculate_router_metrics(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    total = len(rows)
    if total == 0:
        return {
            "case_count": 0,
            "route_accuracy": 0.0,
            "misroute_rate": 0.0,
            "low_confidence_rate": 0.0,
            "rule_direct_rate": 0.0,
            "route_source_counts": {},
            "per_route": {},
        }

    correct = 0
    misrouted = 0
    low_confidence = 0
    rule_direct = 0
    source_counts: Counter[str] = Counter()
    per_route: dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        expected = str(row.get("expected_route") or "unknown")
        predicted = str(row.get("predicted_route") or "unknown")
        source = str(row.get("route_source") or "unknown")
        fallback = bool(row.get("fallback_used"))
        source_counts[source] += 1
        per_route[expected]["total"] += 1

        if predicted == expected:
            correct += 1
            per_route[expected]["correct"] += 1
        elif predicted != "unknown" and not fallback:
            # A safe clarification is tracked separately from a silent wrong Agent.
            misrouted += 1

        if predicted == "unknown" or fallback:
            low_confidence += 1
        if source in {"rule", "rule_override"}:
            rule_direct += 1

    return {
        "case_count": total,
        "route_accuracy": round(correct / total, 4),
        "misroute_rate": round(misrouted / total, 4),
        "low_confidence_rate": round(low_confidence / total, 4),
        "rule_direct_rate": round(rule_direct / total, 4),
        "route_source_counts": dict(sorted(source_counts.items())),
        "per_route": {
            route: {
                "case_count": counts["total"],
                "accuracy": round(counts["correct"] / counts["total"], 4),
            }
            for route, counts in sorted(per_route.items())
        },
    }
