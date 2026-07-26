"""Build the semantic_v1 knowledge experiment in an isolated collection.

semantic_v1 keeps the v2.1 product units unchanged:

* one marketing description;
* one official FAQ Q&A pair;
* one group of three user reviews.

General knowledge is split on Markdown topic headings instead of a fixed or
recursive character window. A long ``##`` topic is only divided at complete
``###`` subtopics, retaining the document and topic headings in every result.

Examples (from ``ai-service``):

    python scripts/ingest_semantic_v1.py --dry-run
    python scripts/ingest_semantic_v1.py --collection knowledge_semantic_v1 --replace
    python scripts/ingest_semantic_v1.py --source general --dry-run

Set ``MILVUS_COLLECTION=knowledge_semantic_v1`` in ``.env`` before evaluation.
The script accepts ``--collection`` for safe ingestion, but runtime retrieval
always reads ``MILVUS_COLLECTION`` from ``.env``.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.knowledge.document_pipeline import hash_content
from app.domain.knowledge.models import ChunkMetadata, DocumentChunk
from app.infrastructure.config import config
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
logger = logging.getLogger("ingest_semantic_v1")

TARGET_COLLECTION = "knowledge_semantic_v1"
GENERAL_DOC_ID_BASE = 900000
TOPIC_MAX_CHARS = 800
CATEGORY_CHOICES = ("beauty", "digital", "fashion", "food")
_H1_RE = re.compile(r"^#\s+(.+?)\s*$")
_H2_RE = re.compile(r"^##\s+.+?\s*$")
_H3_RE = re.compile(r"^###\s+.+?\s*$")


def _join_nonempty(parts: Iterable[str]) -> str:
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def _root_heading(lines: list[str], fallback_title: str) -> str:
    for line in lines:
        match = _H1_RE.match(line.strip())
        if match:
            return match.group(1).strip()
    return fallback_title.strip()


def _split_h2_sections(lines: list[str]) -> tuple[str, list[str]]:
    """Return document preamble and complete second-level Markdown sections."""
    sections: list[str] = []
    preamble: list[str] = []
    current: list[str] = []
    for raw_line in lines:
        line = raw_line.rstrip()
        if _H2_RE.match(line):
            if current:
                sections.append("\n".join(current).strip())
            current = [line]
            continue
        if current:
            current.append(line)
        elif not _H1_RE.match(line.strip()):
            preamble.append(line)
    if current:
        sections.append("\n".join(current).strip())
    return "\n".join(preamble).strip(), [section for section in sections if section]


def _split_long_topic(
    document_heading: str,
    section: str,
    max_chars: int,
    topic_preamble: str = "",
) -> list[str]:
    """Split an oversized H2 section only at complete H3 subsection boundaries."""
    prefix = f"【通用知识】{document_heading}"
    section_lines = section.splitlines()
    if not section_lines:
        return []
    topic_heading = section_lines[0].strip()
    body_lines = section_lines[1:]
    fixed_context = _join_nonempty([prefix, topic_heading])

    subtopics: list[str] = []
    preamble: list[str] = []
    current: list[str] | None = None
    for raw_line in body_lines:
        line = raw_line.rstrip()
        if _H3_RE.match(line):
            if current is not None:
                subtopics.append("\n".join(current).strip())
            current = [line]
        elif current is None:
            preamble.append(line)
        else:
            current.append(line)
    if current is not None:
        subtopics.append("\n".join(current).strip())

    # A topic without H3 subsections is already the smallest meaningful unit.
    # Keep it intact instead of falling back to character slicing.
    if not subtopics:
        return [_join_nonempty([prefix, topic_preamble, section])]

    chunks: list[str] = []
    current_parts = [part for part in (topic_preamble, "\n".join(preamble).strip()) if part]
    for subtopic in subtopics:
        candidate_parts = [*current_parts, subtopic]
        candidate = _join_nonempty([fixed_context, *candidate_parts])
        if current_parts and len(candidate) > max_chars:
            chunks.append(_join_nonempty([fixed_context, *current_parts]))
            current_parts = [subtopic]
        else:
            current_parts = candidate_parts
    if current_parts:
        chunks.append(_join_nonempty([fixed_context, *current_parts]))
    return chunks


def split_general_topic_chunks(
    text: str,
    title: str,
    *,
    max_chars: int = TOPIC_MAX_CHARS,
) -> list[str]:
    """Create retrieval units from complete Markdown topics.

    ``max_chars`` is only a guard for grouping long sections. The splitter
    never cuts arbitrary characters: it either keeps a complete H2 topic or
    separates it at complete H3 subtopics.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be positive")

    lines = (text or "").replace("\r\n", "\n").splitlines()
    lines = [line.rstrip() for line in lines]
    heading = _root_heading(lines, title)
    preamble, sections = _split_h2_sections(lines)
    if not sections:
        content = _join_nonempty([f"【通用知识】{heading}", text])
        return [content] if content else []

    chunks: list[str] = []
    for index, section in enumerate(sections):
        section_preamble = preamble if index == 0 else ""
        content = _join_nonempty([f"【通用知识】{heading}", section_preamble, section])
        if len(content) <= max_chars:
            chunks.append(content)
        else:
            chunks.extend(
                _split_long_topic(
                    heading,
                    section,
                    max_chars,
                    topic_preamble=section_preamble,
                )
            )
    return chunks


def build_general_topic_chunks(document: dict[str, Any], document_index: int) -> list[DocumentChunk]:
    """Build single-layer semantic chunks for one general-knowledge document."""
    title = str(document.get("name") or f"General knowledge {document_index}").strip()
    category_id = int(document.get("category_id") or 0)
    content = str(document.get("content") or "")
    topics = split_general_topic_chunks(content, title)
    doc_id = GENERAL_DOC_ID_BASE + document_index
    total_chunks = len(topics)
    return [
        DocumentChunk(
            content=topic,
            metadata=ChunkMetadata(
                doc_id=doc_id,
                product_id=0,
                category_id=category_id,
                source=title,
                title=title,
                doc_type="general_knowledge",
                chunk_type="general_topic",
                chunk_index=index,
                total_chunks=total_chunks,
                content_hash=hash_content(topic),
                index_version="semantic_v1",
            ),
        )
        for index, topic in enumerate(topics)
    ]


def build_product_semantic_chunks(product: dict[str, Any], category_id: int) -> list[DocumentChunk]:
    """Reuse v2.1 product semantic assembly without changing its content units."""
    product_id = _product_id_to_int(str(product.get("product_id") or ""))
    if not product_id:
        return []
    chunks = build_v21_product_chunks(product, category_id, product_id)
    total_chunks = len(chunks)
    for chunk in chunks:
        chunk.metadata.total_chunks = total_chunks
        chunk.metadata.content_hash = hash_content(chunk.content)
        chunk.metadata.index_version = "semantic_v1"
    return chunks


def _make_store(collection_name: str, dry_run: bool):
    if dry_run:
        return None
    if config.RAG_PARENT_CHILD_ENABLED:
        raise RuntimeError(
            "semantic_v1 is a single-layer experiment; set RAG_PARENT_CHILD_ENABLED=false"
        )
    if collection_name == config.MILVUS_PRODUCT_COLLECTION:
        raise RuntimeError(
            f"{collection_name} is the product information collection, not a knowledge collection"
        )
    from app.infrastructure.vectorstores.knowledge.vector_store import MilvusVectorStore

    return MilvusVectorStore(collection_name=collection_name)


def _doc_stat(chunks: list[DocumentChunk], inserted_count: int) -> dict[str, Any]:
    lengths = [len(chunk.content) for chunk in chunks]
    metadata = chunks[0].metadata
    return {
        "doc_id": metadata.doc_id,
        "product_id": metadata.product_id or "",
        "title": metadata.title,
        "doc_type": metadata.doc_type,
        "chunks_count": len(chunks),
        "inserted_count": inserted_count,
        "avg_chunk_len": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "max_chunk_len": max(lengths) if lengths else 0,
        "min_chunk_len": min(lengths) if lengths else 0,
    }


def ingest_products(
    collection_name: str,
    category_filter: str | None,
    limit: int | None,
    dry_run: bool,
    replace: bool,
) -> dict[str, Any]:
    store = _make_store(collection_name, dry_run)
    total_products = 0
    total_chunks = 0
    skipped = 0
    failed = 0
    per_category: dict[str, int] = {}
    doc_stats: list[dict[str, Any]] = []

    for json_path, category_id, category_label in iter_product_files(category_filter, limit):
        try:
            product = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("skip unreadable product %s: %s", json_path.name, exc)
            skipped += 1
            continue
        if not isinstance(product, dict):
            logger.warning("skip non-object product JSON: %s", json_path.name)
            skipped += 1
            continue

        chunks = build_product_semantic_chunks(product, category_id)
        if not chunks:
            logger.warning("skip product without a valid product ID or knowledge: %s", json_path.name)
            skipped += 1
            continue

        inserted_count = 0
        try:
            if store is not None:
                if replace:
                    store.delete_by_doc_id(int(chunks[0].metadata.doc_id or 0))
                inserted_count = store.upsert_chunks(chunks)
        except Exception:  # noqa: BLE001
            logger.exception("failed to ingest product %s", json_path.name)
            failed += 1
            continue

        total_products += 1
        total_chunks += len(chunks)
        per_category[category_label] = per_category.get(category_label, 0) + 1
        doc_stats.append(_doc_stat(chunks, inserted_count))
        logger.info("[product %04d] %s - %d semantic chunks", total_products, product.get("product_id"), len(chunks))

    return {
        "products": total_products,
        "general_documents": 0,
        "chunks": total_chunks,
        "skipped": skipped,
        "failed": failed,
        "per_category": per_category,
        "doc_stats": doc_stats,
    }


def ingest_general(
    collection_name: str,
    limit: int | None,
    dry_run: bool,
    replace: bool,
) -> dict[str, Any]:
    store = _make_store(collection_name, dry_run)
    total_documents = 0
    total_chunks = 0
    failed = 0
    doc_stats: list[dict[str, Any]] = []
    selected_documents = DOCUMENTS[:limit] if limit is not None else DOCUMENTS

    for index, document in enumerate(selected_documents, start=1):
        chunks = build_general_topic_chunks(document, index)
        if not chunks:
            logger.warning("skip empty general knowledge document: %s", document.get("name"))
            continue

        inserted_count = 0
        try:
            if store is not None:
                if replace:
                    store.delete_by_doc_id(int(chunks[0].metadata.doc_id or 0))
                inserted_count = store.upsert_chunks(chunks)
        except Exception:  # noqa: BLE001
            logger.exception("failed to ingest general knowledge: %s", document.get("name"))
            failed += 1
            continue

        total_documents += 1
        total_chunks += len(chunks)
        doc_stats.append(_doc_stat(chunks, inserted_count))
        logger.info(
            "[general %02d] %s - %d topic chunks",
            total_documents,
            document.get("name"),
            len(chunks),
        )

    return {
        "products": 0,
        "general_documents": total_documents,
        "chunks": total_chunks,
        "skipped": 0,
        "failed": failed,
        "per_category": {},
        "doc_stats": doc_stats,
    }


def _print_manifest(doc_stats: list[dict[str, Any]]) -> None:
    if not doc_stats:
        return
    print("\nImport manifest:")
    print(
        f"  {'doc_id':>10}  {'type':>17}  {'title':>35}  {'chunks':>6}  "
        f"{'inserted':>8}  {'avg_len':>7}  {'max_len':>7}"
    )
    for stat in doc_stats:
        print(
            f"  {int(stat['doc_id'] or 0):>10}  {stat['doc_type']:>17}  {stat['title'][:35]:>35}  "
            f"{stat['chunks_count']:>6}  {stat['inserted_count']:>8}  "
            f"{stat['avg_chunk_len']:>7.1f}  {stat['max_chunk_len']:>7}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the semantic_v1 knowledge experiment in an isolated Milvus collection"
    )
    parser.add_argument("--collection", default=TARGET_COLLECTION)
    parser.add_argument("--source", choices=("product", "general", "all"), default="all")
    parser.add_argument("--category", choices=CATEGORY_CHOICES, default=None)
    parser.add_argument("--limit", type=int, default=None, help="limit per product category or general documents")
    parser.add_argument("--dry-run", action="store_true", help="build and report chunks without Milvus writes")
    parser.add_argument("--replace", action="store_true", help="delete each selected doc_id before inserting")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than zero")
    if config.RAG_PARENT_CHILD_ENABLED:
        parser.error(
            "semantic_v1 is a single-layer experiment; set RAG_PARENT_CHILD_ENABLED=false"
        )

    print("=" * 72)
    print("Semantic topic ingestion (semantic_v1)")
    print(f"  Collection : {args.collection}")
    print(f"  Source     : {args.source}")
    print(f"  Category   : {args.category or 'all'}")
    print(f"  Limit      : {args.limit or 'unlimited'}")
    print(f"  Topic max  : {TOPIC_MAX_CHARS} (heading boundary only)")
    print(f"  Replace    : {args.replace}")
    print(f"  Dry run    : {args.dry_run}")
    print("=" * 72)

    results: list[dict[str, Any]] = []
    try:
        if args.source in {"product", "all"}:
            results.append(ingest_products(args.collection, args.category, args.limit, args.dry_run, args.replace))
        if args.source in {"general", "all"}:
            results.append(ingest_general(args.collection, args.limit, args.dry_run, args.replace))
    except RuntimeError as exc:
        parser.error(str(exc))

    result = {
        "products": sum(item["products"] for item in results),
        "general_documents": sum(item["general_documents"] for item in results),
        "chunks": sum(item["chunks"] for item in results),
        "skipped": sum(item["skipped"] for item in results),
        "failed": sum(item["failed"] for item in results),
        "doc_stats": [stat for item in results for stat in item["doc_stats"]],
    }
    print("\n" + "=" * 72)
    print("[DONE] Semantic topic ingestion" + (" (dry run)" if args.dry_run else ""))
    print(f"  Products          : {result['products']}")
    print(f"  General documents : {result['general_documents']}")
    print(f"  Total chunks      : {result['chunks']}")
    print(f"  Skipped / failed  : {result['skipped']} / {result['failed']}")
    _print_manifest(result["doc_stats"])
    print("=" * 72)
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
