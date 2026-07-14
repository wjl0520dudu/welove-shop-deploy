"""
从 Milvus my_rag_collection 导出商品知识数据，重建 PG chat_svc.knowledge_doc 记录。

背景:
    ingest_knowledge_v2.py 只灌了 Milvus 没写 PG，导致管理后台看不见这些数据。
    本脚本把 Milvus 里的 doc_id 捞出来，在 PG 里补上对应的 knowledge_doc 记录。
    这样管理后台能展示/删除，删除时也会同步清 Milvus 向量。

用法:
    cd ai-service
    python scripts/rebuild_knowledge_doc_from_milvus.py          # 只查看
    python scripts/rebuild_knowledge_doc_from_milvus.py --apply  # 真正写入 PG
"""

import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Set

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.database import get_session_factory
from pymilvus import Collection, connections, utility
from sqlalchemy import text


def get_milvus_doc_groups(collection_name: str = "my_rag_collection") -> List[Dict[str, Any]]:
    """从 Milvus 获取每个 doc_id 的概要信息（取第一个 chunk 的 metadata）。"""
    connections.connect(host=os.getenv("MILVUS_HOST", "localhost"))
    collection = Collection(collection_name)
    collection.load()

    # 获取所有 doc_id
    all_doc_ids: Set[int] = set()
    offset = 0
    limit = 1000
    while True:
        results = collection.query(
            expr="doc_id > 0",
            output_fields=["doc_id"],
            limit=limit,
            offset=offset,
        )
        if not results:
            break
        for r in results:
            all_doc_ids.add(int(r["doc_id"]))
        offset += limit
        if len(results) < limit:
            break

    # 对每个 doc_id 取第一条记录
    groups: List[Dict[str, Any]] = []
    for doc_id in sorted(all_doc_ids):
        try:
            rows = collection.query(
                expr=f"doc_id == {doc_id}",
                output_fields=["doc_id", "product_id", "title", "category_id", "source", "doc_type", "chunk_type"],
                limit=1,
            )
            if rows:
                r = rows[0]
                groups.append({
                    "doc_id": int(r.get("doc_id", doc_id)),
                    "product_id": int(r.get("product_id", 0)),
                    "title": str(r.get("title", "") or ""),
                    "category_id": int(r.get("category_id", 0)) if r.get("category_id") else None,
                    "source": str(r.get("source", "") or ""),
                    "doc_type": str(r.get("doc_type", "") or "product_knowledge"),
                    "chunk_type": str(r.get("chunk_type", "") or "text"),
                })
        except Exception as e:
            print(f"  查询 doc_id={doc_id} 失败: {e}")

    return groups


async def get_pg_doc_ids() -> Set[int]:
    """获取 PG chat_svc.knowledge_doc 中已有的 doc_id（即 id）。"""
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(text("SELECT id FROM chat_svc.knowledge_doc"))
        return {row[0] for row in result.fetchall()}


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="从 Milvus 重建 PG knowledge_doc 记录")
    parser.add_argument("--apply", action="store_true", help="实际写入 PG（不传则只预览）")
    parser.add_argument("--collection", default="my_rag_collection", help="Milvus collection 名称")
    args = parser.parse_args()

    collection_name = args.collection
    print(f"Milvus collection: {collection_name}")
    print("=" * 60)

    # 1. 获取 Milvus 数据
    print("\n[1/3] 从 Milvus 获取 doc_id 分组...")
    groups = get_milvus_doc_groups(collection_name)
    print(f"  Milvus 中共 {len(groups)} 个 doc_id")

    # 2. 获取 PG 已有 doc_id
    print("\n[2/3] 查询 PG 已有记录...")
    pg_ids = await get_pg_doc_ids()
    print(f"  PG 已有 {len(pg_ids)} 条记录 (id={sorted(pg_ids)[:5]}...)")

    # 3. 找出需要重建的
    to_create = [g for g in groups if g["doc_id"] not in pg_ids]
    exists = [g for g in groups if g["doc_id"] in pg_ids]

    print(f"\n[3/3] 对比结果:")
    print(f"  - 两端都有: {len(exists)} 个")
    print(f"  - 需要重建: {len(to_create)} 个")

    if not to_create:
        print("\n  ✅ 没有需要重建的记录，数据一致!")
        return

    print(f"\n  待重建列表:")
    for g in to_create:
        tag = ""
        if g["chunk_type"] == "marketing":
            tag = "[营销]"
        elif g["chunk_type"] == "faq":
            tag = "[FAQ]"
        elif g["chunk_type"] == "review":
            tag = "[评价]"
        print(f"    doc_id={g['doc_id']:>6}  {tag} {g['title'][:30] or g['source']}")

    if not args.apply:
        print(f"\n  (加 --apply 参数执行写入 PG)")
        return

    # 写入 PG
    print(f"\n  正在写入 PG...")
    sf = get_session_factory()
    async with sf() as session:
        created = 0
        for g in to_create:
            title = g["title"] or f"商品知识_{g['source']}"
            doc_name = f"商品知识-{title[:60]}"
            file_path = f"milvus://{collection_name}/{g['source']}"
            category_id = g["category_id"]
            now = datetime.now()

            try:
                # 使用 Milvus 的 doc_id 作为 PG 的 id（确保删除时能对应）
                await session.execute(
                    text("""
                        INSERT INTO chat_svc.knowledge_doc (id, doc_name, file_path, doc_type, status, category_id, create_time)
                        VALUES (:id, :name, :path, :type, :status, :cat, :now)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": g["doc_id"],
                        "name": doc_name,
                        "path": file_path,
                        "type": g["doc_type"],
                        "status": "COMPLETED",
                        "cat": category_id,
                        "now": now,
                    },
                )
                created += 1
                print(f"    ✅ doc_id={g['doc_id']} -> {doc_name[:40]}")
            except Exception as e:
                print(f"    ❌ doc_id={g['doc_id']} 失败: {e}")

        await session.commit()
        print(f"\n  ✅ 写入完成! 共创建 {created} 条记录")

    print(f"\n{'=' * 60}")
    print(f"刷新管理后台「知识库管理」页面即可看到这些记录。")
    print(f"它们可以在管理后台被删除（删除时同步清 Milvus 向量）。")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())