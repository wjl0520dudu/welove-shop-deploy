"""Ingest knowledge documents into knowledge_recursive_v1 using recursive chunking.

This script is the recursive_v1 experiment analogue of ingest_knowledge_v2.py.
It uses build_recursive_chunks_from_text() instead of the fixed
CharacterTextSplitter from document_pipeline.py.

Usage:
    cd ai-service
    python scripts/ingest_recursive_v1.py                    # full run
    python scripts/ingest_recursive_v1.py --collection knowledge_recursive_v1 --dry-run  # dry run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.knowledge.models import ChunkMetadata, DocumentChunk
from app.domain.knowledge.recursive_chunk import build_recursive_chunks_from_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_recursive_v1")

DATASET_ROOT = Path(__file__).resolve().parents[2] / "db" / "data" / "ecommerce_agent_dataset"

CATEGORY_MAP: Dict[str, Tuple[int, str]] = {
    "1_美妆护肤": (1, "beauty"),
    "2_数码电子": (2, "digital"),
    "3_服饰运动": (3, "fashion"),
    "4_食品生活": (4, "food"),
}

# Experiment-fixed recursive chunking parameters
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def _product_id_to_int(pid: str) -> int:
    parts = pid.split("_")
    if len(parts) != 3:
        return 0
    category_prefix = {"beauty": 1, "digital": 2, "clothes": 3, "fashion": 3, "food": 4}.get(parts[1], 0)
    try:
        seq = int(parts[2])
    except ValueError:
        return 0
    return category_prefix * 100000 + seq


def iter_product_files(category_filter: str | None, limit: int | None) -> Iterable[Tuple[Path, int, str]]:
    for dir_name, (cid, label) in CATEGORY_MAP.items():
        if category_filter and category_filter != label:
            continue
        data_dir = DATASET_ROOT / dir_name / "data"
        if not data_dir.exists():
            logger.warning("category 目录不存在：%s", data_dir)
            continue
        files = sorted(data_dir.glob("*.json"))
        if limit:
            files = files[:limit]
        for f in files:
            yield f, cid, label


def build_chunks_for_product(
    product: Dict[str, Any],
    category_id: int,
    doc_id_seed: int,
) -> List[DocumentChunk]:
    """Build recursively-chunked DocumentChunks for a single product's rag_knowledge."""
    product_id = _product_id_to_int(product.get("product_id", ""))
    title = product.get("title", "") or f"商品{product_id}"
    brand = product.get("brand", "")
    sub_category = product.get("sub_category", "")
    header = f"【商品】{title}｜品牌：{brand}｜类目：{sub_category}"

    rag = product.get("rag_knowledge", {}) or {}
    all_chunks: list[DocumentChunk] = []

    def _append(content: str, chunk_type: str) -> None:
        if not content.strip():
            return
        chunks = build_recursive_chunks_from_text(
            text=content,
            doc_id=doc_id_seed,
            title=title,
            doc_type="product_knowledge",
            category_id=category_id,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )
        for c in chunks:
            c.metadata.chunk_type = chunk_type
        all_chunks.extend(chunks)

    # 1) Marketing description — one chunk group
    marketing = (rag.get("marketing_description") or "").strip()
    if marketing:
        _append(f"{header}\n\n[营销描述]\n{marketing}", "marketing")

    # 2) Official FAQ — one chunk per Q&A pair (semantic unit)
    for faq in rag.get("official_faq") or []:
        q = (faq.get("question") or "").strip()
        a = (faq.get("answer") or "").strip()
        if not (q and a):
            continue
        _append(f"{header}\n\n[官方FAQ]\nQ：{q}\nA：{a}", "faq")

    # 3) User reviews — 3 per chunk group
    reviews = rag.get("user_reviews") or []
    for i in range(0, len(reviews), 3):
        batch = reviews[i : i + 3]
        lines = []
        for r in batch:
            nick = r.get("nickname", "匿名")
            rating = r.get("rating", "?")
            content = (r.get("content") or "").strip()
            if content:
                lines.append(f"- {nick}（{rating}星）：{content}")
        if lines:
            _append(f"{header}\n\n[用户评价 #{i // 3 + 1}]\n" + "\n".join(lines), "review")

    return all_chunks


def ingest_to_collection(collection_name: str, category_filter: str | None, limit: int | None, dry_run: bool = False) -> dict:
    """Ingest all product knowledge into the specified Milvus collection."""
    from app.infrastructure.vectorstores.knowledge.vector_store import MilvusVectorStore

    vector_store = MilvusVectorStore(collection_name=collection_name)
    logger.info("[OK] 向量库就绪：%s", vector_store.stats())

    total_products = 0
    total_chunks = 0
    per_category: dict[str, int] = {}
    doc_stats: List[dict] = []

    for json_path, category_id, category_label in iter_product_files(category_filter, limit):
        try:
            product = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("跳过 %s：解析失败 %s", json_path.name, e)
            continue

        product_id_int = _product_id_to_int(product.get("product_id", ""))
        if not product_id_int:
            logger.warning("跳过 %s：无法解析 product_id", json_path.name)
            continue

        chunks = build_chunks_for_product(product, category_id=category_id, doc_id_seed=product_id_int)
        if not chunks:
            logger.info("跳过 %s：无 rag_knowledge", json_path.name)
            continue

        if not dry_run:
            try:
                vector_store.upsert_chunks(chunks)
            except Exception:
                logger.exception("灌入失败：%s", json_path.name)
                continue

        total_products += 1
        total_chunks += len(chunks)
        per_category[category_label] = per_category.get(category_label, 0) + 1

        # Collect per-doc stats
        chunk_lengths = [len(c.content) for c in chunks]
        doc_stats.append({
            "doc_id": product_id_int,
            "product_id": product.get("product_id", ""),
            "title": product.get("title", "")[:40],
            "chunks_count": len(chunks),
            "inserted_count": len(chunks) if not dry_run else 0,
            "avg_chunk_len": round(sum(chunk_lengths) / len(chunk_lengths), 1) if chunk_lengths else 0,
            "max_chunk_len": max(chunk_lengths) if chunk_lengths else 0,
            "min_chunk_len": min(chunk_lengths) if chunk_lengths else 0,
        })
        logger.info("  [%04d] %s — %d chunks (avg=%.0f, max=%d)",
                    total_products, product.get("product_id", ""), len(chunks),
                    doc_stats[-1]["avg_chunk_len"], doc_stats[-1]["max_chunk_len"])

    return {
        "collection": collection_name,
        "total_products": total_products,
        "total_chunks": total_chunks,
        "per_category": per_category,
        "doc_stats": doc_stats,
    }


def main():
    parser = argparse.ArgumentParser(description="递归分块灌入商品知识到 Milvus（knowledge_recursive_v1）")
    parser.add_argument("--collection", default="knowledge_recursive_v1",
                        help="Milvus collection 名（默认 knowledge_recursive_v1）")
    parser.add_argument("--category", choices=["beauty", "digital", "fashion", "food"], default=None,
                        help="只灌某个类目；不填=全量")
    parser.add_argument("--limit", type=int, default=None,
                        help="每个类目最多灌多少商品（冒烟测试用）")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅生成分块统计，不写入 Milvus")
    args = parser.parse_args()

    print("=" * 60)
    print("递归分块灌入 (recursive_v1)")
    print(f"  Collection : {args.collection}")
    print(f"  类目过滤   : {args.category or '全量'}")
    print(f"  每类限制   : {args.limit or '不限'}")
    print(f"  干跑       : {args.dry_run}")
    print(f"  Chunk size : {CHUNK_SIZE} / overlap: {CHUNK_OVERLAP}")
    print("=" * 60)

    result = ingest_to_collection(
        collection_name=args.collection,
        category_filter=args.category,
        limit=args.limit,
        dry_run=args.dry_run,
    )

    print()
    print("=" * 60)
    print(f"[DONE] 灌入完成{'（干跑）' if args.dry_run else ''}")
    print(f"  商品数    : {result['total_products']}")
    print(f"  分块数    : {result['total_chunks']}")
    for cat, n in result["per_category"].items():
        print(f"    {cat}: {n} 个商品")

    # Print import manifest
    if result["doc_stats"]:
        print()
    print("导入清单:")
    print(f"  {'doc_id':>10}  {'商品ID':>20}  {'title':>35}  {'chunks':>6}  {'插入':>6}  {'avg_len':>7}  {'max_len':>7}")
    for ds in result["doc_stats"]:
        print(f"  {ds['doc_id']:>10}  {ds['product_id']:>20}  {ds['title'][:35]:>35}  "
              f"{ds['chunks_count']:>6}  {ds['inserted_count']:>6}  "
              f"{ds['avg_chunk_len']:>7.1f}  {ds['max_chunk_len']:>7}")

    print("=" * 60)
    return result


if __name__ == "__main__":
    main()
