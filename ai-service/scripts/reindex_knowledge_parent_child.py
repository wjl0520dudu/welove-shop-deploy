"""Rebuild the KnowledgeAgent index with recursive parent-child chunks.

This script deliberately targets ``MILVUS_COLLECTION`` only.  It imports the
same two KnowledgeAgent sources as the legacy scripts:

* ``ingest_general_knowledge.py``: cross-product/general knowledge documents;
* ``ingest_knowledge_v2.py``: product ``rag_knowledge`` documents.

It never touches ``product_mm_collection`` or ``product_mm_v2`` used by
ShoppingAgent's product/image/multimodal retrieval.

Usage (new collection is recommended):

    # .env: MILVUS_COLLECTION=knowledge_parent_child_v1
    # .env: RAG_PARENT_CHILD_ENABLED=true
    python scripts/reindex_knowledge_parent_child.py --source all --replace

    # Smoke import: two general documents and two products per category
    python scripts/reindex_knowledge_parent_child.py --source all --limit 2 --replace

    # Inspect planned counts without calling embedding/Milvus
    python scripts/reindex_knowledge_parent_child.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.infrastructure.config import config  # noqa: E402
from app.domain.knowledge.document_pipeline import build_chunks_from_text  # noqa: E402
from app.domain.knowledge.models import DocumentChunk  # noqa: E402
from app.infrastructure.vectorstores.knowledge.vector_store import create_vector_store  # noqa: E402
from scripts.ingest_general_knowledge import DOCUMENTS  # noqa: E402
from scripts.ingest_knowledge_v2 import (  # noqa: E402
    _product_id_to_int,
    iter_product_files,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("reindex_knowledge_parent_child")

GENERAL_DOC_ID_BASE = 900000


def _product_knowledge_text(product: dict[str, Any]) -> str:
    """Rebuild one complete product knowledge document before recursive split."""
    title = str(product.get("title") or "商品知识")
    brand = str(product.get("brand") or "")
    category = str(product.get("category") or product.get("sub_category") or "")
    parts = [f"# {title}\n\n品牌：{brand}\n品类：{category}"]
    rag = product.get("rag_knowledge") or {}
    marketing = str(rag.get("marketing_description") or "").strip()
    if marketing:
        parts.append("## 商品描述\n" + marketing)
    faq_lines = []
    for faq in rag.get("official_faq") or []:
        question = str(faq.get("question") or "").strip()
        answer = str(faq.get("answer") or "").strip()
        if question and answer:
            faq_lines.append(f"### {question}\n{answer}")
    if faq_lines:
        parts.append("## 官方 FAQ\n" + "\n\n".join(faq_lines))
    review_lines = []
    for review in rag.get("user_reviews") or []:
        content = str(review.get("content") or "").strip() if isinstance(review, dict) else str(review).strip()
        if content:
            review_lines.append(f"- {content}")
    if review_lines:
        parts.append("## 用户评价\n" + "\n".join(review_lines))
    return "\n\n".join(parts)


def _general_documents(limit: int | None) -> Iterable[tuple[int, str, str, str, int | None, int | None]]:
    for index, doc in enumerate(DOCUMENTS[:limit] if limit else DOCUMENTS, start=1):
        yield (
            GENERAL_DOC_ID_BASE + index,
            str(doc["content"]),
            str(doc["name"]),
            "general_knowledge",
            doc.get("category_id"),
            None,
        )


def _product_documents(category: str | None, limit: int | None) -> Iterable[tuple[int, str, str, str, int | None, int | None]]:
    for path, category_id, _ in iter_product_files(category, limit):
        try:
            product = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("skip unreadable product knowledge %s: %s", path, exc)
            continue
        product_id = _product_id_to_int(str(product.get("product_id") or ""))
        if not product_id:
            logger.warning("skip product without stable id: %s", path.name)
            continue
        yield (
            product_id,
            _product_knowledge_text(product),
            str(product.get("title") or path.stem),
            "product_knowledge",
            category_id,
            product_id,
        )


def _build_chunks(doc_id: int, content: str, title: str, doc_type: str,
                  category_id: int | None, product_id: int | None) -> list[DocumentChunk]:
    chunks = build_chunks_from_text(
        content, doc_id=doc_id, title=title, doc_type=doc_type, category_id=category_id,
    )
    for chunk in chunks:
        chunk.metadata.product_id = product_id
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Reindex KnowledgeAgent data with parent-child chunks")
    parser.add_argument("--source", choices=["all", "general", "product"], default="all")
    parser.add_argument("--category", choices=["beauty", "digital", "fashion", "food"], default=None,
                        help="only applies to --source product/all")
    parser.add_argument("--limit", type=int, default=None,
                        help="max documents (general) or products per category (product)")
    parser.add_argument("--replace", action="store_true",
                        help="delete the same doc_id from the target collection before upsert; makes reruns idempotent")
    parser.add_argument("--dry-run", action="store_true", help="build/count chunks without embedding or Milvus writes")
    args = parser.parse_args()

    if not config.RAG_PARENT_CHILD_ENABLED:
        raise SystemExit("RAG_PARENT_CHILD_ENABLED must be true; refusing to write legacy chunks into the target collection")

    documents: list[tuple[int, str, str, str, int | None, int | None]] = []
    if args.source in {"all", "general"}:
        documents.extend(_general_documents(args.limit))
    if args.source in {"all", "product"}:
        documents.extend(_product_documents(args.category, args.limit))
    if not documents:
        raise SystemExit("no source documents found")

    logger.info("target collection=%s docs=%d source=%s replace=%s dry_run=%s",
                config.MILVUS_COLLECTION, len(documents), args.source, args.replace, args.dry_run)
    store = None if args.dry_run else create_vector_store()
    totals: Counter[str] = Counter()
    succeeded = 0

    for number, (doc_id, content, title, doc_type, category_id, product_id) in enumerate(documents, start=1):
        chunks = _build_chunks(doc_id, content, title, doc_type, category_id, product_id)
        kinds = Counter(chunk.metadata.chunk_type for chunk in chunks)
        if not kinds.get("parent") or not kinds.get("child"):
            raise RuntimeError(f"doc_id={doc_id} did not produce both parent and child chunks")
        if args.dry_run:
            logger.info("[dry %d/%d] doc=%s parent=%d child=%d", number, len(documents), doc_id,
                        kinds["parent"], kinds["child"])
        else:
            if args.replace:
                store.delete_by_doc_id(doc_id)
            store.upsert_chunks(chunks)
            logger.info("[%d/%d] doc=%s parent=%d child=%d", number, len(documents), doc_id,
                        kinds["parent"], kinds["child"])
        totals.update(kinds)
        succeeded += 1

    logger.info("completed docs=%d parent_chunks=%d child_chunks=%d target=%s",
                succeeded, totals["parent"], totals["child"], config.MILVUS_COLLECTION)
    if store is not None:
        logger.info("target stats=%s", store.stats())


if __name__ == "__main__":
    main()
