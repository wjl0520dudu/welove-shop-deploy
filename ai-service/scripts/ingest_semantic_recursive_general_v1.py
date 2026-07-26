"""Build the semantic-product + recursive-general single-layer experiment.

This is the missing controlled splitter ablation:

* Product knowledge reuses the v2.1 semantic units unchanged: one marketing
  description, one FAQ Q&A, and each group of three reviews.
* General knowledge alone uses RecursiveCharacterTextSplitter with 500/50.
* Retrieval stays single-layer; parent-child reconstruction is disabled.

Use ``--dry-run --compare-fixed`` before importing. It compares each general
document against v2.1's fixed 500/50 splitter so a full RAGAS run is skipped
when recursive splitting does not materially change the collection.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.knowledge.document_pipeline import hash_content
from app.domain.knowledge.models import ChunkMetadata, DocumentChunk
from app.domain.knowledge.recursive_chunk import build_recursive_chunks_from_text
from app.infrastructure.config import config
from scripts.ingest_general_knowledge import DOCUMENTS, split_into_chunks
from scripts.ingest_knowledge_v2 import (
    _product_id_to_int,
    build_chunks_for_product as build_v21_product_chunks,
    iter_product_files,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_semantic_recursive_general_v1")

TARGET_COLLECTION = "knowledge_semantic_recursive_general_v1"
INDEX_VERSION = "semantic_recursive_general_v1"
GENERAL_DOC_ID_BASE = 900000
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CATEGORY_CHOICES = ("beauty", "digital", "fashion", "food")


def build_product_semantic_chunks(
    product: dict[str, Any],
    category_id: int,
) -> list[DocumentChunk]:
    """Reuse the v2.1 product knowledge units without any recursive split."""
    product_id = _product_id_to_int(str(product.get("product_id") or ""))
    if not product_id:
        return []
    chunks = build_v21_product_chunks(product, category_id, product_id)
    total_chunks = len(chunks)
    for chunk in chunks:
        chunk.metadata.total_chunks = total_chunks
        chunk.metadata.content_hash = hash_content(chunk.content)
        chunk.metadata.index_version = INDEX_VERSION
    return chunks


def build_general_recursive_chunks(
    document: dict[str, Any],
    document_index: int,
) -> list[DocumentChunk]:
    """Build recursive 500/50 records for one general-knowledge document."""
    title = str(document.get("name") or f"General knowledge {document_index}").strip()
    content = str(document.get("content") or "")
    chunks = build_recursive_chunks_from_text(
        text=content,
        doc_id=GENERAL_DOC_ID_BASE + document_index,
        title=title,
        doc_type="general_knowledge",
        category_id=int(document.get("category_id") or 0),
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    for chunk in chunks:
        chunk.metadata.product_id = 0
        chunk.metadata.chunk_type = "general_recursive"
        chunk.metadata.index_version = INDEX_VERSION
    return chunks


def compare_general_with_fixed(limit: int | None = None) -> list[dict[str, Any]]:
    """Compare recursive general chunks with the exact v2.1 fixed splitter."""
    selected = DOCUMENTS[:limit] if limit is not None else DOCUMENTS
    rows: list[dict[str, Any]] = []
    for index, document in enumerate(selected, start=1):
        fixed_chunks = split_into_chunks(
            str(document.get("content") or ""),
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
        )
        recursive_chunks = [
            chunk.content for chunk in build_general_recursive_chunks(document, index)
        ]
        matching_positions = sum(
            fixed == recursive
            for fixed, recursive in zip(fixed_chunks, recursive_chunks)
        )
        rows.append({
            "doc_id": GENERAL_DOC_ID_BASE + index,
            "title": str(document.get("name") or ""),
            "fixed_count": len(fixed_chunks),
            "recursive_count": len(recursive_chunks),
            "matching_positions": matching_positions,
            "identical": fixed_chunks == recursive_chunks,
        })
    return rows


def _make_store(collection_name: str, dry_run: bool):
    if config.RAG_PARENT_CHILD_ENABLED:
        raise RuntimeError(
            "semantic_recursive_general_v1 is single-layer; set RAG_PARENT_CHILD_ENABLED=false"
        )
    if not dry_run and config.MILVUS_COLLECTION != collection_name:
        raise RuntimeError(
            "MILVUS_COLLECTION must match --collection so ingestion and runtime retrieval use the same index"
        )
    if collection_name == config.MILVUS_PRODUCT_COLLECTION:
        raise RuntimeError(f"{collection_name} is a product retrieval collection, not a knowledge collection")
    if dry_run:
        return None

    from app.infrastructure.vectorstores.knowledge.vector_store import MilvusVectorStore

    return MilvusVectorStore(collection_name=collection_name)


def _write_document(store, chunks: list[DocumentChunk], replace: bool) -> int:
    if store is None:
        return 0
    doc_id = int(chunks[0].metadata.doc_id or 0)
    if replace:
        store.delete_by_doc_id(doc_id)
    return store.upsert_chunks(chunks)


def _doc_stat(chunks: list[DocumentChunk], inserted_count: int) -> dict[str, Any]:
    lengths = [len(chunk.content) for chunk in chunks]
    metadata = chunks[0].metadata
    return {
        "doc_id": metadata.doc_id,
        "product_id": metadata.product_id or "",
        "title": metadata.title,
        "doc_type": metadata.doc_type,
        "chunk_type": metadata.chunk_type,
        "chunks": len(chunks),
        "inserted": inserted_count,
        "avg_len": round(sum(lengths) / len(lengths), 1),
        "max_len": max(lengths),
    }


def ingest_products(store, category_filter: str | None, limit: int | None, replace: bool) -> dict[str, Any]:
    result = {"products": 0, "general_documents": 0, "chunks": 0, "skipped": 0, "failed": 0, "stats": []}
    for path, category_id, _category_label in iter_product_files(category_filter, limit):
        try:
            product = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("skip unreadable product %s: %s", path.name, exc)
            result["skipped"] += 1
            continue
        if not isinstance(product, dict):
            logger.warning("skip non-object product JSON: %s", path.name)
            result["skipped"] += 1
            continue

        chunks = build_product_semantic_chunks(product, category_id)
        if not chunks:
            logger.warning("skip product without stable product knowledge: %s", path.name)
            result["skipped"] += 1
            continue
        try:
            inserted = _write_document(store, chunks, replace)
        except Exception:  # noqa: BLE001
            logger.exception("failed to ingest product %s", path.name)
            result["failed"] += 1
            continue

        result["products"] += 1
        result["chunks"] += len(chunks)
        result["stats"].append(_doc_stat(chunks, inserted))
        logger.info(
            "[product %04d] %s: %d semantic chunks",
            result["products"],
            product.get("product_id"),
            len(chunks),
        )
    return result


def ingest_general(store, limit: int | None, replace: bool) -> dict[str, Any]:
    result = {"products": 0, "general_documents": 0, "chunks": 0, "skipped": 0, "failed": 0, "stats": []}
    selected = DOCUMENTS[:limit] if limit is not None else DOCUMENTS
    for index, document in enumerate(selected, start=1):
        chunks = build_general_recursive_chunks(document, index)
        if not chunks:
            logger.warning("skip empty general knowledge document: %s", document.get("name"))
            result["skipped"] += 1
            continue
        try:
            inserted = _write_document(store, chunks, replace)
        except Exception:  # noqa: BLE001
            logger.exception("failed to ingest general knowledge: %s", document.get("name"))
            result["failed"] += 1
            continue

        result["general_documents"] += 1
        result["chunks"] += len(chunks)
        result["stats"].append(_doc_stat(chunks, inserted))
        logger.info(
            "[general %02d] %s: %d recursive chunks",
            result["general_documents"],
            document.get("name"),
            len(chunks),
        )
    return result


def _print_comparison(rows: list[dict[str, Any]]) -> bool:
    print("\nGeneral chunk comparison against v2.1 fixed 500/50:")
    print(f"  {'doc_id':>10}  {'title':>35}  {'fixed':>5}  {'recursive':>9}  {'same_pos':>8}  {'identical':>9}")
    any_difference = False
    for row in rows:
        any_difference = any_difference or not row["identical"]
        print(
            f"  {row['doc_id']:>10}  {row['title'][:35]:>35}  {row['fixed_count']:>5}  "
            f"{row['recursive_count']:>9}  {row['matching_positions']:>8}  {str(row['identical']):>9}"
        )
    print(f"  Result: {'DIFFERENT - RAGAS is meaningful' if any_difference else 'IDENTICAL - skip RAGAS'}")
    return any_difference


def _print_manifest(stats: list[dict[str, Any]]) -> None:
    if not stats:
        return
    print("\nImport manifest:")
    print(f"  {'doc_id':>10}  {'type':>17}  {'chunk_type':>19}  {'title':>35}  {'chunks':>6}  {'inserted':>8}")
    for stat in stats:
        print(
            f"  {int(stat['doc_id'] or 0):>10}  {stat['doc_type']:>17}  {stat['chunk_type']:>19}  "
            f"{stat['title'][:35]:>35}  {stat['chunks']:>6}  {stat['inserted']:>8}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the semantic-product + recursive-general single-layer experiment"
    )
    parser.add_argument("--collection", default=TARGET_COLLECTION)
    parser.add_argument("--source", choices=("product", "general", "all"), default="all")
    parser.add_argument("--category", choices=CATEGORY_CHOICES, default=None)
    parser.add_argument("--limit", type=int, default=None, help="limit per product category or general document")
    parser.add_argument("--dry-run", action="store_true", help="build and report chunks without Milvus writes")
    parser.add_argument("--compare-fixed", action="store_true", help="compare general recursive chunks with v2.1 fixed 500/50")
    parser.add_argument("--replace", action="store_true", help="delete each selected doc_id before inserting")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than zero")

    try:
        store = _make_store(args.collection, args.dry_run)
    except RuntimeError as exc:
        parser.error(str(exc))

    print("=" * 78)
    print("Semantic product + recursive general ingestion (single-layer)")
    print(f"  Collection       : {args.collection}")
    print(f"  Source           : {args.source}")
    print(f"  Category / limit : {args.category or 'all'} / {args.limit or 'unlimited'}")
    print(f"  General splitter : recursive {CHUNK_SIZE}/{CHUNK_OVERLAP}")
    print(f"  Replace / dryrun : {args.replace} / {args.dry_run}")
    print("=" * 78)

    if args.compare_fixed and args.source in {"general", "all"}:
        _print_comparison(compare_general_with_fixed(args.limit))

    results: list[dict[str, Any]] = []
    if args.source in {"product", "all"}:
        results.append(ingest_products(store, args.category, args.limit, args.replace))
    if args.source in {"general", "all"}:
        results.append(ingest_general(store, args.limit, args.replace))

    summary = {
        key: sum(item[key] for item in results)
        for key in ("products", "general_documents", "chunks", "skipped", "failed")
    }
    stats = [stat for item in results for stat in item["stats"]]
    print("\n" + "=" * 78)
    print("[DONE] Semantic product + recursive general ingestion" + (" (dry run)" if args.dry_run else ""))
    print(f"  Products / general documents : {summary['products']} / {summary['general_documents']}")
    print(f"  Stored records               : {summary['chunks']}")
    print(f"  Skipped / failed             : {summary['skipped']} / {summary['failed']}")
    _print_manifest(stats)
    if store is not None:
        print(f"  Collection stats             : {store.stats()}")
    print("=" * 78)
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
