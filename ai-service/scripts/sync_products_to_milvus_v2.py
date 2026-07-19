"""PG → Milvus product_mm_v2 多模态同步脚本。

和旧 `sync_products_pg_to_milvus.py` 的边界：
- 旧脚本写 `product_mm_collection`，线上纯文本检索继续使用；
- 本脚本写 `product_mm_v2`，只用于多模态评测；
- dry-run 只打印计划，不调用 text/multimodal embedding，避免产生费用。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text                       # noqa: E402

from app.infrastructure.persistence.database import get_session_factory             # noqa: E402
from app.infrastructure.retrieval.embeddings import _build_search_text_v2, get_embeddings  # noqa: E402
from app.infrastructure.retrieval.multimodal_embeddings import (                   # noqa: E402
    MultimodalImageError,
    get_multimodal_embeddings,
    zero_image_vector,
    zero_multimodal_vector,
)
from shopping.orm_models import CategoryORM, ProductORM   # noqa: E402
from shopping.vector_store_v2 import get_product_milvus_store_v2  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("sync_products_v2")


_WATERMARK_KEY = "products_to_milvus_v2"

_ENSURE_WATERMARK_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sync_watermark (
    key VARCHAR(64) PRIMARY KEY,
    last_synced_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


# ---- watermark 持久化 -----------------------------------------------------

async def _ensure_watermark_table():
    sf = get_session_factory()
    async with sf() as s:
        await s.execute(text(_ENSURE_WATERMARK_TABLE_SQL))
        await s.commit()


async def _get_last_synced_at() -> Optional[datetime]:
    sf = get_session_factory()
    async with sf() as s:
        row = (await s.execute(
            text("SELECT last_synced_at FROM sync_watermark WHERE key = :k"),
            {"k": _WATERMARK_KEY},
        )).first()
    return row[0] if row else None


async def _save_last_synced_at(ts: datetime):
    sf = get_session_factory()
    async with sf() as s:
        await s.execute(
            text(
                "INSERT INTO sync_watermark (key, last_synced_at, updated_at) "
                "VALUES (:k, :ts, NOW()) "
                "ON CONFLICT (key) DO UPDATE SET last_synced_at = :ts, updated_at = NOW()"
            ),
            {"k": _WATERMARK_KEY, "ts": ts},
        )
        await s.commit()


# ---- PG 商品读取 ---------------------------------------------------------

async def _fetch_products_from_pg(
    *,
    since: Optional[datetime] = None,
    product_id: Optional[int] = None,
    only_active: bool = True,
) -> List[Dict[str, Any]]:
    """从 PG 读商品 join category，转成 v2 同步行的原始商品 dict。"""
    sf = get_session_factory()
    async with sf() as s:
        stmt = (
            select(ProductORM, CategoryORM.name.label("category_name"))
            .outerjoin(CategoryORM, ProductORM.category_id == CategoryORM.id)
        )
        if only_active:
            stmt = stmt.where(ProductORM.status == 1)
        if product_id is not None:
            stmt = stmt.where(ProductORM.id == product_id)
        if since is not None:
            if since.tzinfo is not None:
                since = since.astimezone(timezone.utc).replace(tzinfo=None)
            stmt = stmt.where(ProductORM.update_time > since)

        rows = (await s.execute(stmt)).all()

    products: List[Dict[str, Any]] = []
    for p, cat_name in rows:
        products.append({
            "product_id": int(p.id),
            "title": p.title or "",
            "brand": p.brand or "",
            "category": cat_name or "",
            "sub_category": p.sub_category or "",
            "base_price": float(p.base_price) if p.base_price is not None else 0.0,
            "image_url": p.image_url or "",
            "description": p.description or "",
            "tags": p.tags or "",
            "rating": float(p.rating) if p.rating is not None else 0.0,
            "sales_count": int(p.sales_count or 0),
            "review_count": int(p.review_count or 0),
            "status": int(p.status if p.status is not None else 1),
        })
    return products


# ---- Milvus 现存 ID 查询 --------------------------------------------------

def _fetch_milvus_product_ids() -> Set[int]:
    from pymilvus import Collection

    store = get_product_milvus_store_v2()
    collection = Collection(store.collection_name)
    collection.load()
    rows = collection.query(
        expr="product_id > 0",
        output_fields=["product_id"],
        limit=16384,
    )
    return {int(r["product_id"]) for r in rows}


def _diff_sets(pg_ids: Set[int], milvus_ids: Set[int]) -> Dict[str, Set[int]]:
    return {
        "to_add": pg_ids - milvus_ids,
        "to_delete": milvus_ids - pg_ids,
        "common": pg_ids & milvus_ids,
    }


# ---- 向量化行构建 ---------------------------------------------------------

def build_product_mm_v2_rows(
    products: List[Dict[str, Any]],
    *,
    sleep_seconds: float = 0.15,
) -> List[Dict[str, Any]]:
    """把 PG 商品批量转成 ProductMilvusStoreV2.upsert_rows 所需结构。

    text_dense 走 batch embedding；image / fusion 暂按单商品保守调用。
    """
    if not products:
        return []

    texts = [_build_search_text_v2(p) for p in products]
    dense_vectors = get_embeddings().embed_documents(texts)
    mm = get_multimodal_embeddings()

    rows: list[dict[str, Any]] = []
    for product, search_text, dense_vector in zip(products, texts, dense_vectors):
        image_url = str(product.get("image_url") or "").strip()
        if image_url:
            # 单张商品图挂了不阻断整批：catch MultimodalImageError 后写零
            # 向量占位。文本路（text_dense + BM25）仍能覆盖该商品。
            try:
                image_vector = mm.embed_image(image_url)
            except MultimodalImageError as e:
                logger.warning(
                    "product_id=%s image embedding 拒识别，降级零向量：%s",
                    product.get("product_id"), e,
                )
                image_vector = zero_image_vector()
            try:
                multimodal_vector = mm.embed_fusion(search_text, image_url)
            except MultimodalImageError as e:
                logger.warning(
                    "product_id=%s fusion embedding 拒识别，降级零向量：%s",
                    product.get("product_id"), e,
                )
                multimodal_vector = zero_multimodal_vector()
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
        else:
            image_vector = zero_image_vector()
            multimodal_vector = zero_multimodal_vector()

        rows.append({
            "product_id": int(product["product_id"]),
            "text": search_text,
            "text_dense_vector": dense_vector,
            "image_vector": image_vector,
            "multimodal_vector": multimodal_vector,
            "title": str(product.get("title") or "")[:256],
            "brand": str(product.get("brand") or "")[:64],
            "image_url": image_url[:512],
            "description": str(product.get("description") or "")[:2048],
            "category": str(product.get("category") or "")[:64],
            "sub_category": str(product.get("sub_category") or "")[:64],
            "tags": str(product.get("tags") or "")[:512],
            "base_price": float(product.get("base_price") or product.get("price") or 0),
            "rating": float(product.get("rating") or 0),
            "sales_count": int(product.get("sales_count") or 0),
            "review_count": int(product.get("review_count") or 0),
            "status": int(product.get("status") if product.get("status") is not None else 1),
        })
    return rows


# ---- 主流程 --------------------------------------------------------------

async def _run_full(
    *,
    dry_run: bool = False,
    batch_size: int = 20,
    sleep_seconds: float = 0.15,
) -> Dict[str, int]:
    logger.info("=== product_mm_v2 全量同步开始 ===")

    products = await _fetch_products_from_pg(only_active=True)
    pg_ids = {p["product_id"] for p in products}
    milvus_ids = _fetch_milvus_product_ids()
    diff = _diff_sets(pg_ids, milvus_ids)
    logger.info(
        "PG active=%d  Milvus v2 现存=%d  新增=%d  删除=%d  覆盖=%d",
        len(pg_ids), len(milvus_ids),
        len(diff["to_add"]), len(diff["to_delete"]), len(diff["common"]),
    )

    if dry_run:
        for p in products[:5]:
            logger.info("[dry-run upsert] id=%d title=%s", p["product_id"], p["title"][:40])
        for pid in list(diff["to_delete"])[:5]:
            logger.info("[dry-run delete] id=%d", pid)
        return {"upserted": 0, "deleted": 0, "skipped": len(products)}

    store = get_product_milvus_store_v2()
    upserted = 0
    for i in range(0, len(products), batch_size):
        chunk = products[i:i + batch_size]
        rows = build_product_mm_v2_rows(chunk, sleep_seconds=sleep_seconds)
        n = store.upsert_rows(rows)
        upserted += n
        logger.info("[batch %d-%d] upsert=%d 累计 %d", i, i + len(chunk) - 1, n, upserted)

    deleted = 0
    for pid in diff["to_delete"]:
        store.delete_by_product_id(pid)
        deleted += 1
    if deleted:
        logger.info("清理 v2 孤儿商品 %d 条", deleted)

    return {"upserted": upserted, "deleted": deleted, "skipped": 0}


async def _run_incremental(
    since: Optional[datetime],
    *,
    dry_run: bool = False,
    batch_size: int = 20,
    sleep_seconds: float = 0.15,
) -> Dict[str, int]:
    if since is None:
        since = await _get_last_synced_at()

    if since is None:
        logger.warning("v2 watermark 为空且未指定 --since，退回全量模式")
        return await _run_full(
            dry_run=dry_run,
            batch_size=batch_size,
            sleep_seconds=sleep_seconds,
        )

    logger.info("=== product_mm_v2 增量同步开始（since=%s）===", since.isoformat())

    changed_active = await _fetch_products_from_pg(since=since, only_active=True)
    changed_all = await _fetch_products_from_pg(since=since, only_active=False)
    inactive_to_delete = [p["product_id"] for p in changed_all if p["status"] != 1]
    logger.info("有更新的 active 商品=%d  变下架待删=%d", len(changed_active), len(inactive_to_delete))

    if dry_run:
        for p in changed_active[:5]:
            logger.info("[dry-run upsert] id=%d title=%s", p["product_id"], p["title"][:40])
        for pid in inactive_to_delete[:5]:
            logger.info("[dry-run delete] id=%d", pid)
        return {"upserted": 0, "deleted": 0, "skipped": len(changed_active) + len(inactive_to_delete)}

    store = get_product_milvus_store_v2()
    upserted = 0
    for i in range(0, len(changed_active), batch_size):
        chunk = changed_active[i:i + batch_size]
        rows = build_product_mm_v2_rows(chunk, sleep_seconds=sleep_seconds)
        upserted += store.upsert_rows(rows)

    deleted = 0
    for pid in inactive_to_delete:
        store.delete_by_product_id(pid)
        deleted += 1

    return {"upserted": upserted, "deleted": deleted, "skipped": 0}


async def _run_one(
    product_id: int,
    *,
    dry_run: bool = False,
    sleep_seconds: float = 0.15,
) -> Dict[str, int]:
    logger.info("=== product_mm_v2 单商品同步 product_id=%d ===", product_id)

    products = await _fetch_products_from_pg(product_id=product_id, only_active=False)
    if not products:
        logger.warning("PG 里没有 id=%d 的商品，改为从 Milvus v2 删除", product_id)
        if dry_run:
            return {"upserted": 0, "deleted": 0, "skipped": 1}
        store = get_product_milvus_store_v2()
        n = store.delete_by_product_id(product_id)
        return {"upserted": 0, "deleted": n, "skipped": 0}

    product = products[0]
    if product["status"] != 1:
        logger.info("商品 %d status=%d（下架），从 Milvus v2 删除", product_id, product["status"])
        if dry_run:
            return {"upserted": 0, "deleted": 0, "skipped": 1}
        store = get_product_milvus_store_v2()
        n = store.delete_by_product_id(product_id)
        return {"upserted": 0, "deleted": n, "skipped": 0}

    if dry_run:
        logger.info("[dry-run upsert] id=%d title=%s", product["product_id"], product["title"][:40])
        return {"upserted": 0, "deleted": 0, "skipped": 1}

    store = get_product_milvus_store_v2()
    rows = build_product_mm_v2_rows([product], sleep_seconds=sleep_seconds)
    n = store.upsert_rows(rows)
    return {"upserted": n, "deleted": 0, "skipped": 0}


# ---- CLI 入口 ------------------------------------------------------------

def _parse_since(s: str) -> datetime:
    s = s.strip().replace(" ", "T")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


async def main_async(args) -> int:
    await _ensure_watermark_table()

    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    if args.mode == "full":
        stats = await _run_full(
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            sleep_seconds=args.sleep_seconds,
        )
    elif args.mode == "incremental":
        since = _parse_since(args.since) if args.since else None
        stats = await _run_incremental(
            since=since,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            sleep_seconds=args.sleep_seconds,
        )
    elif args.mode == "one":
        if args.product_id is None:
            print("错误：--mode one 需要 --product-id", file=sys.stderr)
            return 2
        stats = await _run_one(
            product_id=args.product_id,
            dry_run=args.dry_run,
            sleep_seconds=args.sleep_seconds,
        )
    else:
        print(f"未知 mode: {args.mode}", file=sys.stderr)
        return 2

    dt = time.perf_counter() - t0
    logger.info("完成：upserted=%d deleted=%d skipped=%d 耗时 %.1fs",
                stats["upserted"], stats["deleted"], stats["skipped"], dt)

    if not args.dry_run and args.mode in ("full", "incremental"):
        await _save_last_synced_at(started_at)
        logger.info("v2 watermark 更新到 %s", started_at.isoformat())

    return 0


def main():
    parser = argparse.ArgumentParser(description="Sync products from PG to Milvus product_mm_v2")
    parser.add_argument("--mode", choices=["full", "incremental", "one"], default="incremental",
                        help="同步模式（默认 incremental）")
    parser.add_argument("--since", type=str, default=None,
                        help="增量模式的起始时间戳（ISO 格式）；不传则读 sync_watermark")
    parser.add_argument("--product-id", type=int, default=None,
                        help="--mode one 时指定的商品 id")
    parser.add_argument("--dry-run", action="store_true",
                        help="不真写 Milvus，不调用 embedding，只打印计划")
    parser.add_argument("--batch-size", type=int, default=20,
                        help="每批向量化/写入商品数（默认 20）")
    parser.add_argument("--sleep-seconds", type=float, default=0.15,
                        help="每个有图商品完成多模态调用后的 sleep 秒数（默认 0.15）")
    args = parser.parse_args()

    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
