"""查看 PostgreSQL 业务库磁盘占用

用 PG 内置函数直接问库自己，比外部量磁盘准：
  - pg_database_size(dbname)      整库物理大小（含索引、TOAST、FSM/VM）
  - pg_total_relation_size(rel)   表 + 索引 + TOAST 全部
  - pg_relation_size(rel)         只算表本体（heap）
  - pg_indexes_size(rel)          该表所有索引累计

默认库从 core.config 读（welove_shop_search）。想看别的库直接改 DB_NAME 常量或传参。

用法：
  python ai-service/tests/check_pg_db_size.py                    # 看默认业务库
  python ai-service/tests/check_pg_db_size.py welove_shop_search # 指定库名
"""
from __future__ import annotations

import asyncio
import os
import sys

# 让 ai-service/ 下的 core.* 可导入
_HERE = os.path.dirname(os.path.abspath(__file__))
_AI_SERVICE = os.path.dirname(_HERE)
if _AI_SERVICE not in sys.path:
    sys.path.insert(0, _AI_SERVICE)

import asyncpg  # noqa: E402

from core.config import config  # noqa: E402

TOP_N_TABLES = 20


def human(n_bytes: float) -> str:
    size = float(n_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:>8.2f} {unit}"
        size /= 1024
    return f"{size:>8.2f} TB"


async def inspect(db_name: str) -> None:
    conn = await asyncpg.connect(
        host=config.PG_HOST,
        port=config.PG_PORT,
        user=config.PG_USER,
        password=config.PG_PASSWORD,
        database=db_name,
    )
    try:
        # ── 1. 整库大小 ──────────────────────────────
        db_size = await conn.fetchval("SELECT pg_database_size($1)", db_name)
        print(f"=== 数据库 {db_name} @ {config.PG_HOST}:{config.PG_PORT} ===")
        print(f"  整库物理大小:  {human(db_size)}  ({db_size} B)\n")

        # ── 2. 每个 schema 汇总 ──────────────────────
        rows = await conn.fetch(
            """
            SELECT n.nspname AS schema,
                   COUNT(c.oid) FILTER (WHERE c.relkind = 'r') AS tables,
                   COALESCE(SUM(pg_total_relation_size(c.oid))
                            FILTER (WHERE c.relkind = 'r'), 0) AS total_bytes
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
              AND n.nspname NOT LIKE 'pg_temp_%'
              AND n.nspname NOT LIKE 'pg_toast_temp_%'
            GROUP BY n.nspname
            ORDER BY total_bytes DESC
            """
        )
        print("── Schema 汇总 ──")
        print(f"  {'schema':<20}{'tables':>8}{'total':>14}")
        for r in rows:
            print(f"  {r['schema']:<20}{r['tables']:>8}   {human(r['total_bytes'])}")
        print()

        # ── 3. 表 Top N（含 heap + 索引 + TOAST） ────
        rows = await conn.fetch(
            """
            SELECT n.nspname AS schema,
                   c.relname AS name,
                   pg_total_relation_size(c.oid) AS total_bytes,
                   pg_relation_size(c.oid)      AS heap_bytes,
                   pg_indexes_size(c.oid)       AS index_bytes,
                   c.reltuples::bigint          AS approx_rows
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
              AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY total_bytes DESC
            LIMIT $1
            """,
            TOP_N_TABLES,
        )
        print(f"── 表 Top {TOP_N_TABLES}（按 total 降序） ──")
        header = f"  {'schema.table':<45}{'total':>14}{'heap':>14}{'index':>14}{'~rows':>12}"
        print(header)
        for r in rows:
            full = f"{r['schema']}.{r['name']}"
            print(
                f"  {full:<45}"
                f"   {human(r['total_bytes'])}"
                f"   {human(r['heap_bytes'])}"
                f"   {human(r['index_bytes'])}"
                f"{r['approx_rows']:>12}"
            )
        print()

        # ── 4. 主要 langgraph / 业务表精确行数（可选） ──
        # reltuples 是估计值，VACUUM 后才准；这里再补一个"关注表精确 count"
        watch_tables = _pick_watch_tables(rows)
        if watch_tables:
            print("── 关注表精确行数 ──")
            for schema, name in watch_tables:
                try:
                    cnt = await conn.fetchval(
                        f'SELECT COUNT(*) FROM "{schema}"."{name}"'
                    )
                    print(f"  {schema}.{name:<40} {cnt:>10}")
                except Exception as e:
                    print(f"  {schema}.{name:<40} [error] {e}")
    finally:
        await conn.close()


def _pick_watch_tables(top_rows) -> list[tuple[str, str]]:
    """从 Top N 里挑几张想精确 count 的表——只取前 5 张，避免大表全表扫。"""
    return [(r["schema"], r["name"]) for r in top_rows[:5]]


async def main() -> None:
    db_name = sys.argv[1] if len(sys.argv) > 1 else config.PG_BUSINESS_DB
    await inspect(db_name)


if __name__ == "__main__":
    asyncio.run(main())
