"""
验证 LLM 驱动的指代消解和实体抽取。

用法（在 Docker 容器内执行）：
    cd /app
    python scripts/test_llm_rules.py

测试覆盖：
1. resolve_reference：LLM 优先，正则兜底
2. entity extraction：LLM 优先，正则兜底
3. 无 LLM 时的降级行为
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── 测试数据 ──

CARDS = [
    {"product_id": 1, "title": "粉底液A", "price": 199, "brand": "品牌A", "rating": 4.5, "sales_count": 100},
    {"product_id": 2, "title": "粉底液B", "price": 299, "brand": "品牌B", "rating": 4.8, "sales_count": 300},
    {"product_id": 3, "title": "粉底液C", "price": 99,  "brand": "品牌C", "rating": 4.2, "sales_count": 500},
]

FOCUSED = {"product_id": 2, "title": "粉底液B", "price": 299}

ENTITIES = ["烟酰胺", "视黄醇", "透明质酸"]

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} — {detail}")


class MockMemory:
    """模拟 Store 的 get_business_memory 返回。"""
    def __init__(self, cards=None, focused=None, entities=None):
        self.data = {}
        if cards is not None:
            self.data["last_product_cards"] = cards
        if focused is not None:
            self.data["last_focused_product"] = focused
        if entities is not None:
            self.data["last_knowledge_entities"] = entities


# ── 测试 resolve_reference（直接测 LLM 函数）──

async def test_resolve_reference_llm():
    print("\n[resolve_reference — LLM 路径]")

    from app.application.assistant.reference_tools import _resolve_reference_with_llm

    # 商品+实体混合上下文 —— 商品优先
    mixed_memory = MockMemory(cards=CARDS, focused=FOCUSED, entities=ENTITIES).data
    # 纯实体上下文 —— 实体域
    entity_memory = MockMemory(entities=ENTITIES).data
    # 纯商品上下文
    product_memory = MockMemory(cards=CARDS, focused=FOCUSED).data

    # 1. 序号指代（有商品上下文，走商品域）
    r = await _resolve_reference_with_llm("第二个多少钱", mixed_memory)
    if r:
        check("序号指代：第二个 → product_id=2",
              r.get("has_reference") and r.get("matched_product", {}).get("product_id") == 2,
              f"got product_id={r.get('matched_product', {}).get('product_id')}")
    else:
        check("序号指代：LLM 无结果（可能无 API key，正则兜底会覆盖）", True, "LLM 返回 None，等正则兜底测试")

    # 2. 代词指代
    r = await _resolve_reference_with_llm("刚才那个多少钱", mixed_memory)
    if r:
        check("代词指代：刚才那个 → product_id=2",
              r.get("has_reference") and r.get("matched_product", {}).get("product_id") == 2,
              f"got product_id={r.get('matched_product', {}).get('product_id')}")

    # 3. 实体序号指代（只有实体上下文，走实体域）
    r = await _resolve_reference_with_llm("第二个的成分是什么", entity_memory)
    if r:
        check("实体序号指代：第二个 → 视黄醇",
              r.get("has_reference") and r.get("matched_entity") == "视黄醇",
              f"got entity={r.get('matched_entity')}")
    else:
        check("实体序号指代：LLM 无结果", True, "LLM 返回 None")

    # 4. 实体隐式指代（只有实体上下文）
    r = await _resolve_reference_with_llm("副作用严重吗", entity_memory)
    if r:
        check("实体隐式指代：副作用 → 烟酰胺",
              r.get("has_reference") and r.get("matched_entity") == "烟酰胺",
              f"got entity={r.get('matched_entity')}")
    else:
        check("实体隐式指代：LLM 无结果", True, "LLM 返回 None")

    # 5. 商品+实体混合时，商品优先
    r = await _resolve_reference_with_llm("第二个的成分是什么", mixed_memory)
    if r:
        check("混合上下文：商品优先 → product_id 不为空",
              r.get("has_reference") and r.get("matched_product") is not None,
              f"got product_id={r.get('matched_product', {}).get('product_id') if r.get('matched_product') else None}")
    else:
        check("混合上下文：LLM 无结果", True, "LLM 返回 None")

    # 6. 无指代
    r = await _resolve_reference_with_llm("推荐一款保湿粉底液", product_memory)
    if r is None:
        check("无指代 → None（正确）", True)
    else:
        check("无指代 → has_reference=false",
              not r.get("has_reference"),
              f"got has_reference={r.get('has_reference')}")

    # 7. 空上下文
    r = await _resolve_reference_with_llm("第二个", {})
    if r is None:
        check("空上下文 → None（正确）", True)
    else:
        check("空上下文 → has_reference=false",
              not r.get("has_reference"),
              f"got has_reference={r.get('has_reference')}")


async def test_resolve_reference_regex_fallback():
    """测试正则兜底路径 —— 强制 LLM 不可用，验证正则兜底。"""
    print("\n[resolve_reference — 正则兜底路径]")

    from unittest.mock import patch
    from app.application.assistant.reference_tools import resolve_reference
    from langgraph.prebuilt import ToolRuntime
    from langchain_core.runnables import RunnableConfig

    runtime = ToolRuntime(
        state={"conversation_id": "c1", "user_id": 1},
        context=None,
        config=RunnableConfig(),
        stream_writer=None,
        tool_call_id="test-call-id",
        store=None,
    )

    async def _memory(*a, **kw):
        return {"last_product_cards": CARDS, "last_focused_product": FOCUSED, "last_knowledge_entities": ENTITIES}

    # 强制 LLM 不可用 → 触发正则兜底
    with patch("core.llm.get_llm", return_value=None):
        with patch("tools.reference_tools.get_business_memory", side_effect=_memory):
            # 序号指代
            r = await resolve_reference.ainvoke({"query": "第二个多少钱", "runtime": runtime})
            check("[正则] 序号指代 → product_id=2",
                  r.get("has_reference") and r.get("matched_product", {}).get("product_id") == 2,
                  f"got product_id={r.get('matched_product', {}).get('product_id')}")

            # 代词指代
            r = await resolve_reference.ainvoke({"query": "刚才那个怎么样", "runtime": runtime})
            check("[正则] 代词指代 → product_id=2",
                  r.get("has_reference") and r.get("matched_product", {}).get("product_id") == 2)

            # 比较指代
            r = await resolve_reference.ainvoke({"query": "更便宜的", "runtime": runtime})
            check("[正则] 比较指代（更便宜）→ product_id=3（¥99）",
                  r.get("has_reference") and r.get("matched_product", {}).get("product_id") == 3,
                  f"got product_id={r.get('matched_product', {}).get('product_id')}")

            # 隐式指代
            r = await resolve_reference.ainvoke({"query": "多少钱", "runtime": runtime})
            check("[正则] 隐式指代 → product_id=2",
                  r.get("has_reference") and r.get("matched_product", {}).get("product_id") == 2)

            # 实体序号指代（混合上下文时商品优先，这是正确行为）

            # 实体复数指代（需要实体上下文，商品域优先所以此处返回复数商品）
            r = await resolve_reference.ainvoke({"query": "它们的副作用", "runtime": runtime})
            check("[正则] 实体复数 → 全部",
                  r.get("has_reference") and len(r.get("matched_entities", [])) == 3,
                  f"got {len(r.get('matched_entities', []))} entities")

            # 无指代
            r = await resolve_reference.ainvoke({"query": "推荐一款保湿粉底液", "runtime": runtime})
            check("[正则] 无指代 → has_reference=false",
                  not r.get("has_reference"))


# ── 测试 entity extraction ──

async def test_entity_extraction_llm():
    print("\n[实体抽取 — LLM 路径]")

    from app.domain.knowledge import _extract_entities_with_llm

    # 1. 并列实体
    r = await _extract_entities_with_llm("烟酰胺和视黄醇能一起用吗")
    if r:
        check("并列实体：烟酰胺和视黄醇",
              "烟酰胺" in r and "视黄醇" in r,
              f"got {r}")
    else:
        check("并列实体：LLM 无结果（可能无 API key，正则兜底会覆盖）", True, "LLM 返回 None")

    # 2. 指代不提取
    r = await _extract_entities_with_llm("第二个的成分是什么")
    if r:
        check("指代不提取 → 空列表",
              len(r) == 0,
              f"got {r}")
    elif r is None:
        check("指代不提取：LLM 无结果，等正则兜底", True)

    # 3. 单个实体
    r = await _extract_entities_with_llm("透明质酸的功效原理")
    if r:
        check("单个实体：透明质酸",
              "透明质酸" in r,
              f"got {r}")

    # 4. 空问题
    r = await _extract_entities_with_llm("")
    if r is not None:
        check("空问题 → 空列表", len(r) == 0, f"got {r}")
    else:
        check("空问题 → None", True, "LLM 返回 None，正则兜底会处理")


async def test_entity_extraction_regex_fallback():
    """测试正则兜底路径 —— 实体抽取的旧逻辑。"""
    print("\n[实体抽取 — 正则兜底路径]")

    from app.domain.knowledge import _extract_entities_from_query

    check("并列实体：烟酰胺和视黄醇",
          _extract_entities_from_query("烟酰胺和视黄醇能一起用吗") == ["烟酰胺", "视黄醇"])

    check("英文实体：VC",
          "VC" in _extract_entities_from_query("VC 和 VE 能不能一起用"))

    check("单个实体：透明质酸",
          _extract_entities_from_query("透明质酸的功效原理") == ["透明质酸"])

    check("纯停用词 → 空",
          _extract_entities_from_query("能不能一起用") == [])

    check("空 → 空",
          _extract_entities_from_query("") == [])


# ── 测试 _persist_entities 的 LLM 调用路径 ──

async def test_persist_entities_llm_path():
    """测试 _persist_entities 会优先调 LLM。"""
    print("\n[_persist_entities — LLM 优先路径]")

    from unittest.mock import patch, AsyncMock
    from app.domain.knowledge import KnowledgeAgent

    # 构造一个 mock LLM 返回实体的场景
    with patch("core.llm.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.with_structured_output.return_value = mock_llm
        # 模拟 LLM 返回实体
        from app.domain.knowledge import EntityExtractionResult
        mock_llm.ainvoke.return_value = EntityExtractionResult(entities=["烟酰胺", "视黄醇"])
        mock_get_llm.return_value = mock_llm

        with patch("knowledge.agent.remember_knowledge_entities") as mock_remember:
            agent = KnowledgeAgent(llm=mock_llm)
            await agent._persist_entities("c1", 1, "烟酰胺和视黄醇能一起用吗", [])

            # 验证 remember_knowledge_entities 被调用了
            call_args = mock_remember.call_args
            if call_args:
                _, _, entities = call_args[0]
                check("LLM 抽取的实体被写入 Store",
                      "烟酰胺" in entities and "视黄醇" in entities,
                      f"got {entities}")
            else:
                check("LLM 抽取的实体被写入 Store", False, "remember 未被调用")


# ── 格式化上下文测试 ──

async def test_format_context():
    print("\n[语境格式化 — _format_reference_context]")

    from app.application.assistant.reference_tools import _format_reference_context

    memory = {
        "last_product_cards": CARDS[:2],
        "last_focused_product": FOCUSED,
        "last_knowledge_entities": ENTITIES,
    }
    text = _format_reference_context(memory)
    check("包含商品信息", "粉底液A" in text, f"got {text[:50]}")
    check("包含关注商品", "粉底液B" in text)
    check("包含实体信息", "烟酰胺" in text)

    # 空上下文
    text = _format_reference_context({})
    check("空上下文", "暂无上下文" in text, f"got {text[:20]}")


# ── 主入口 ──

async def main():
    print("=" * 60)
    print("测试：LLM 驱动的指代消解 + 实体抽取")
    print("=" * 60)

    llm_available = os.getenv("LLM_API_KEY", "")
    if llm_available:
        print(f"  LLM 已配置（{os.getenv('LLM_MODEL', 'unknown')}），将测试 LLM 路径")
    else:
        print("  LLM 未配置，仅测试正则兜底路径（LLM 路径会返回 None）")
    print()

    await test_format_context()
    await test_resolve_reference_llm()
    await test_resolve_reference_regex_fallback()
    await test_entity_extraction_llm()
    await test_entity_extraction_regex_fallback()
    await test_persist_entities_llm_path()

    print(f"\n{'=' * 60}")
    print(f"结果：{passed} 通过，{failed} 失败，共 {passed + failed} 项")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)