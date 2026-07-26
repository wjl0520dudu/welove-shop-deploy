"""冻结 50 条数据集上的多模态商品检索对比实验（v1～v5）。

独立于旧 ``eval_multimodal_retrieval.py``：只使用人工冻结 relevance_grades，
不调用 LLM-as-Judge；每次输出 JSON + Markdown，便于跨轮实验直接比较。
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.shopping.multimodal_search import (  # noqa: E402
    extract_explicit_product_filters, search_multimodal_v1, search_multimodal_v2,
    search_multimodal_v3, search_multimodal_v4, search_multimodal_v5,
)
from app.infrastructure.config import config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "evals" / "datasets" / "multimodal_retrieval_v1.jsonl"
DEFAULT_REPORT_DIR = ROOT / "evals" / "reports"
ROUTES = {
    "v1_three_path_vlrerank": search_multimodal_v1,
    "v2_four_path_vlrerank": search_multimodal_v2,
    "v3_four_path_weighted": search_multimodal_v3,
    "v4_single_multimodal": search_multimodal_v4,
    "v5_single_multimodal_vlrerank": search_multimodal_v5,
}


def load_dataset(path: Path) -> list[dict[str, Any]]:
    cases = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip() and not raw.startswith("#"):
            item = json.loads(raw)
            if not item.get("query_id") or not item.get("query_image_url") or not item.get("relevance_grades"):
                raise ValueError(f"invalid dataset case: {item.get('query_id')}")
            item["relevance_grades"] = {int(k): int(v) for k, v in item["relevance_grades"].items()}
            cases.append(item)
    return cases


def dcg(gains: list[int]) -> float:
    return sum(g / math.log2(index + 2) for index, g in enumerate(gains))


def metrics(result_ids: list[int], grades: dict[int, int], top_k: int) -> dict[str, float]:
    gains = [grades.get(pid, 0) for pid in result_ids[:top_k]]
    ideal = sorted(grades.values(), reverse=True)
    relevant = {pid for pid, grade in grades.items() if grade >= 2}

    def ndcg_at(k: int) -> float:
        denominator = dcg(ideal[:k])
        return dcg(gains[:k]) / denominator if denominator else 0.0

    def recall_at(k: int) -> float:
        return len(set(result_ids[:k]) & relevant) / len(relevant) if relevant else 0.0

    first = next((i for i, pid in enumerate(result_ids[:top_k], 1) if pid in relevant), None)
    return {
        "ndcg5": ndcg_at(5), "ndcg10": ndcg_at(10),
        "recall5": recall_at(5), "recall10": recall_at(10),
        "mrr": 1.0 / first if first else 0.0,
        "hit1": 1.0 if result_ids and result_ids[0] in relevant else 0.0,
    }


def average(rows: list[dict[str, Any]]) -> dict[str, float]:
    keys = ("ndcg5", "ndcg10", "recall5", "recall10", "mrr", "hit1", "latency_seconds")
    return {key: sum(float(row[key]) for row in rows) / len(rows) if rows else 0.0 for key in keys}


async def run_route(name: str, fn, cases: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    output = []
    for index, case in enumerate(cases, 1):
        started = time.perf_counter()
        error = ""
        try:
            filters = case["retrieval_filters"] if "retrieval_filters" in case else extract_explicit_product_filters(case["query_text"])
            results = await fn(
                case["query_text"], case["query_image_url"], top_k=top_k,
                filters=filters,
            )
        except Exception as exc:  # experiment must continue and record failures
            results, error = [], f"{type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - started
        seen, returned = set(), []
        for item in results:
            pid = int(item.get("product_id") or 0)
            if pid and pid not in seen:
                seen.add(pid)
                returned.append({"product_id": pid, "title": item.get("title", ""), "grade": case["relevance_grades"].get(pid, 0)})
        row = metrics([item["product_id"] for item in returned], case["relevance_grades"], top_k)
        row.update({"query_id": case["query_id"], "latency_seconds": elapsed, "error": error, "results": returned})
        output.append(row)
        print(f"[{name}] {index}/{len(cases)} {case['query_id']} NDCG@5={row['ndcg5']:.3f} {elapsed:.2f}s")
    return output


def markdown(report: dict[str, Any]) -> str:
    lines = ["# 多模态商品检索子链路实验报告", "", f"- 运行时间：{report['run_at']}", f"- Collection：`{report['collection']}`", f"- 数据集：`{report['dataset']}`（{report['case_count']} 条，SHA256 `{report['dataset_sha256'][:16]}`）", f"- top_k：{report['top_k']}；不使用 LLM-as-Judge，完全按冻结人工标注评分。", "", "## 总体指标", "", "| 方案 | NDCG@5 | NDCG@10 | Recall@5 | Recall@10 | MRR | Hit@1 | 平均耗时(s) |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, summary in report["summaries"].items():
        lines.append(f"| {name} | {summary['ndcg5']:.3f} | {summary['ndcg10']:.3f} | {summary['recall5']:.3f} | {summary['recall10']:.3f} | {summary['mrr']:.3f} | {summary['hit1']:.3f} | {summary['latency_seconds']:.2f} |")
    lines.extend(["", "## 结论口径", "", "- 主效果优先看 NDCG@5、Recall@10、MRR；Hit@1 反映首位命中。"])
    routes = set(report["summaries"])
    if {"v4_single_multimodal", "v5_single_multimodal_vlrerank"}.issubset(routes):
        lines.append("- v4 对比 v5 可隔离 VL rerank 的贡献。")
    if {"v1_three_path_vlrerank", "v2_four_path_vlrerank"}.issubset(routes):
        lines.append("- v1 对比 v2 可隔离第四路图文融合召回的贡献。")
    lines.append("- JSON 报告保留逐 query 的返回商品与等级，用于定位回归样本。")
    return "\n".join(lines) + "\n"


async def main_async(args: argparse.Namespace) -> int:
    dataset_path = Path(args.dataset)
    cases = load_dataset(dataset_path)
    if args.limit:
        cases = cases[:args.limit]
    if args.collection:
        config.MILVUS_PRODUCT_V2_COLLECTION = args.collection
    selected_routes = args.routes or list(ROUTES)
    all_rows = {
        name: await run_route(name, ROUTES[name], cases, args.top_k)
        for name in selected_routes
    }
    summaries = {name: average(rows) for name, rows in all_rows.items()}
    raw = dataset_path.read_bytes()
    report = {"run_at": datetime.now(timezone.utc).isoformat(), "dataset": str(dataset_path), "dataset_sha256": hashlib.sha256(raw).hexdigest(), "case_count": len(cases), "top_k": args.top_k, "collection": config.MILVUS_PRODUCT_V2_COLLECTION, "models": {"embedding": config.DASH_SCOPE_MULTI_MODAL_EMBEDDING_MODEL, "rerank": config.DASH_SCOPE_MULTI_MODAL_RERANK_MODEL}, "summaries": summaries, "per_query": all_rows}
    report_dir = Path(args.report_dir); report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"{args.run_name}.json"; md_path = report_dir / f"{args.run_name}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(markdown(report), encoding="utf-8")
    print(f"REPORT_JSON={json_path}"); print(f"REPORT_MD={md_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run frozen multimodal retrieval v1 experiment")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--collection", default="product_mm_eval_v1", help="实验 collection，不改线上 collection")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--run-name", default="multimodal-retrieval-v1")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--routes", nargs="+", choices=list(ROUTES), default=None,
        help="仅运行指定方案；生产三路 collection 应只传 v1_three_path_vlrerank",
    )
    parser.add_argument("--limit", type=int, default=0, help="仅 smoke test 前 N 条")
    raise SystemExit(asyncio.run(main_async(parser.parse_args())))


if __name__ == "__main__":
    main()
