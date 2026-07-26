"""只读输出商品 Milvus collection 的真实 schema 与索引，便于导入前核对。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymilvus import Collection, MilvusClient, connections  # noqa: E402
from app.infrastructure.config import config  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect product Milvus collection schema")
    parser.add_argument("--collection", default=config.MILVUS_PRODUCT_V2_COLLECTION)
    args = parser.parse_args()
    kwargs = {"uri": config.MILVUS_URL}
    if config.MILVUS_TOKEN:
        kwargs["token"] = config.MILVUS_TOKEN
    connections.connect(**kwargs)
    client = MilvusClient(**kwargs)
    if not client.has_collection(args.collection):
        raise SystemExit(f"collection not found: {args.collection}")
    collection = Collection(args.collection)
    collection.load()
    payload = {
        "collection": args.collection,
        "entity_count": collection.num_entities,
        "fields": [
            {"name": field.name, "dtype": str(field.dtype), "primary": bool(field.is_primary), "params": field.params}
            for field in collection.schema.fields
        ],
        "indexes": [
            {
                "field_name": getattr(index, "field_name", ""),
                "index_name": getattr(index, "index_name", ""),
                "params": getattr(index, "params", {}),
            }
            for index in collection.indexes
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
