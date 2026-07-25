"""Ingest product knowledge into the knowledge Milvus collection.

Each product is assembled into one knowledge document before splitting. The
splitter uses fixed 500-character chunks with 50 characters of overlap.

Examples (the write commands require cloud settings in ``ai-service/.env``):

    cd ai-service
    python scripts/ingest_product_knowledge_fixed.py --dry-run --limit 1
    python scripts/ingest_product_knowledge_fixed.py --replace
    python scripts/ingest_product_knowledge_fixed.py --category beauty --replace

The script only targets the knowledge collection. It does not write to the
product catalog collections used by ShoppingAgent.

By default the target is ``knowledge_v21_fixed``. ``MILVUS_PRODUCT_COLLECTION``
is deliberately rejected because that collection stores one row per product,
not knowledge chunks.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

# Allow running this file directly from the ai-service directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.knowledge.document_pipeline import hash_content, split_text  # noqa: E402
from app.domain.knowledge.models import ChunkMetadata, DocumentChunk  # noqa: E402
from app.infrastructure.config import config  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_product_knowledge_fixed")

DATASET_ROOT = Path(__file__).resolve().parents[2] / "db" / "data" / "ecommerce_agent_dataset"

# Keep the same numeric IDs as ingest_knowledge_v2.py. Directory names are
# discovered by numeric prefix so this file remains robust to console encoding.
CATEGORY_MAP = {
    "beauty": (1, "beauty"),
    "digital": (2, "digital"),
    "fashion": (3, "fashion"),
    "food": (4, "food"),
}

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
DOC_TYPE = "product_knowledge"
TARGET_COLLECTION = "knowledge_v21_fixed"


def iter_product_files(
    category_filter: str | None,
    limit: int | None,
) -> Iterable[tuple[Path, int, str]]:
    """Yield product JSON files and their stable category metadata."""
    for category, (category_id, category_label) in CATEGORY_MAP.items():
        if category_filter and category_filter != category:
            continue

        category_dirs = sorted(
            path
            for path in DATASET_ROOT.glob(f"{category_id}_*")
            if path.is_dir()
        )
        if not category_dirs:
            logger.warning("category directory not found: %s_*", category_id)
            continue

        data_dir = category_dirs[0] / "data"
        if not data_dir.exists():
            logger.warning("product data directory not found: %s", data_dir)
            continue

        files = sorted(data_dir.glob("*.json"))
        if limit is not None:
            files = files[:limit]
        for path in files:
            yield path, category_id, category_label


def product_id_to_int(product_id: str) -> int:
    """Map dataset IDs such as ``p_beauty_001`` to stable INT64 IDs."""
    parts = product_id.split("_")
    if len(parts) != 3:
        return 0

    category_prefix = {
        "beauty": 1,
        "digital": 2,
        "clothes": 3,
        "fashion": 3,
        "food": 4,
    }.get(parts[1], 0)
    try:
        sequence = int(parts[2])
    except ValueError:
        return 0
    return category_prefix * 100000 + sequence


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_product_text(product: dict[str, Any]) -> str:
    """Build the same product knowledge sections used by ingest_knowledge_v2."""
    product_id = _text(product.get("product_id"))
    title = _text(product.get("title")) or product_id or "Product knowledge"
    brand = _text(product.get("brand"))
    sub_category = _text(product.get("sub_category"))

    header = (
        f"Product: {title}\n"
        f"Brand: {brand}\n"
        f"Sub-category: {sub_category}"
    )
    sections: list[str] = []
    rag = product.get("rag_knowledge") or {}

    marketing = _text(rag.get("marketing_description")) if isinstance(rag, dict) else ""
    if marketing:
        sections.append(f"{header}\n\n[Marketing description]\n{marketing}")

    faq_lines: list[str] = []
    faq_items = rag.get("official_faq") if isinstance(rag, dict) else []
    for faq in faq_items or []:
        if not isinstance(faq, dict):
            continue
        question = _text(faq.get("question"))
        answer = _text(faq.get("answer"))
        if question and answer:
            faq_lines.append(f"Q: {question}\nA: {answer}")
    for faq in faq_lines:
        sections.append(f"{header}\n\n[Official FAQ]\n{faq}")

    review_lines: list[str] = []
    review_items = rag.get("user_reviews") if isinstance(rag, dict) else []
    for review in review_items or []:
        if isinstance(review, dict):
            nickname = _text(review.get("nickname")) or "Anonymous"
            rating = _text(review.get("rating")) or "?"
            content = _text(review.get("content"))
            if content:
                review_lines.append(f"- {nickname} ({rating}/5): {content}")
        elif _text(review):
            review_lines.append("- " + _text(review))
    for index in range(0, len(review_lines), 3):
        batch = review_lines[index : index + 3]
        sections.append(
            f"{header}\n\n[User reviews #{index // 3 + 1}]\n" + "\n".join(batch)
        )

    return "\n\n".join(sections)


def build_chunks_for_product(
    product: dict[str, Any],
    category_id: int,
) -> list[DocumentChunk]:
    """Build fixed-size chunks and attach metadata used by the RAG store."""
    raw_product_id = _text(product.get("product_id"))
    product_id = product_id_to_int(raw_product_id)
    if not product_id:
        return []

    title = _text(product.get("title")) or raw_product_id
    parts = split_text(
        build_product_text(product),
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    total_chunks = len(parts)
    return [
        DocumentChunk(
            content=content,
            metadata=ChunkMetadata(
                doc_id=product_id,
                product_id=product_id,
                category_id=category_id,
                source=raw_product_id,
                title=title,
                doc_type=DOC_TYPE,
                chunk_type="text",
                chunk_index=index,
                total_chunks=total_chunks,
                content_hash=hash_content(content),
            ),
        )
        for index, content in enumerate(parts)
    ]


def ingest(
    collection_name: str,
    category_filter: str | None,
    limit: int | None,
    dry_run: bool,
    replace: bool,
) -> dict[str, Any]:
    """Build and optionally write all selected product documents."""
    if collection_name == config.MILVUS_PRODUCT_COLLECTION:
        raise RuntimeError(
            f"{collection_name} is the product information collection; "
            f"use the knowledge collection {TARGET_COLLECTION} instead"
        )

    store = None
    if not dry_run:
        if not config.MILVUS_URL.lower().startswith("https://"):
            raise RuntimeError(
                "cloud import requires MILVUS_URL to start with https://"
            )
        if not config.MILVUS_TOKEN:
            raise RuntimeError(
                "cloud import requires MILVUS_TOKEN in ai-service/.env"
            )
        if config.RAG_PARENT_CHILD_ENABLED:
            raise RuntimeError(
                "RAG_PARENT_CHILD_ENABLED=true targets parent-child chunks; "
                "use a legacy fixed-chunk collection or disable the flag before importing"
            )
        from app.infrastructure.vectorstores.knowledge.vector_store import MilvusVectorStore

        store = MilvusVectorStore(collection_name=collection_name)

    totals: Counter[str] = Counter()
    lengths: list[int] = []
    product_count = 0
    skipped_count = 0
    failed_count = 0

    for json_path, category_id, category_label in iter_product_files(category_filter, limit):
        try:
            product = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("skip unreadable JSON %s: %s", json_path, exc)
            skipped_count += 1
            continue

        if not isinstance(product, dict):
            logger.warning("skip non-object product JSON: %s", json_path)
            skipped_count += 1
            continue

        chunks = build_chunks_for_product(product, category_id)
        if not chunks:
            logger.warning("skip product without a valid product_id: %s", json_path.name)
            skipped_count += 1
            continue

        product_id = chunks[0].metadata.product_id
        try:
            if store is not None:
                if replace:
                    store.delete_by_doc_id(int(product_id))
                store.upsert_chunks(chunks)
        except Exception:  # noqa: BLE001
            logger.exception("failed to ingest %s", json_path.name)
            failed_count += 1
            continue

        chunk_lengths = [len(chunk.content) for chunk in chunks]
        lengths.extend(chunk_lengths)
        totals[category_label] += 1
        totals["chunks"] += len(chunks)
        product_count += 1
        logger.info(
            "[%04d] %s: chunks=%d avg=%d max=%d",
            product_count,
            product_id,
            len(chunks),
            sum(chunk_lengths) // len(chunk_lengths),
            max(chunk_lengths),
        )

    return {
        "collection": collection_name,
        "products": product_count,
        "chunks": totals["chunks"],
        "skipped": skipped_count,
        "failed": failed_count,
        "categories": {
            category: totals[category]
            for category in CATEGORY_MAP
            if totals[category]
        },
        "min_chunk_length": min(lengths) if lengths else 0,
        "max_chunk_length": max(lengths) if lengths else 0,
        "avg_chunk_length": round(sum(lengths) / len(lengths), 1) if lengths else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import product knowledge with fixed 500/50 text chunks"
    )
    parser.add_argument(
        "--collection",
        default=TARGET_COLLECTION,
        help=f"target cloud knowledge collection (default: {TARGET_COLLECTION})",
    )
    parser.add_argument(
        "--category",
        choices=sorted(CATEGORY_MAP),
        default=None,
        help="only import one product category",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="maximum products per category; omit for all products",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build and report chunks without connecting to Milvus or DashScope",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="delete existing chunks for each product before inserting",
    )
    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than zero")

    print("=" * 72)
    print("Product knowledge import")
    print(f"  Collection : {args.collection}")
    print(f"  Category   : {args.category or 'all'}")
    print(f"  Limit      : {args.limit or 'unlimited'} per category")
    print(f"  Chunking   : size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}")
    print(f"  Replace    : {args.replace}")
    print(f"  Dry run    : {args.dry_run}")
    print(f"  Dataset    : {DATASET_ROOT}")
    print("=" * 72)

    try:
        result = ingest(
            collection_name=args.collection,
            category_filter=args.category,
            limit=args.limit,
            dry_run=args.dry_run,
            replace=args.replace,
        )
    except RuntimeError as exc:
        parser.error(str(exc))

    print("\n" + "=" * 72)
    print("[DONE] Product knowledge import" + (" (dry run)" if args.dry_run else ""))
    print(f"  Products       : {result['products']}")
    print(f"  Chunks         : {result['chunks']}")
    print(f"  Skipped        : {result['skipped']}")
    print(f"  Failed         : {result['failed']}")
    print(f"  Chunk lengths  : min={result['min_chunk_length']} "
          f"avg={result['avg_chunk_length']} max={result['max_chunk_length']}")
    for category, count in result["categories"].items():
        print(f"    {category}: {count} products")
    print("=" * 72)

    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
