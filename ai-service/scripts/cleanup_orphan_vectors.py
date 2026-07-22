"""
清理 Milvus 中无 PG 对应记录的孤儿向量数据。

用法:
    cd ai-service
    python scripts/cleanup_orphan_vectors.py           # 只查看,不删除
    python scripts/cleanup_orphan_vectors.py --delete  # 查看并删除

逻辑:
    1. 查询 Milvus my_rag_collection 中的所有 doc_id
    2. 查询 PG chat_svc.knowledge_doc 中的所有 id
    3. 找出在 Milvus 中存在但 PG 中不存在的 doc_id
    4. 删除这些孤儿向量
"""

import os
import sys
import argparse
from typing import Set

# 添加项目根目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.vectorstores.knowledge.vector_store import create_vector_store
from pymilvus import Collection, connections


def get_milvus_doc_ids(collection_name: str = "my_rag_collection") -> Set[int]:
    """获取 Milvus 中所有 doc_id。"""
    connections.connect(host=os.getenv("MILVUS_HOST", "localhost"))
    collection = Collection(collection_name)
    collection.load()

    # 分页查询所有 doc_id
    doc_ids: Set[int] = set()
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
            doc_ids.add(int(r["doc_id"]))
        offset += limit
        if len(results) < limit:
            break

    return doc_ids


async def get_pg_doc_ids() -> Set[int]:
    """获取 PG chat_svc.knowledge_doc 表中所有 id。"""
    from sqlalchemy import text
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(text("SELECT id FROM chat_svc.knowledge_doc"))
        return {row[0] for row in result.fetchall()}


async def main():
    parser = argparse.ArgumentParser(description="清理 Milvus 孤儿向量")
    parser.add_argument("--delete", action="store_true", help="是否删除孤儿向量")
    parser.add_argument("--collection", default="my_rag_collection", help="Milvus collection 名称")
    args = parser.parse_args()

    print("=" * 50)
    print(f"Milvus collection: {args.collection}")
    print("=" * 50)

    # 1. 获取 Milvus 中的 doc_id
    print("\n[1/3] 查询 Milvus 中的 doc_id...")
    milvus_ids = get_milvus_doc_ids(args.collection)
    print(f"  Milvus 中共 {len(milvus_ids)} 个 doc_id")

    # 2. 获取 PG 中的 doc_id
    print("\n[2/3] 查询 PG chat_svc.knowledge_doc 中的 id...")
    pg_ids = await get_pg_doc_ids()
    print(f"  PG 中共 {len(pg_ids)} 个 id")

    # 3. 找出孤儿
    orphan_ids = milvus_ids - pg_ids
    both_ids = milvus_ids & pg_ids
    print(f"\n[3/3] 分析结果:")
    print(f"  - 两端都有: {len(both_ids)} 个")
    print(f"  - 仅在 Milvus(孤儿): {len(orphan_ids)} 个")
    print(f"  - 仅在 PG: {len(pg_ids - milvus_ids)} 个")

    if orphan_ids:
        print(f"\n  孤儿 doc_id: {sorted(orphan_ids)}")
        if args.delete:
            print("\n  正在删除孤儿向量...")
            vector_store = create_vector_store()
            for doc_id in sorted(orphan_ids):
                deleted = vector_store.delete_by_doc_id(doc_id)
                print(f"    删除 doc_id={doc_id} -> {deleted} 个 chunk")
            print(f"\n  ✅ 删除完成!")
        else:
            print("\n  (加 --delete 参数执行删除)")
    else:
        print("\n  ✅ 没有孤儿向量，数据一致!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())