"""PG → 三路生产商品 collection。

仅生成 text dense、Milvus BM25、image vector；不调用图文融合 embedding。
默认 collection 为 ``product_multimodal_prod_v1``，适用于本地预演或 Zilliz Cloud。
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

from pymilvus import MilvusClient  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.infrastructure.config import config  # noqa: E402
from app.infrastructure.retrieval.embeddings import _build_search_text_v2, get_embeddings  # noqa: E402
from app.infrastructure.retrieval.multimodal_embeddings import (  # noqa: E402
    MultimodalImageError, get_multimodal_embeddings, zero_image_vector,
)
from app.infrastructure.vectorstores.product.vector_store_three_path import (  # noqa: E402
    ProductMilvusThreePathStore,
)
from sync_products_to_milvus_v2 import _fetch_products_from_pg  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("prepare_product_three_path")


def build_rows(products: list[dict[str, Any]], sleep_seconds: float) -> tuple[list[dict[str, Any]], int]:
    texts = [_build_search_text_v2(product) for product in products]
    dense_vectors = get_embeddings().embed_documents(texts)
    multimodal = get_multimodal_embeddings()
    rows, image_failures = [], 0
    for product, text, dense_vector in zip(products, texts, dense_vectors):
        image_url = str(product.get("image_url") or "").strip()
        try:
            image_vector = multimodal.embed_image(image_url) if image_url else zero_image_vector()
        except MultimodalImageError as exc:
            image_failures += 1
            logger.warning("product_id=%s image rejected; write zero image vector: %s", product["product_id"], exc)
            image_vector = zero_image_vector()
        rows.append({
            "product_id": int(product["product_id"]), "text": text,
            "text_dense_vector": dense_vector, "image_vector": image_vector,
            "title": product.get("title", ""), "brand": product.get("brand", ""),
            "image_url": image_url, "description": product.get("description", ""),
            "category": product.get("category", ""), "sub_category": product.get("sub_category", ""),
            "tags": product.get("tags", ""), "base_price": product.get("base_price", 0),
            "rating": product.get("rating", 0), "sales_count": product.get("sales_count", 0),
            "review_count": product.get("review_count", 0), "status": product.get("status", 1),
        })
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return rows, image_failures


async def main_async(args: argparse.Namespace) -> int:
    config.MILVUS_PRODUCT_THREE_PATH_COLLECTION = args.collection
    products = await _fetch_products_from_pg(only_active=True)
    logger.info("PG active products=%d; target collection=%s", len(products), args.collection)
    if args.dry_run:
        kwargs = {"uri": config.MILVUS_URL}
        if config.MILVUS_TOKEN:
            kwargs["token"] = config.MILVUS_TOKEN
        client = MilvusClient(**kwargs)
        logger.info(
            "dry-run passed; target collection exists=%s; no collection creation, embedding, or product write",
            client.has_collection(args.collection),
        )
        return 0

    store = ProductMilvusThreePathStore(args.collection)

    total, image_failures = 0, 0
    for start in range(0, len(products), args.batch_size):
        rows, failed = build_rows(products[start:start + args.batch_size], args.sleep_seconds)
        total += store.upsert_rows(rows)
        image_failures += failed
        logger.info("batch %d-%d upserted=%d", start, start + len(rows) - 1, len(rows))
    logger.info("completed collection=%s upserted=%d image_embedding_failures=%d", args.collection, total, image_failures)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Build production three-path product collection")
    parser.add_argument("--collection", default=config.MILVUS_PRODUCT_THREE_PATH_COLLECTION)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--sleep-seconds", type=float, default=0.15)
    parser.add_argument("--dry-run", action="store_true", help="check PG/Milvus only; no model calls or product writes")
    raise SystemExit(asyncio.run(main_async(parser.parse_args())))


if __name__ == "__main__":
    main()
