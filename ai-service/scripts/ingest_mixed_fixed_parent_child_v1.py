"""Build the mixed fixed parent-child knowledge experiment.

The collection contains two intentionally different record types:

* product knowledge: unchanged v2.1 semantic units (marketing, one FAQ,
  three-review group), retrieved directly;
* general knowledge: fixed parent/child records (parent 1000/100, child
  500/50), retrieved through children then reconstructed from parents.

The script requires the isolated runtime configuration documented in its
``main`` validation. It never writes to product retrieval collections.
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
from app.infrastructure.config import config
from app.infrastructure.retrieval.mixed_fixed_parent_child import (
    CHILD_CHUNK_OVERLAP,
    CHILD_CHUNK_SIZE,
    PARENT_CHUNK_OVERLAP,
    PARENT_CHUNK_SIZE,
    build_mixed_fixed_parent_child_records,
)
from scripts.ingest_general_knowledge import DOCUMENTS
from scripts.ingest_knowledge_v2 import (
    _product_id_to_int,
    build_chunks_for_product as build_v21_product_chunks,
    iter_product_files,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_mixed_fixed_parent_child_v1")

TARGET_COLLECTION = "knowledge_mixed_fixed_parent_child_v1"
INDEX_VERSION = "mixed_fixed_parent_child_v1"
GENERAL_DOC_ID_BASE = 900000
CATEGORY_CHOICES = ("beauty", "digital", "fashion", "food")


def build_product_semantic_chunks(
    product: dict[str, Any],
    category_id: int,
) -> list[DocumentChunk]:
    """Reuse v2.1 product units and make them valid in the parent-child schema."""
    product_id = _product_id_to_int(str(product.get("product_id") or ""))
    if not product_id:
        return []
    chunks = build_v21_product_chunks(product, category_id, product_id)
    total_chunks = len(chunks)
    for chunk in chunks:
        chunk.metadata.total_chunks = total_chunks
        chunk.metadata.content_hash = hash_content(chunk.content)
        chunk.metadata.parent_id = ""
        chunk.metadata.child_index = 0
        chunk.metadata.index_version = INDEX_VERSION
    return chunks


def build_general_parent_child_chunks(
    document: dict[str, Any],
    document_index: int,
) -> list[DocumentChunk]:
    """Build parent and child records for one general knowledge document."""
    title = str(document.get("name") or f"General knowledge {document_index}").strip()
    content = str(document.get("content") or "").strip()
    if not content:
        return []
    doc_id = GENERAL_DOC_ID_BASE + document_index
    category_id = int(document.get("category_id") or 0)
    metadata = {
        "source": title,
        "title": title,
        "doc_type": "general_knowledge",
        "category_id": category_id,
    }
    parents, children = build_mixed_fixed_parent_child_records(doc_id, content, metadata)
    parent_chunks = [
        DocumentChunk(
            content=parent["content"],
            metadata=ChunkMetadata(
                doc_id=doc_id,
                product_id=0,
                category_id=category_id,
                source=title,
                title=title,
                doc_type="general_knowledge",
                chunk_type="parent",
                chunk_index=index,
                total_chunks=len(parents),
                content_hash=hash_content(parent["content"]),
                parent_id=parent["parent_id"],
                child_index=0,
                index_version=INDEX_VERSION,
            ),
        )
        for index, parent in enumerate(parents)
    ]
    child_chunks = [
        DocumentChunk(
            content=child["content"],
            metadata=ChunkMetadata(
                doc_id=doc_id,
                product_id=0,
                category_id=category_id,
                source=title,
                title=title,
                doc_type="general_knowledge",
                chunk_type="child",
                chunk_index=index,
                total_chunks=len(children),
                content_hash=hash_content(child["content"]),
                parent_id=child["parent_id"],
                child_index=child["child_index"],
                index_version=INDEX_VERSION,
            ),
        )
        for index, child in enumerate(children)
    ]
    return parent_chunks + child_chunks


def _make_store(collection_name: str, dry_run: bool):
    if not config.RAG_PARENT_CHILD_ENABLED:
        raise RuntimeError("set RAG_PARENT_CHILD_ENABLED=true for this experiment")
    if not config.RAG_PARENT_CHILD_GENERAL_ONLY:
        raise RuntimeError("set RAG_PARENT_CHILD_GENERAL_ONLY=true for this mixed experiment")
    if config.RAG_PARENT_CHILD_CHUNKING != "mixed_fixed_v1":
        raise RuntimeError("set RAG_PARENT_CHILD_CHUNKING=mixed_fixed_v1 for this experiment")
    if config.MILVUS_COLLECTION != collection_name:
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
    kinds: dict[str, int] = {}
    for chunk in chunks:
        kind = chunk.metadata.chunk_type
        kinds[kind] = kinds.get(kind, 0) + 1
    metadata = chunks[0].metadata
    return {
        "doc_id": metadata.doc_id,
        "title": metadata.title,
        "doc_type": metadata.doc_type,
        "chunks": len(chunks),
        "kinds": kinds,
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
        logger.info("[product %04d] %s: %d semantic chunks", result["products"], product.get("product_id"), len(chunks))
    return result


def ingest_general(store, limit: int | None, replace: bool) -> dict[str, Any]:
    result = {"products": 0, "general_documents": 0, "chunks": 0, "skipped": 0, "failed": 0, "stats": []}
    selected_documents = DOCUMENTS[:limit] if limit is not None else DOCUMENTS
    for index, document in enumerate(selected_documents, start=1):
        chunks = build_general_parent_child_chunks(document, index)
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
        kinds = result["stats"][-1]["kinds"]
        logger.info(
            "[general %02d] %s: parent=%d child=%d",
            result["general_documents"],
            document.get("name"),
            kinds.get("parent", 0),
            kinds.get("child", 0),
        )
    return result


def _print_manifest(stats: list[dict[str, Any]]) -> None:
    if not stats:
        return
    print("\nImport manifest:")
    print(f"  {'doc_id':>10}  {'type':>17}  {'title':>35}  {'chunks':>6}  {'kinds':>26}  {'inserted':>8}")
    for stat in stats:
        kinds = ",".join(f"{name}:{count}" for name, count in sorted(stat["kinds"].items()))
        print(
            f"  {int(stat['doc_id'] or 0):>10}  {stat['doc_type']:>17}  {stat['title'][:35]:>35}  "
            f"{stat['chunks']:>6}  {kinds:>26}  {stat['inserted']:>8}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the mixed fixed parent-child knowledge experiment")
    parser.add_argument("--collection", default=TARGET_COLLECTION)
    parser.add_argument("--source", choices=("product", "general", "all"), default="all")
    parser.add_argument("--category", choices=CATEGORY_CHOICES, default=None)
    parser.add_argument("--limit", type=int, default=None, help="limit per product category or general document")
    parser.add_argument("--dry-run", action="store_true", help="build and report chunks without Milvus writes")
    parser.add_argument("--replace", action="store_true", help="delete each selected doc_id before inserting")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than zero")

    try:
        store = _make_store(args.collection, args.dry_run)
    except RuntimeError as exc:
        parser.error(str(exc))

    print("=" * 78)
    print("Mixed fixed parent-child ingestion (product semantic + general parent-child)")
    print(f"  Collection       : {args.collection}")
    print(f"  Source           : {args.source}")
    print(f"  Category / limit : {args.category or 'all'} / {args.limit or 'unlimited'}")
    print(f"  General parent   : {PARENT_CHUNK_SIZE} / overlap {PARENT_CHUNK_OVERLAP}")
    print(f"  General child    : {CHILD_CHUNK_SIZE} / overlap {CHILD_CHUNK_OVERLAP}")
    print(f"  Replace / dryrun : {args.replace} / {args.dry_run}")
    print("=" * 78)

    results: list[dict[str, Any]] = []
    if args.source in {"product", "all"}:
        results.append(ingest_products(store, args.category, args.limit, args.replace))
    if args.source in {"general", "all"}:
        results.append(ingest_general(store, args.limit, args.replace))

    result = {
        key: sum(item[key] for item in results)
        for key in ("products", "general_documents", "chunks", "skipped", "failed")
    }
    stats = [stat for item in results for stat in item["stats"]]
    print("\n" + "=" * 78)
    print("[DONE] Mixed fixed parent-child ingestion" + (" (dry run)" if args.dry_run else ""))
    print(f"  Products / general documents : {result['products']} / {result['general_documents']}")
    print(f"  Stored records               : {result['chunks']}")
    print(f"  Skipped / failed             : {result['skipped']} / {result['failed']}")
    _print_manifest(stats)
    if store is not None:
        print(f"  Collection stats             : {store.stats()}")
    print("=" * 78)
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
