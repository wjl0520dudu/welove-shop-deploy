"""多模态检索评测：四个接口对比。

对比对象：
  ① search_multimodal_v1  三路 + RRF + qwen3-vl-rerank
  ② search_multimodal_v2  四路 + RRF + qwen3-vl-rerank
  ③ search_multimodal_v3  四路 + RRF + WeightedRanker
  ④ search_multimodal_v4  单路 multimodal_vector（无 RRF 无 rerank）

指标：NDCG@5 / NDCG@10 / Recall@5 / Recall@10 / MRR / Hit@1

流程：
  1. 读 tests/fixtures/mock_multimodal_queries.jsonl
  2. 对每条 query 跑 3 个接口，各取 top 10
  3. LLM-as-Judge 对每个 (query, product) pair 打分 0-3
     - source_product_id 命中直接给 3 分（金标）
     - 其他商品交给 LLM 判断
     - 打分结果落盘缓存，避免重复调用 LLM
  4. 计算指标 → 输出对比表
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.llm import get_llm                                # noqa: E402
from shopping.multimodal_search import (                    # noqa: E402
    search_multimodal_v1,
    search_multimodal_v2,
    search_multimodal_v3,
    search_multimodal_v4,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("eval_multimodal")

DEFAULT_QUERIES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "mock_multimodal_queries.jsonl"
DEFAULT_CACHE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "eval_judge_cache.json"
DEFAULT_REPORT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "eval_report.md"


INTERFACES = {
    "v1_three_path_vlrerank": search_multimodal_v1,
    "v2_four_path_vlrerank": search_multimodal_v2,
    "v3_four_path_weighted": search_multimodal_v3,
    "v4_single_multimodal": search_multimodal_v4,
}


JUDGE_PROMPT = """你是电商检索相关性评估专家，需要判断一个召回商品对用户查询的相关性。

## 用户查询
{query_text}

## 召回商品
- 标题：{title}
- 品牌：{brand}
- 品类：{category} / {sub_category}
- 标签：{tags}
- 描述：{description}
- 价格：{base_price}

## 打分标准（0-3 分）
- **3 分**：高度相关，几乎完美匹配用户需求（同品类 + 核心卖点或场景对得上）
- **2 分**：相关，品类对，但有小差异（品牌/价格/风格不完全匹配）
- **1 分**：勉强相关（大类相似但核心需求对不上，比如都属"防晒"但用户要防晒霜给了防晒衣）
- **0 分**：不相关（完全不同品类或明显不匹配）

## 输出
只输出一个 JSON 对象：{{"score": <整数 0-3>, "reason": "<20 字以内简短理由>"}}
不要输出其他内容。
"""


# ─────────────────── 数据加载 ───────────────────

def load_queries(path: Path) -> List[Dict[str, Any]]:
    queries = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))
    return queries


def load_judge_cache(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_judge_cache(cache: Dict[str, Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ─────────────────── LLM Judge ───────────────────

def _judge_cache_key(query_text: str, product_id: int) -> str:
    """打分缓存 key：query 全文 + product_id（同 query 同商品复用打分）。"""
    return f"{query_text} || {product_id}"


async def judge_relevance(
    llm,
    query_text: str,
    product: Dict[str, Any],
    cache: Dict[str, Dict[str, Any]],
    *,
    source_product_id: Optional[int],
) -> int:
    """给召回商品打分，命中金标直接 3 分。"""
    pid = int(product.get("product_id") or 0)

    # 金标商品：直接 3 分
    if source_product_id is not None and pid == source_product_id:
        return 3

    key = _judge_cache_key(query_text, pid)
    if key in cache:
        return int(cache[key]["score"])

    prompt = JUDGE_PROMPT.format(
        query_text=query_text,
        title=product.get("title") or "",
        brand=product.get("brand") or "",
        category=product.get("category") or "",
        sub_category=product.get("sub_category") or "",
        tags=product.get("tags") or "",
        description=(product.get("description") or "")[:300],
        base_price=product.get("base_price") or product.get("price") or "未知",
    )

    try:
        resp = await llm.ainvoke(prompt)
        text = str(resp.content or "").strip()
        # 剥可能的代码块围栏
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
            text = text.strip()
        data = json.loads(text)
        score = int(data.get("score", 0))
        score = max(0, min(3, score))
        cache[key] = {"score": score, "reason": data.get("reason", "")}
        return score
    except Exception as e:  # noqa: BLE001
        logger.warning("judge 失败，默认 0：query=%r pid=%d err=%s", query_text, pid, e)
        cache[key] = {"score": 0, "reason": f"judge_error: {e}"}
        return 0


# ─────────────────── 指标计算 ───────────────────

def _dcg(scores: List[int]) -> float:
    return sum(s / math.log2(i + 2) for i, s in enumerate(scores))


def ndcg_at_k(gains: List[int], k: int) -> float:
    """NDCG@k：gain 用 0-3 的相关性分数。"""
    if not gains:
        return 0.0
    k = min(k, len(gains))
    dcg = _dcg(gains[:k])
    ideal = _dcg(sorted(gains, reverse=True)[:k])
    return dcg / ideal if ideal > 0 else 0.0


def recall_at_k(gains: List[int], total_relevant: int, k: int) -> float:
    """Recall@k：只算相关（score >= 2）的召回。"""
    if total_relevant <= 0:
        return 0.0
    hit = sum(1 for s in gains[:k] if s >= 2)
    return hit / total_relevant


def mrr(gains: List[int], threshold: int = 2) -> float:
    """MRR：第一个 score >= threshold 的位置的倒数。"""
    for i, s in enumerate(gains):
        if s >= threshold:
            return 1.0 / (i + 1)
    return 0.0


def hit_at_1(gains: List[int], threshold: int = 2) -> float:
    """Hit@1：第一位是不是相关（score >= threshold）。"""
    return 1.0 if gains and gains[0] >= threshold else 0.0


# ─────────────────── 主评测 ───────────────────

async def eval_query_on_interface(
    interface_fn,
    query: Dict[str, Any],
    llm,
    cache: Dict[str, Dict[str, Any]],
    *,
    top_k: int,
    total_relevant_hint: int,
) -> Dict[str, Any]:
    """跑一次接口 + LLM 打分 + 算单条 query 指标。"""
    t0 = time.perf_counter()
    try:
        results = await interface_fn(
            query["query_text"],
            query["query_image_url"],
            top_k=top_k,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("接口调用失败 query=%s err=%s", query["query_id"], e)
        results = []
    dt = time.perf_counter() - t0

    # LLM 打分
    gains: List[int] = []
    judged_items: List[Dict[str, Any]] = []
    for r in results:
        score = await judge_relevance(
            llm, query["query_text"], r, cache,
            source_product_id=query.get("source_product_id"),
        )
        gains.append(score)
        judged_items.append({
            "product_id": int(r.get("product_id") or 0),
            "title": r.get("title") or "",
            "score": score,
        })

    # total_relevant：用当前召回结果里 score>=2 的作为分母下限
    # （无金标数据，只能这么估算 —— 三个接口结果拼在一起后重新算）
    return {
        "query_id": query["query_id"],
        "gains": gains,
        "judged": judged_items,
        "elapsed": dt,
    }


def summarize_interface(
    per_query: List[Dict[str, Any]],
    total_relevant_map: Dict[str, int],
) -> Dict[str, float]:
    """汇总一个接口在所有 query 上的指标平均。"""
    if not per_query:
        return {k: 0.0 for k in ("ndcg5", "ndcg10", "recall5", "recall10", "mrr", "hit1", "avg_latency")}

    ndcg5s, ndcg10s, recall5s, recall10s, mrrs, hit1s, lats = [], [], [], [], [], [], []
    for row in per_query:
        gains = row["gains"]
        tot = total_relevant_map.get(row["query_id"], sum(1 for g in gains if g >= 2))
        ndcg5s.append(ndcg_at_k(gains, 5))
        ndcg10s.append(ndcg_at_k(gains, 10))
        recall5s.append(recall_at_k(gains, tot, 5))
        recall10s.append(recall_at_k(gains, tot, 10))
        mrrs.append(mrr(gains))
        hit1s.append(hit_at_1(gains))
        lats.append(row["elapsed"])

    def _avg(xs): return sum(xs) / len(xs) if xs else 0.0

    return {
        "ndcg5": _avg(ndcg5s),
        "ndcg10": _avg(ndcg10s),
        "recall5": _avg(recall5s),
        "recall10": _avg(recall10s),
        "mrr": _avg(mrrs),
        "hit1": _avg(hit1s),
        "avg_latency": _avg(lats),
    }


def _format_report(
    interface_results: Dict[str, List[Dict[str, Any]]],
    summaries: Dict[str, Dict[str, float]],
    total_queries: int,
) -> str:
    lines = []
    lines.append(f"# 多模态检索评测结果\n")
    lines.append(f"- 查询数：{total_queries}")
    lines.append(f"- 接口数：{len(interface_results)}")
    lines.append(f"- 每个查询 top_k = 10\n")

    lines.append("## 指标对比\n")
    lines.append("| 接口 | NDCG@5 | NDCG@10 | Recall@5 | Recall@10 | MRR | Hit@1 | 平均耗时(s) |")
    lines.append("|------|--------|---------|----------|-----------|-----|-------|------------|")
    for name, s in summaries.items():
        lines.append(
            f"| {name} | {s['ndcg5']:.3f} | {s['ndcg10']:.3f} | "
            f"{s['recall5']:.3f} | {s['recall10']:.3f} | {s['mrr']:.3f} | "
            f"{s['hit1']:.3f} | {s['avg_latency']:.2f} |"
        )

    # 找每列最优
    lines.append("\n## 各指标最优接口\n")
    for metric in ("ndcg5", "ndcg10", "recall5", "recall10", "mrr", "hit1"):
        best = max(summaries.items(), key=lambda kv: kv[1][metric])
        lines.append(f"- **{metric}**：{best[0]}（{best[1][metric]:.3f}）")

    # 详细样例（前 3 条）
    lines.append("\n## 部分样例（前 3 条 query）\n")
    sample_query_ids = list(next(iter(interface_results.values())))[:3]
    sample_query_ids = [row["query_id"] for row in list(next(iter(interface_results.values())))[:3]]
    for qid in sample_query_ids:
        lines.append(f"\n### {qid}\n")
        for name, results in interface_results.items():
            row = next((r for r in results if r["query_id"] == qid), None)
            if row is None:
                continue
            lines.append(f"**{name}**：gains={row['gains']}")
            for item in row["judged"][:5]:
                lines.append(f"  - [{item['score']}] pid={item['product_id']} {item['title'][:40]}")

    return "\n".join(lines)


async def main_async(args) -> int:
    queries_path = Path(args.queries)
    if not queries_path.exists():
        logger.error("查询文件不存在：%s，先跑 scripts/gen_mock_multimodal_queries.py 生成", queries_path)
        return 2

    queries = load_queries(queries_path)
    if args.limit and args.limit > 0:
        queries = queries[:args.limit]
    logger.info("加载 %d 条 mock 查询", len(queries))

    llm = get_llm()
    if llm is None:
        logger.error("LLM 未配置，无法评测")
        return 2

    cache_path = Path(args.cache)
    cache = load_judge_cache(cache_path)
    logger.info("加载 judge 缓存 %d 条", len(cache))

    interface_results: Dict[str, List[Dict[str, Any]]] = {name: [] for name in INTERFACES}
    per_query_gains: Dict[str, List[int]] = defaultdict(list)  # 用于估 total_relevant

    for interface_name, fn in INTERFACES.items():
        logger.info("======== 开始跑接口 %s ========", interface_name)
        for i, query in enumerate(queries, start=1):
            row = await eval_query_on_interface(
                fn, query, llm, cache,
                top_k=args.top_k,
                total_relevant_hint=0,
            )
            interface_results[interface_name].append(row)
            per_query_gains[query["query_id"]].extend(row["gains"])
            logger.info(
                "[%s] %d/%d query=%s gains=%s (%.2fs)",
                interface_name, i, len(queries),
                query["query_id"], row["gains"][:5], row["elapsed"],
            )
            # 每 5 条落一次缓存
            if i % 5 == 0:
                save_judge_cache(cache, cache_path)

    # 落盘缓存
    save_judge_cache(cache, cache_path)

    # 估 total_relevant：把所有接口召回的 score>=2 商品数当分母
    total_relevant_map: Dict[str, int] = {}
    for qid, all_gains in per_query_gains.items():
        # 用不同接口召回并集里 score>=2 的个数
        total_relevant_map[qid] = sum(1 for g in all_gains if g >= 2)
        # 保证 >= 1，否则 Recall 全是 0
        if total_relevant_map[qid] == 0:
            total_relevant_map[qid] = 1

    summaries = {
        name: summarize_interface(rows, total_relevant_map)
        for name, rows in interface_results.items()
    }

    # 打印表
    logger.info("\n" + "=" * 100)
    logger.info("评测汇总（top_k=%d, queries=%d）", args.top_k, len(queries))
    logger.info("=" * 100)
    header = f"{'接口':<28} {'NDCG@5':>7} {'NDCG@10':>8} {'Recall@5':>9} {'Recall@10':>10} {'MRR':>6} {'Hit@1':>7} {'耗时(s)':>8}"
    logger.info(header)
    for name, s in summaries.items():
        logger.info(
            f"{name:<28} {s['ndcg5']:>7.3f} {s['ndcg10']:>8.3f} "
            f"{s['recall5']:>9.3f} {s['recall10']:>10.3f} "
            f"{s['mrr']:>6.3f} {s['hit1']:>7.3f} {s['avg_latency']:>8.2f}"
        )

    # 保存 markdown 报告
    report = _format_report(interface_results, summaries, len(queries))
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    logger.info("详细报告 → %s", report_path)

    return 0


def main():
    parser = argparse.ArgumentParser(description="多模态检索三接口对比评测")
    parser.add_argument("--queries", type=str, default=str(DEFAULT_QUERIES),
                        help=f"mock 查询 jsonl 路径（默认 {DEFAULT_QUERIES}）")
    parser.add_argument("--cache", type=str, default=str(DEFAULT_CACHE),
                        help=f"LLM judge 缓存 json 路径（默认 {DEFAULT_CACHE}）")
    parser.add_argument("--report", type=str, default=str(DEFAULT_REPORT),
                        help=f"评测报告 markdown 路径（默认 {DEFAULT_REPORT}）")
    parser.add_argument("--top-k", type=int, default=10, help="每个接口取 top_k（默认 10）")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条 query（0=全部）")
    args = parser.parse_args()

    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
