"""查看本地 Milvus 集合的磁盘大小 / 行数

磁盘大小从 Milvus DataCoord 的 Prometheus metrics 拿：
  http://<host>:9091/metrics
  - milvus_datacoord_stored_binlog_size          原始数据 binlog
  - milvus_datacoord_stored_index_files_size     索引文件（HNSW 等）
  两个指标都以 collection_id 打标（不是 name），需要先用 describe_collection 拿到 id 再匹配。

行数从 pymilvus SDK 拿：Collection.num_entities（flush 后准确）。
"""
from __future__ import annotations

import re
import urllib.request

from pymilvus import Collection, connections, utility

HOST = "127.0.0.1"
MILVUS_PORT = "19530"
METRICS_URL = f"http://{HOST}:9091/metrics"
COLLECTIONS = ["my_rag_collection", "product_mm_v2"]

# 通用 metric 匹配：拿到 (metric_name, collection_id, value)
_METRIC_RE = re.compile(
    r'(milvus_datacoord_stored_binlog_size|milvus_datacoord_stored_index_files_size)'
    r'\{[^}]*collection_id="(\d+)"[^}]*\}\s+([0-9.eE+-]+)'
)


def human(n_bytes: float) -> str:
    size = float(n_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def fetch_size_maps() -> tuple[dict[str, float], dict[str, float]]:
    """返回 (binlog_size_map, index_size_map)，key 都是 collection_id"""
    try:
        with urllib.request.urlopen(METRICS_URL, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[warn] 拿 metrics 失败: {e}（跳过磁盘大小）")
        return {}, {}

    binlog: dict[str, float] = {}
    index: dict[str, float] = {}
    for m in _METRIC_RE.finditer(body):
        metric, cid, val = m.group(1), m.group(2), float(m.group(3))
        target = binlog if metric.endswith("binlog_size") else index
        target[cid] = target.get(cid, 0.0) + val
    return binlog, index


def inspect(name: str, binlog_map: dict[str, float], index_map: dict[str, float]) -> None:
    if not utility.has_collection(name):
        print(f"[skip] 集合不存在: {name}\n")
        return

    coll = Collection(name)
    coll.flush()

    desc = coll.describe()  # type: ignore[assignment]
    coll_id = str(desc.get("collection_id", "") if isinstance(desc, dict) else "")
    num_rows = coll.num_entities
    binlog_bytes = binlog_map.get(coll_id, 0.0)
    index_bytes = index_map.get(coll_id, 0.0)
    total_bytes = binlog_bytes + index_bytes

    print(f"=== {name} (collection_id={coll_id}) ===")
    print(f"  实体总数        : {num_rows}")
    print(f"  原始 binlog     : {human(binlog_bytes)}")
    print(f"  索引文件        : {human(index_bytes)}")
    print(f"  合计磁盘        : {human(total_bytes)}  ({int(total_bytes)} B)")
    if num_rows:
        print(f"  平均每行        : {human(total_bytes / num_rows)}")
    if index_bytes == 0.0:
        print("  ↑ 索引大小为 0：可能该 collection 还没建索引，或 metrics 名字随版本变了。")
    field_names = [f.name for f in coll.schema.fields]
    print(f"  字段            : {field_names}")
    print()


def main() -> None:
    connections.connect(alias="default", host=HOST, port=MILVUS_PORT)
    print(f"[connected] {HOST}:{MILVUS_PORT}")
    binlog_map, index_map = fetch_size_maps()
    print(f"[metrics] binlog: {len(binlog_map)} 个集合, index: {len(index_map)} 个集合\n")
    for name in COLLECTIONS:
        inspect(name, binlog_map, index_map)


if __name__ == "__main__":
    main()
