"""业务库连接工厂（PostgreSQL / asyncpg）。

ai-service 的商品/用户/购物车等业务数据从 MySQL 迁移到 PostgreSQL，
本模块提供业务库的 async session。

架构：单实例 + 单库 + 多 schema
- 库：`PG_BUSINESS_DB`（默认 welove_shop_search，跟 Java 微服务共用）
- schema：product_svc / user_svc / trade_svc / chat_svc / admin_svc / public
- 连接时自动 `SET search_path` 到 `PG_BUSINESS_SEARCH_PATH`（默认覆盖所有业务 schema），
  ORM 里 `__tablename__ = "product"` 就能透明命中 `product_svc.product`

与 langgraph 记忆库（checkpointer/store）的关系：
- 记忆库变量 `PG_LANGGRAPH_DB`（= `PG_NAME`）现在也是 welove_shop_search（同一个库）
- 但 checkpointer/store 表建在 public schema，跟业务 schema 天然隔离

MySQL 兼容层：`build_mysql_url()` 仍保留，供 scripts/sync_mysql_to_pg.py 从 MySQL 拉数据用。
业务代码不应再调用它。
"""

from __future__ import annotations

from functools import lru_cache
from typing import AsyncIterator
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.config import config


def build_database_url() -> str:
    """业务库连接串（PostgreSQL asyncpg）。"""
    password = quote_plus(config.PG_PASSWORD)
    return (
        f"postgresql+asyncpg://{config.PG_USER}:{password}"
        f"@{config.PG_HOST}:{config.PG_PORT}/{config.PG_BUSINESS_DB}"
    )


def build_mysql_url() -> str:
    """MySQL 连接串（历史遗留，只用于 sync 脚本从 MySQL 拉数据）。

    业务代码请用 build_database_url()。
    """
    password = quote_plus(config.DB_PASSWORD)
    return (
        f"mysql+aiomysql://{config.DB_USER}:{password}"
        f"@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
        f"?charset={config.DB_CHARSET}"
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """业务库 (PostgreSQL) async session factory。

    通过 asyncpg 的 server_settings 在每个连接建立时设置 search_path，
    让 ORM 无 schema 前缀查询也能命中 product_svc / user_svc / trade_svc 等表。
    """
    engine = create_async_engine(
        build_database_url(),
        pool_pre_ping=True,
        pool_recycle=3600,
        # asyncpg 会把 server_settings 里的项作为 SET 命令一次性传给 server
        connect_args={
            "server_settings": {
                "search_path": config.PG_BUSINESS_SEARCH_PATH,
            },
        },
    )
    return async_sessionmaker(
        engine, expire_on_commit=False, autoflush=False,
    )


@lru_cache(maxsize=1)
def get_mysql_session_factory() -> async_sessionmaker[AsyncSession]:
    """MySQL async session factory（仅供 sync 脚本使用）。"""
    engine = create_async_engine(
        build_mysql_url(),
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    return async_sessionmaker(
        engine, expire_on_commit=False, autoflush=False,
    )


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session
