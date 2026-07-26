"""Resume Agent Golden Dataset evaluations from an existing JSON report.

This is intentionally case-oriented rather than process-oriented:

* ``--mode failed`` reruns only cases whose Contract or main response failed.
* ``--mode ragas`` scores only cases with a saved answer and raw contexts but
  no successful RAGAS result. The AssistantGraph is not executed in this mode.

The resulting report keeps the original case order and recomputes all summary
sections from the merged rows.

Examples (from ``ai-service``)::

    python scripts/resume_agent_eval.py \
      --report evals/reports/agent-v2.1-rerun-20260725.json \
      --mode failed \
      --dataset evals/datasets/agent_golden_cases.jsonl \
      --timeout-seconds 90 \
      --ragas \
      --output evals/reports/agent-v2.1-resumed.json \
      --markdown-output evals/reports/agent-v2.1-resumed.md

    python scripts/resume_agent_eval.py \
      --report evals/reports/agent-v2.1-partial.json \
      --mode ragas \
      --dataset evals/datasets/agent_golden_cases.jsonl \
      --output evals/reports/agent-v2.1-ragas-resumed.json
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from evals.agent_metrics import calculate_agent_metrics
from evals.retrieval_metrics import summarize_retrieval_rows
from evals.run_agent_eval import (
    _build_metadata,
    _summarize_judge,
    _summarize_ragas,
    collect_direct_results,
    collect_http_results,
    evaluate,
    load_jsonl,
    render_markdown,
)


def load_report(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取报告 {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("cases"), list):
        raise ValueError(f"报告缺少 cases 数组: {path}")
    return value


def _response(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("response")
    return value if isinstance(value, dict) else {}


def _is_failed_row(row: dict[str, Any]) -> bool:
    response = _response(row)
    contract = row.get("contract") or {}
    return (
        contract.get("passed") is False
        or bool(response.get("error"))
        or bool(response.get("error_code"))
    )


def _has_saved_ragas_context(row: dict[str, Any]) -> bool:
    response = _response(row)
    contexts = response.get("retrieved_contexts")
    return (
        response.get("task_type") == "knowledge"
        and not response.get("error")
        and isinstance(contexts, list)
        and any(str(item).strip() for item in contexts)
    )


def _needs_ragas(row: dict[str, Any]) -> bool:
    if not _has_saved_ragas_context(row):
        return False
    ragas = row.get("ragas") or {}
    return ragas.get("enabled") is not True or bool(ragas.get("error"))


def select_case_ids(
    report: dict[str, Any],
    mode: str,
    explicit_case_ids: list[str] | None = None,
) -> list[str]:
    """Select IDs in report order, making selection independently testable."""
    rows = [row for row in report.get("cases") or [] if isinstance(row, dict)]
    by_id = {str(row.get("id")): row for row in rows if row.get("id") is not None}
    if explicit_case_ids:
        missing = [case_id for case_id in explicit_case_ids if case_id not in by_id]
        if missing:
            raise ValueError(f"报告中不存在这些 case ID: {', '.join(missing)}")
        selected = []
        for case_id in (str(item) for item in explicit_case_ids):
            row = by_id[case_id]
            if mode == "ragas" and not _needs_ragas(row):
                raise ValueError(
                    f"case {case_id} has no unfinished RAGAS record with saved retrieved_contexts"
                )
            if case_id not in selected:
                selected.append(case_id)
        return [str(row.get("id")) for row in rows if str(row.get("id")) in selected]

    predicate = _is_failed_row if mode == "failed" else _needs_ragas
    return [str(row.get("id")) for row in rows if row.get("id") is not None and predicate(row)]


def _row_observation(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a report row back to the recorded-result shape used by evaluate."""
    return {
        "id": row.get("id"),
        "response": copy.deepcopy(_response(row)),
        "latency_ms": row.get("latency_ms"),
        "ttft_ms": row.get("ttft_ms"),
        "sse_events": copy.deepcopy(row.get("sse_events") or []),
    }


def _merge_rows(
    original_rows: list[dict[str, Any]],
    updates: dict[str, dict[str, Any]],
    *,
    mode: str,
    ragas_requested: bool = False,
    deepeval_requested: bool = False,
) -> list[dict[str, Any]]:
    merged_rows: list[dict[str, Any]] = []
    for original in original_rows:
        case_id = str(original.get("id"))
        update = updates.get(case_id)
        if update is None:
            merged_rows.append(copy.deepcopy(original))
            continue

        if mode == "ragas":
            merged = copy.deepcopy(original)
            merged["ragas"] = copy.deepcopy(update.get("ragas") or {"enabled": False})
        else:
            merged = {**copy.deepcopy(original), **copy.deepcopy(update)}
            # A failed-mode resume only reruns the requested judging steps.
            # Preserve already recorded judge/RAGAS data when those steps were
            # not requested, instead of silently replacing it with disabled.
            if not ragas_requested and "ragas" in original:
                merged["ragas"] = copy.deepcopy(original["ragas"])
            if not deepeval_requested and "judge" in original:
                merged["judge"] = copy.deepcopy(original["judge"])
        merged_rows.append(merged)
    return merged_rows


def build_merged_report(
    source_report: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    source_path: Path,
    dataset: Path,
    mode: str,
    selected_case_ids: list[str],
) -> dict[str, Any]:
    """Recalculate report-level sections after case-level replacement."""
    report = copy.deepcopy(source_report)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    metadata = _build_metadata()
    metadata["dataset"] = str(dataset)
    try:
        from evals.run_agent_eval import _file_hash

        metadata["dataset_fingerprint"] = _file_hash(dataset)
    except (ImportError, OSError):
        metadata["dataset_fingerprint"] = source_report.get("metadata", {}).get("dataset_fingerprint")
    metadata["execution_mode"] = f"resume:{mode}"
    metadata["resume"] = {
        "source_report": str(source_path),
        "mode": mode,
        "rerun_case_ids": selected_case_ids,
        "rerun_case_count": len(selected_case_ids),
    }
    report["metadata"] = metadata
    report["cases"] = rows
    report["metrics"] = calculate_agent_metrics(rows)
    report["failures"] = [
        row for row in rows
        if not (row.get("contract") or {}).get("passed")
        or (row.get("judge") or {}).get("passed") is False
    ]
    report["evaluation_errors"] = [
        {
            "id": row.get("id"),
            "judge": next(
                (
                    f"{key}:{value.get('error')}"
                    for key, value in (row.get("judge") or {}).get("metrics", {}).items()
                    if isinstance(value, dict) and value.get("error")
                ),
                None,
            ),
            "ragas": (row.get("ragas") or {}).get("error"),
        }
        for row in rows
        if any(
            isinstance(value, dict) and value.get("error")
            for value in (row.get("judge") or {}).get("metrics", {}).values()
        )
        or (row.get("ragas") or {}).get("error")
    ]
    report["ragas_summary"] = _summarize_ragas(rows)
    report["judge_summary"] = _summarize_judge(rows)
    report["retrieval_summary"] = summarize_retrieval_rows(
        [row.get("retrieval") or {} for row in rows], k=5,
    )
    # A comparison embedded in the source report describes the source rows,
    # so retaining it after a partial merge would be misleading.
    report.pop("comparison", None)
    return report


def _write_outputs(report: dict[str, Any], output: Path, markdown_output: Path | None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if markdown_output:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(report), encoding="utf-8")


def _default_output(report_path: Path) -> Path:
    return report_path.with_name(f"{report_path.stem}-resumed{report_path.suffix or '.json'}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resume selected Agent Golden Dataset cases")
    parser.add_argument("--report", type=Path, required=True, help="Existing JSON report")
    parser.add_argument("--mode", choices=("failed", "ragas"), required=True)
    parser.add_argument("--dataset", type=Path, default=AI_SERVICE_ROOT / "evals/datasets/agent_golden_cases.jsonl")
    parser.add_argument("--case-id", action="append", help="Override automatic selection; repeatable")
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    exec_group = parser.add_mutually_exclusive_group()
    exec_group.add_argument("--direct", action="store_true", help="Run AssistantGraph in-process (default)")
    exec_group.add_argument("--base-url", help="Use HTTP execution instead of direct mode for failed cases")
    parser.add_argument("--ragas", action="store_true", help="Also run RAGAS for newly successful failed cases")
    parser.add_argument("--deepeval", action="store_true", help="Also rerun DeepEval for selected failed cases")
    parser.add_argument("--judge-threshold", type=float, default=0.6)
    parser.add_argument("--judge-cache", type=Path, default=Path("evals/reports/judge-cache.local.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    return parser.parse_args()


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    args = _parse_args()
    if args.mode == "ragas" and (args.base_url or args.ragas or args.deepeval):
        raise SystemExit("--mode ragas 只补 RAGAS，不需要 --base-url/--ragas/--deepeval")

    report = load_report(args.report)
    dataset_cases = load_jsonl(args.dataset)
    dataset_by_id = {str(case["id"]): case for case in dataset_cases}
    selected_ids = select_case_ids(report, args.mode, args.case_id)
    missing_dataset = [case_id for case_id in selected_ids if case_id not in dataset_by_id]
    if missing_dataset:
        raise SystemExit(f"数据集缺少这些 case ID: {', '.join(missing_dataset)}")

    print(f"[resume] mode={args.mode} selected={len(selected_ids)} case(s)")
    if selected_ids:
        print(f"[resume] case_ids: {', '.join(selected_ids)}")

    updates: dict[str, dict[str, Any]] = {}
    if selected_ids and args.mode == "failed":
        cases = [dataset_by_id[case_id] for case_id in selected_ids]
        timeout = max(1.0, args.timeout_seconds)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        if args.base_url:
            observations = loop.run_until_complete(
                collect_http_results(cases, args.base_url, timeout),
            )
        else:
            # Keep the loop alive until process exit, matching run_agent_eval.
            # httpx cleanup callbacks may still reference this loop on Windows.
            observations = loop.run_until_complete(collect_direct_results(cases, timeout))
        from evals.run_agent_eval import load_judge_cache, save_judge_cache

        judge_cache = load_judge_cache(args.judge_cache) if args.deepeval else None
        judged = evaluate(
            cases,
            observations,
            deepeval_enabled=args.deepeval,
            ragas_enabled=args.ragas,
            judge_threshold=args.judge_threshold,
            judge_cache=judge_cache,
        )
        if judge_cache is not None:
            save_judge_cache(args.judge_cache, judge_cache)
        updates = {str(row["id"]): row for row in judged["cases"]}
    elif selected_ids and args.mode == "ragas":
        report_rows = {str(row["id"]): row for row in report["cases"]}
        cases = [dataset_by_id[case_id] for case_id in selected_ids]
        observations = {
            case_id: _row_observation(report_rows[case_id])
            for case_id in selected_ids
        }
        judged = evaluate(cases, observations, ragas_enabled=True)
        updates = {str(row["id"]): row for row in judged["cases"]}

    rows = _merge_rows(
        [row for row in report["cases"] if isinstance(row, dict)],
        updates,
        mode=args.mode,
        ragas_requested=args.ragas or args.mode == "ragas",
        deepeval_requested=args.deepeval,
    )
    output = args.output or _default_output(args.report)
    markdown_output = args.markdown_output
    if markdown_output is None:
        markdown_output = output.with_suffix(".md")
    merged = build_merged_report(
        report,
        rows,
        source_path=args.report,
        dataset=args.dataset,
        mode=args.mode,
        selected_case_ids=selected_ids,
    )
    _write_outputs(merged, output, markdown_output)
    print(f"[resume] wrote {output}")
    if selected_ids:
        print(f"[resume] completed {len(updates)}/{len(selected_ids)} selected case(s)")
    else:
        print("[resume] 没有需要补跑的 case，已输出原报告的完整合并副本")


if __name__ == "__main__":
    main()
