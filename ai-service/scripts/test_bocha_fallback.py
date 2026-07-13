"""独立测试博查兜底功能。不依赖 Milvus / LLM，只验证博查检索本身。

用法：
    conda activate d:\\dev\\env\\conda_envs\\wlagt
    cd d:\\dev\\project\\py\\welove-shop-agt\\ai-service
    python scripts/test_bocha_fallback.py

测试用例：
1. bocha_search 直接调用（MCP 优先，HTTP 兜底）
2. search_knowledge 完整链路（模拟 Milvus 低分 → 触发博查兜底）
3. search_knowledge 完整链路（模拟 Milvus 高分 → 不触发兜底）
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Windows 终端 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 把 ai-service 根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 打开 knowledge/mcp 相关日志（默认 WARNING 才输出，看不到 INFO）
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

from agents.runtime import init_runtime, close_runtime
from rag.models import Source


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(f" {title}")
    print("=" * 70)


async def test_1_bocha_search_direct() -> None:
    """测试 1：直接调用 bocha_search，验证博查 API 通路。"""
    section("测试 1：bocha_search 直接调用（MCP 优先，HTTP 兜底）")

    from knowledge.mcp_client import bocha_search, build_bocha_context

    query = "烟酰胺和VC能一起用吗"
    print(f"查询：{query}")

    result = await bocha_search(query, count=3)
    print(f"success: {result['success']}")
    print(f"error:   {result.get('error')}")
    print(f"results: {len(result.get('results', []))}")

    if result["success"]:
        for i, r in enumerate(result["results"], 1):
            print(f"\n  [{i}] {r['title']}")
            print(f"      站点：{r.get('site_name', '')}")
            print(f"      日期：{r.get('date_published', '')[:10]}")
            print(f"      摘要：{r.get('content', '')[:120]}...")
            print(f"      链接：{r.get('url', '')}")

        print()
        print("--- knowledge_context 拼接示例（前 500 字符）---")
        context = build_bocha_context(result["results"])
        print(context[:500] + ("..." if len(context) > 500 else ""))


async def test_2_search_knowledge_low_score() -> None:
    """测试 2：Milvus 低分 → 触发博查兜底。"""
    section("测试 2：search_knowledge 低分场景（应该触发兜底）")

    from knowledge.agent import search_knowledge

    fake_output = MagicMock()
    fake_output.knowledge_context = "（低质量内部结果）"
    fake_output.sources = [
        Source(doc="弱相关1.md", score=0.15),
        Source(doc="弱相关2.md", score=0.05),
    ]
    fake_output.results = []

    with patch("knowledge.agent.get_retriever") as gr:
        gr.return_value.retrieve.return_value = fake_output
        result = await search_knowledge.ainvoke({"query": "烟酰胺和VC能一起用吗"})

    print(f"fallback_used: {result['fallback_used']}   ← 应该是 True")
    print(f"sources 数量：{len(result['sources'])}")
    for s in result["sources"]:
        src = s.get("source", "milvus")
        title = s["title"][:60]
        print(f"  [{src:6s}] score={s.get('score', 0)}  {title}")
    print()
    print("--- knowledge_context 片段（前 500 字符）---")
    print(result["knowledge_context"][:500])


async def test_3_search_knowledge_high_score() -> None:
    """测试 3：Milvus 高分 → 不触发兜底。"""
    section("测试 3：search_knowledge 高分场景（不应触发兜底）")

    from knowledge.agent import search_knowledge

    fake_output = MagicMock()
    fake_output.knowledge_context = "烟酰胺可以和VC一起使用（内部知识库高质量结果）"
    fake_output.sources = [
        Source(doc="成分搭配.md", score=0.9),
        Source(doc="VC使用.md", score=0.7),
    ]
    fake_output.results = []

    with patch("knowledge.agent.get_retriever") as gr:
        gr.return_value.retrieve.return_value = fake_output
        result = await search_knowledge.ainvoke({"query": "烟酰胺和VC能一起用吗"})

    print(f"fallback_used: {result['fallback_used']}   ← 应该是 False")
    print(f"sources 数量：{len(result['sources'])}")
    for s in result["sources"]:
        src = s.get("source", "milvus")
        print(f"  [{src:6s}] score={s.get('score', 0)}  {s['title'][:60]}")
    print()
    print(f"knowledge_context：{result['knowledge_context']}")


async def main() -> None:
    # 初始化 runtime（Postgres + MCP 客户端）
    await init_runtime()
    try:
        await test_1_bocha_search_direct()
        await test_2_search_knowledge_low_score()
        await test_3_search_knowledge_high_score()
        section("✅ 全部测试完成")
    finally:
        await close_runtime()


if __name__ == "__main__":
    asyncio.run(main())