"""指代消解工具 —— 显式解析用户问题中的商品/知识实体指代表达。

resolve_reference 工具负责把 "第二个"、"刚才那个"、"更便宜的"、"它" 等模糊指代
解析为具体商品或知识实体，让 Agent 不再靠 LLM 自行猜测。

## 两种解析域

### 商品域（ShoppingAgent 使用）
从 Store 的 last_product_cards / last_focused_product 里定位商品，
返回 matched_product（单数）或 matched_products（复数）。

### 知识实体域（KnowledgeAgent 使用）
从 Store 的 last_knowledge_entities 里定位实体（成分名、产品名等），
返回 matched_entity（单数）或 matched_entities（复数）。

**优先级：商品指代命中优先**（product 有 product_id 更结构化，
且 shopping 场景对指代的定位精度要求更高）。商品未命中再尝试实体。

## 支持的指代类型

| 类型 | 示例 | 解析方式 |
|------|------|----------|
| 序号指代 | "第二个"、"最后一款"、"倒数第一个" | last_product_cards[index] |
| 复数/集合 | "他们三"、"这三款"、"这几款" | last_product_cards 多款 |
| 代词指代 | "刚才那个"、"这个"、"那个"、"它" | last_focused_product 或 cards[0] |
| 比较指代 | "更便宜的"、"评分更高的"、"销量多的" | last_product_cards 按字段排序取最优 |
| 隐式指代 | "还有别的颜色吗"、"多少钱" | last_focused_product |
| **实体序号** | 上一轮"烟酰胺和视黄醇" → "第二个成分" | last_knowledge_entities[1] |
| **实体复数** | 上一轮"A/B/C" → "它们都能空腹用吗" | last_knowledge_entities 全部 |
| **实体隐式** | 上一轮谈"烟酰胺" → "副作用有哪些"（无商品上下文） | last_knowledge_entities[0] |

## 工具返回结构

```json
{
  "has_reference": true,
  "resolved_query": "「视黄醇」的成分是什么",
  "matched_product": {...} | null,           // 商品域命中时
  "matched_products": [...],                 // 商品复数
  "matched_entity": "视黄醇" | null,          // 实体域命中时
  "matched_entities": ["视黄醇"],            // 实体复数
  "reference_type": "ordinal|entity_ordinal|...",
  "hint": "已将「第二个」解析为「视黄醇」，请基于此实体检索"
}
```

如果未检测到指代，has_reference=False，resolved_query 为原始 query。
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from pydantic import BaseModel, Field

from app.infrastructure.persistence.memory import get_business_memory
from app.infrastructure.llm.llm import get_llm

logger = logging.getLogger("ai-service.reference_tools")


# ---- 指代模式 ---------------------------------------------------------------

# 中文数字 → int 映射（覆盖常见序号，够用即可）
_CHINESE_NUM: dict[str, int] = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def _parse_numeral(s: str) -> Optional[int]:
    """把 '2' / '二' / '十' 之类解析成 int；无法解析返回 None。"""
    s = s.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if s in _CHINESE_NUM:
        return _CHINESE_NUM[s]
    return None


# 序号指代：第二个、第三款、最后一个、倒数第一个
# 支持阿拉伯数字和常见中文数字（一/二/三/两/十/…）
_NUM_CHAR_CLASS = r"[0-9一二两三四五六七八九十]+"
_ORDINAL_PATTERNS: list[tuple[str, Any]] = [
    # "第2个" / "第二个" → (index_from_start = num - 1)
    (rf"第\s*({_NUM_CHAR_CLASS})\s*[个款]",
     lambda m: (_parse_numeral(m.group(1)) or 0) - 1),
    # "最后一个" / "最后一款" → -1
    (r"最后一\s*[个款]", lambda m: -1),
    # "倒数第2个" / "倒数第二个" → -num
    (rf"倒数第\s*({_NUM_CHAR_CLASS})\s*[个款]",
     lambda m: -(_parse_numeral(m.group(1)) or 0)),
]

# 代词指代
_PRONOUN_PATTERNS = ["刚才那个", "刚才这款", "那个", "这个", "这款", "它"]

# 比较指代：匹配 "更/最 + 形容词 + 的（那个/这款）"
_COMPARATIVE_PATTERNS: list[tuple[str, str]] = [
    (r"更?便宜的(?:那个|这款)?", "price"),
    (r"更?贵的(?:那个|这款)?", "price"),
    (r"评分[更高最]+的(?:那个|这款)?", "rating"),
    (r"评价[更好最]+的(?:那个|这款)?", "rating"),
    (r"口碑[更好最]+的(?:那个|这款)?", "rating"),
    (r"销量[更高最多]+的(?:那个|这款)?", "sales_count"),
    (r"更?实惠的(?:那个|这款)?", "price"),
]

# 比较指代的触发关键词（用于优先级判定：pronominal 前先看有没有 comparative）
_COMPARATIVE_MARKERS = ["便宜", "贵", "实惠", "评分", "评价", "口碑", "销量"]

# 隐式指代：没有明确指代词，但语义上指向当前关注的商品
_IMPLICIT_MARKERS = [
    "还有别的颜色", "有其他颜色", "还有别的色号", "有其他色号",
    "多少钱", "什么价格", "价格多少",
    "还有货", "有货吗", "库存",
    "适合什么肤质", "适合我吗",
]

# 复数/集合指代：指向上轮推荐的多款商品（他们三、这三款、这几款、它们）
# 区别于 _resolve_comparative（"更便宜的那款" = 选一个）：这里返回多款，用于
# "他们三价格怎么样""这三款对比一下"这类对集合整体提问的场景。
_PLURAL_PRONOUNS: list[str] = [
    "他们", "它们", "这几款", "这几个", "那几款", "那几个",
    "上面几款", "上面几个", "刚才那几款", "刚才那几个", "刚才推荐的",
    "这俩", "那俩", "这两款", "那两款", "这几样", "那几样",
]
# "这/那 + 数字 + 款/个" —— 这三款、那两个、这 3 款
_PLURAL_NUM_PATTERN = re.compile(r"[这那]\s*([0-9一二两三四五六七八九十]+)\s*[款个]")
# "他们三 / 它们三" —— 带数量的集合代词
_PLURAL_PRONOUN_NUM_PATTERN = re.compile(r"(?:他们|它们)\s*([0-9一二两三四五六七八九十]+)")

# 比较意图：用户想对多款商品做横向对比（区别于"更便宜的那款"这种选一个）
# 命中时 hint 会引导 agent 调 compare_products。
_COMPARE_INTENT_MARKERS: list[str] = [
    "比较", "对比", "比一下", "相比", "比比", "横向对比", "对比一下", "比一比",
]


def _resolve_ordinal(
    query: str, last_cards: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """尝试解析序号指代。"""
    for pattern, index_fn in _ORDINAL_PATTERNS:
        m = re.search(pattern, query)
        if not m:
            continue
        try:
            idx = index_fn(m)
        except (TypeError, ValueError):
            continue
        if not last_cards:
            return None
        # index_fn 可能返回 -1 表示 "无法解析中文数字"（0 - 1），这里需过滤掉
        if idx == -1 and "最后" not in m.group():
            continue
        if idx >= 0 and idx < len(last_cards):
            product = last_cards[idx]
        elif idx < 0 and abs(idx) <= len(last_cards):
            product = last_cards[idx]
        else:
            return None
        product_name = product.get("title") or f"商品{product.get('product_id', '')}"
        resolved = re.sub(pattern, f"「{product_name}」", query, count=1)
        return {
            "has_reference": True,
            "resolved_query": resolved,
            "matched_product": product,
            "reference_type": "ordinal",
            "hint": f"已将序号指代解析为「{product_name}」，请基于此商品回答。",
        }
    return None


def _resolve_pronominal(
    query: str, focused: Optional[Dict[str, Any]], last_cards: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """尝试解析代词指代。

    如果 query 里同时含比较指代关键词（便宜/贵/评分/…），跳过代词解析，
    交给下一级比较解析器处理。避免 "更便宜的那个" 被拆成 "那个"。
    """
    if any(marker in query for marker in _COMPARATIVE_MARKERS):
        return None

    for pronoun in _PRONOUN_PATTERNS:
        if pronoun not in query:
            continue
        # 优先级：last_focused_product > cards[0]
        product = focused or (last_cards[0] if last_cards else None)
        if not product:
            return None
        product_name = product.get("title") or f"商品{product.get('product_id', '')}"
        resolved = query.replace(pronoun, f"「{product_name}」", 1)
        return {
            "has_reference": True,
            "resolved_query": resolved,
            "matched_product": product,
            "reference_type": "pronominal",
            "hint": f"已将「{pronoun}」解析为「{product_name}」，请基于此商品回答。",
        }
    return None


def _resolve_comparative(
    query: str, last_cards: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """尝试解析比较指代。"""
    if not last_cards:
        return None

    for pattern, sort_field in _COMPARATIVE_PATTERNS:
        m = re.search(pattern, query)
        if not m:
            continue
        # 按指定字段排序
        if sort_field == "price":
            # "更便宜的" → 升序取第一个；"更贵的" → 降序
            ascending = "便宜" in m.group() or "实惠" in m.group()
            sorted_cards = sorted(
                last_cards,
                key=lambda c: float(c.get("price") or 999999),
            )
            product = sorted_cards[0] if ascending else sorted_cards[-1]
        elif sort_field == "rating":
            sorted_cards = sorted(
                last_cards,
                key=lambda c: float(c.get("rating") or 0),
                reverse=True,
            )
            product = sorted_cards[0]
        elif sort_field == "sales_count":
            sorted_cards = sorted(
                last_cards,
                key=lambda c: int(c.get("sales_count") or 0),
                reverse=True,
            )
            product = sorted_cards[0]
        else:
            product = last_cards[0]

        product_name = product.get("title") or f"商品{product.get('product_id', '')}"
        resolved = re.sub(pattern, f"「{product_name}」", query, count=1)
        return {
            "has_reference": True,
            "resolved_query": resolved,
            "matched_product": product,
            "reference_type": "comparative",
            "hint": f"已将比较指代解析为「{product_name}」（{m.group()}），请基于此商品回答。",
        }
    return None


def _resolve_implicit(
    query: str, focused: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """尝试解析隐式指代。"""
    if not focused:
        return None
    for marker in _IMPLICIT_MARKERS:
        if marker in query:
            product_name = focused.get("title") or f"商品{focused.get('product_id', '')}"
            return {
                "has_reference": True,
                "resolved_query": query,
                "matched_product": focused,
                "reference_type": "implicit",
                "hint": f"此问题隐式指向当前关注的商品「{product_name}」，请基于此商品回答。",
            }
    return None


# ---- 知识实体域解析 --------------------------------------------------------
# 复用商品域的序号 / 复数正则模式（"第二个"、"这三个"、"它们"都通用）；
# 但隐式指代的触发词不同：知识场景没有"多少钱""还有颜色吗"这类，改成
# "副作用"、"功效"、"成分"、"怎么用"这类跟知识主体强绑定的词。

# 实体隐式指代触发词：句子里出现这些词、且没有明确说主语，就认为在
# 追问上一轮谈到的实体。区别于商品的 _IMPLICIT_MARKERS。
_ENTITY_IMPLICIT_MARKERS = [
    "副作用", "禁忌", "禁用", "不良反应",
    "功效", "作用", "效果", "有用吗", "有效吗",
    "成分", "有什么成分", "含什么",
    "怎么用", "怎样用", "怎么使用", "用法",
    "适合什么", "适合哪种", "适合谁",
    "浓度", "剂量",
    "原理", "机制",
]


def _resolve_entity_ordinal(
    query: str, entities: List[str]
) -> Optional[Dict[str, Any]]:
    """实体序号指代：'第二个'、'最后一个' → last_knowledge_entities[index]。

    正则模式与商品序号完全一致（"第二个/最后一个/倒数第 N 个"），
    只是拿 index 去查实体列表而非商品列表。
    """
    if not entities:
        return None
    for pattern, index_fn in _ORDINAL_PATTERNS:
        m = re.search(pattern, query)
        if not m:
            continue
        try:
            idx = index_fn(m)
        except (TypeError, ValueError):
            continue
        if idx == -1 and "最后" not in m.group():
            continue
        if 0 <= idx < len(entities):
            entity = entities[idx]
        elif idx < 0 and abs(idx) <= len(entities):
            entity = entities[idx]
        else:
            return None
        resolved = re.sub(pattern, f"「{entity}」", query, count=1)
        return {
            "has_reference": True,
            "resolved_query": resolved,
            "matched_entity": entity,
            "matched_entities": [entity],
            "reference_type": "entity_ordinal",
            "hint": f"已将序号指代解析为上一轮知识实体「{entity}」，请基于此实体检索/回答。",
        }
    return None


def _resolve_entity_plural(
    query: str, entities: List[str]
) -> Optional[Dict[str, Any]]:
    """实体复数指代：'它们'、'这几个'、'他们三' → last_knowledge_entities 多个。"""
    if not entities:
        return None

    n: Optional[int] = None
    matched = False

    m = _PLURAL_NUM_PATTERN.search(query)
    if m:
        n = _parse_numeral(m.group(1))
        matched = True

    if not matched:
        m2 = _PLURAL_PRONOUN_NUM_PATTERN.search(query)
        if m2:
            n = _parse_numeral(m2.group(1))
            matched = True

    if not matched and any(p in query for p in _PLURAL_PRONOUNS):
        matched = True

    if not matched:
        return None

    picked = list(entities[:n]) if n else list(entities)
    if not picked:
        return None

    names = "、".join(picked)
    return {
        "has_reference": True,
        "resolved_query": query,
        "matched_entity": picked[0],       # 兼容单数字段
        "matched_entities": picked,
        "reference_type": "entity_plural",
        "hint": (
            f"已将指代解析为上一轮知识实体：{names}。"
            f"请针对这些实体分别检索/回答，禁止把整句原样丢进 search_knowledge。"
        ),
    }


def _resolve_entity_implicit(
    query: str, entities: List[str]
) -> Optional[Dict[str, Any]]:
    """实体隐式指代：句里含 '副作用/功效/成分/怎么用' 等词、没有明确主语，
    就认为在追问上一轮谈到的（首个）实体。

    只在没匹配到商品指代且 last_knowledge_entities 非空时才会走到这里。
    只取首个实体（entities[0]）作为默认追问对象，因为多轮追问的
    "副作用是什么"通常问的是上一轮讨论的主要对象。
    """
    if not entities:
        return None
    for marker in _ENTITY_IMPLICIT_MARKERS:
        if marker in query:
            entity = entities[0]
            return {
                "has_reference": True,
                "resolved_query": query,
                "matched_entity": entity,
                "matched_entities": [entity],
                "reference_type": "entity_implicit",
                "hint": (
                    f"此问题隐式追问上一轮知识实体「{entity}」的「{marker}」，"
                    f"请以「{entity}」为检索主体。"
                ),
            }
    return None


def _resolve_plural(
    query: str, last_cards: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """尝试解析复数/集合指代：他们三、这三款、这几款 → 上轮推荐的多款商品。

    用于"他们三价格怎么样""这三款对比一下""它们哪个销量高"这类对
    集合整体提问的场景。区别于 _resolve_comparative（选一个最优），
    这里返回多款，让 agent 基于这些商品回答或调 compare_products。
    """
    if not last_cards:
        return None

    n: Optional[int] = None
    matched = False

    # 这三款 / 那两个 / 这 3 款 → 取前 N 个
    m = _PLURAL_NUM_PATTERN.search(query)
    if m:
        n = _parse_numeral(m.group(1))
        matched = True

    # 他们三 / 它们三 → 取前 N 个
    if not matched:
        m2 = _PLURAL_PRONOUN_NUM_PATTERN.search(query)
        if m2:
            n = _parse_numeral(m2.group(1))
            matched = True

    # 裸复数代词：他们 / 它们 / 这几款 → 全部
    if not matched and any(p in query for p in _PLURAL_PRONOUNS):
        matched = True

    if not matched:
        return None

    products = list(last_cards[:n]) if n else list(last_cards)
    if not products:
        return None

    names = "、".join(
        p.get("title") or f"商品{p.get('product_id', '')}" for p in products
    )
    is_compare = any(mk in query for mk in _COMPARE_INTENT_MARKERS)
    ref_type = "plural_compare" if is_compare else "plural"
    if is_compare:
        hint = (
            f"已将指代解析为上轮推荐的 {len(products)} 款商品：{names}。"
            f"用户想对比这些商品，请直接调用 compare_products()（无需传参，"
            f"工具会自动读取这 {len(products)} 款做对比），禁止重新搜索。"
        )
    else:
        hint = (
            f"已将指代解析为上轮推荐的 {len(products)} 款商品：{names}。"
            f"请基于这些商品回答，禁止重新搜索。"
        )
    return {
        "has_reference": True,
        "resolved_query": query,
        "matched_product": products[0],   # 兼容单数字段
        "matched_products": products,     # 复数
        "reference_type": ref_type,
        "hint": hint,
    }


# ---- 工具本体 ----------------------------------------------------------------


class ReferenceResult(BaseModel):
    """指代消解的结构化输出（LLM 用 with_structured_output 产出）。"""
    has_reference: bool = Field(..., description="是否检测到指代")
    resolved_query: str = Field(default="", description="解析后的 query，指代已被替换为实体名/商品名")
    matched_product_id: Optional[int] = Field(default=None, description="商品域命中的 product_id（单数）")
    matched_product_ids: List[int] = Field(default_factory=list, description="商品域命中的 product_id 列表（复数/集合）")
    matched_entity: Optional[str] = Field(default=None, description="实体域命中的实体名（单数）")
    matched_entities: List[str] = Field(default_factory=list, description="实体域命中的实体名列表（复数）")
    reference_type: Optional[str] = Field(default=None, description="指代类型：ordinal | plural | pronominal | comparative | implicit | entity_ordinal | entity_plural | entity_implicit")
    hint: str = Field(default="", description="给 LLM 的提示（含后续动作建议）")


_REFERENCE_RESOLVER_PROMPT = """你是指代消解器。根据对话上下文，判断用户当前问题是否包含指代表达，并解析为具体商品或知识实体。

## 支持的指代类型

| 类型 | 示例 | 说明 |
|------|------|------|
| ordinal | "第二个"、"第三款"、"最后一个" | 序号指代，按上轮商品列表顺序 |
| pronominal | "刚才那个"、"这个"、"它" | 代词指代，优先匹配当前关注商品 |
| comparative | "更便宜的"、"评分高的那个" | 比较指代，按价格/评分等字段排序 |
| implicit | "多少钱"、"还有别的颜色吗" | 隐式指代，指向当前关注商品 |
| plural | "他们三"、"这几款"、"它们" | 复数指代，指向多款商品 |
| entity_ordinal | "第二个成分" | 实体序号指代，看上轮知识实体列表 |
| entity_plural | "它们能一起用吗" | 实体复数指代 |
| entity_implicit | "副作用"、"成分"、"怎么用" | 实体隐式指代，追问上轮实体 |

## 规则
1. **必须有上下文才能判定指代**：如果上下文里没有商品也没有实体，has_reference 必须为 false，不能自己编造
2. 商品域优先于实体域：同时有商品和实体上下文时，优先返回商品域结果
3. matched_product_id 填商品列表中的 product_id 数值
4. matched_entity 必须填实体列表中实际出现的实体名（如"视黄醇"），不能编造，不能填 null
5. entity_ordinal 类型：看"第X个"来定位实体列表，例如"第二个"在实体列表["烟酰胺","视黄醇","透明质酸"]中对应第2个→ matched_entity="视黄醇"
6. resolved_query 把指代替换为具体的名称
7. entity_implicit 类型：追问"副作用/成分/怎么用"且没有明确主语时，指向实体列表的第1个（如实体列表["烟酰胺","视黄醇","透明质酸"]，问"副作用" → matched_entity="烟酰胺"）"""


def _format_reference_context(memory: Dict[str, Any]) -> str:
    """把 business_memory 格式化成 LLM 可读的上下文。"""
    parts: List[str] = []

    cards = memory.get("last_product_cards") or []
    if cards:
        lines = [f"  第{i}个：{c.get('title')}（¥{c.get('price')}）product_id={c.get('product_id')}"
                 for i, c in enumerate(cards[:5], 1)]
        if len(cards) > 5:
            lines.append(f"  … 另有 {len(cards) - 5} 个未列出")
        parts.append("[上轮推荐商品]\n" + "\n".join(lines))

    focused = memory.get("last_focused_product")
    if focused:
        parts.append(f"[当前关注商品] {focused.get('title')}（product_id={focused.get('product_id')}）")

    entities = memory.get("last_knowledge_entities") or []
    if entities:
        lines = [f"  第{i}个：{e}" for i, e in enumerate(entities[:5], 1)]
        parts.append("[上轮谈到的知识实体]\n" + "\n".join(lines))

    return "\n\n".join(parts) if parts else "（暂无上下文）"


async def _resolve_reference_with_llm(query: str, memory: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """用 LLM 解析指代。失败返回 None 触发正则兜底。"""
    try:
        llm = get_llm()
        if llm is None:
            return None
    except Exception:
        logger.warning("LLM not available for resolve_reference", exc_info=True)
        return None

    context = _format_reference_context(memory)
    cards = memory.get("last_product_cards") or []

    try:
        structured = llm.with_structured_output(ReferenceResult, method="function_calling")
        result = await structured.ainvoke(
            [
                SystemMessage(content=_REFERENCE_RESOLVER_PROMPT),
                SystemMessage(content=f"## 对话上下文\n\n{context}"),
                HumanMessage(content=query),
            ],
            config={"tags": ["ai_internal"]},
        )
    except Exception:
        logger.warning("LLM resolve_reference failed", exc_info=True)
        return None

    if not isinstance(result, ReferenceResult) or not result.has_reference:
        return None

    # 从 product_id 反查 product card
    matched_product = None
    matched_products = []
    target_ids = []
    if result.matched_product_id is not None:
        target_ids.append(result.matched_product_id)
    if result.matched_product_ids:
        target_ids.extend(result.matched_product_ids)

    if target_ids and cards:
        for pid in set(target_ids):
            for c in cards:
                if c.get("product_id") == pid:
                    cpy = dict(c)
                    if cpy not in matched_products:
                        matched_products.append(cpy)
                    if matched_product is None:
                        matched_product = cpy
                    break

    matched_entity = result.matched_entity
    matched_entities = result.matched_entities or []
    if matched_entity and matched_entity not in matched_entities:
        matched_entities.insert(0, matched_entity)

    hint = result.hint or ""
    if not hint and matched_product:
        hint = f"已将指代解析为「{matched_product.get('title')}」，请基于此商品回答。"
    elif not hint and matched_entity:
        hint = f"已将指代解析为「{matched_entity}」，请基于此实体检索/回答。"

    return {
        "has_reference": True,
        "resolved_query": result.resolved_query or query,
        "matched_product": matched_product,
        "matched_products": matched_products,
        "matched_entity": matched_entity,
        "matched_entities": matched_entities,
        "reference_type": result.reference_type,
        "hint": hint,
    }


@tool(parse_docstring=True)
async def resolve_reference(query: str, runtime: ToolRuntime) -> Dict[str, Any]:
    """解析用户问题中的商品/知识实体指代表达。

    支持两个域的指代消解：
    - 商品域（ShoppingAgent）：从 last_product_cards / last_focused_product 定位商品
    - 知识实体域（KnowledgeAgent）：从 last_knowledge_entities 定位实体（成分名等）

    **调用时机**：
    - 序号："第二个"、"第三款"、"最后一个"
    - 复数："他们三"、"这三款"、"这几款"、"它们"
    - 代词："刚才那个"、"这个"、"它"
    - 比较："更便宜的"、"评分高的那个"（仅商品域）
    - 隐式：
      - 商品域："还有别的颜色吗"、"多少钱"（指 last_focused_product）
      - 实体域："副作用"、"功效"、"怎么用"、"成分"（指 last_knowledge_entities[0]）

    **解析优先级**：商品域先于实体域。同一句话同时有两种上下文时，
    优先返回商品域结果（product_id 更结构化，且 shopping 场景对指代精度要求高）。

    如果两域都没命中，has_reference=False。

    Args:
        query: 用户当前问题文本。
        runtime: 工具运行时（自动注入）。从 runtime.state 拿 conversation_id / user_id。

    Returns:
        dict: {
            "has_reference": bool,
            "resolved_query": str,          # 解析后的 query
            "matched_product": dict|None,   # 商品域命中的（首个）商品
            "matched_products": list,        # 商品域复数
            "matched_entity": str|None,      # 实体域命中的（首个）实体
            "matched_entities": list,        # 实体域复数
            "reference_type": str|None,     # ordinal | plural | plural_compare |
                                            # pronominal | comparative | implicit |
                                            # entity_ordinal | entity_plural | entity_implicit
            "hint": str,                    # 给 LLM 的提示（含后续动作建议）
        }
    """
    state = runtime.state or {}
    cid = state.get("conversation_id")
    uid = state.get("user_id")

    try:
        memory = await get_business_memory(cid, uid)
    except Exception:
        logger.warning("resolve_reference: Store 读取失败", exc_info=True)
        return _no_reference_result(query, hint="无法读取业务记忆，无法解析指代。请直接按原始 query 处理。")

    # ── LLM 优先 ──
    llm_result = await _resolve_reference_with_llm(query, memory)
    if llm_result is not None:
        return llm_result

    # ── LLM 失败 → 正则兜底 ──
    last_cards: List[Dict[str, Any]] = memory.get("last_product_cards") or []
    focused: Optional[Dict[str, Any]] = memory.get("last_focused_product")
    entities: List[str] = memory.get("last_knowledge_entities") or []

    product_result = _try_product_resolvers(query, last_cards, focused)
    if product_result is not None:
        return _pad_result(product_result)

    entity_result = _try_entity_resolvers(query, entities)
    if entity_result is not None:
        return _pad_result(entity_result)

    return _no_reference_result(query, hint="未检测到指代表达，请按正常流程处理。")


def _try_product_resolvers(
    query: str,
    last_cards: List[Dict[str, Any]],
    focused: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """按优先级跑商品域解析器，返回第一个命中结果或 None。"""
    if r := _resolve_ordinal(query, last_cards):
        return r
    if r := _resolve_plural(query, last_cards):
        return r
    if r := _resolve_pronominal(query, focused, last_cards):
        return r
    if r := _resolve_comparative(query, last_cards):
        return r
    if r := _resolve_implicit(query, focused):
        return r
    return None


def _try_entity_resolvers(
    query: str,
    entities: List[str],
) -> Optional[Dict[str, Any]]:
    """按优先级跑实体域解析器，返回第一个命中结果或 None。"""
    if r := _resolve_entity_ordinal(query, entities):
        return r
    if r := _resolve_entity_plural(query, entities):
        return r
    if r := _resolve_entity_implicit(query, entities):
        return r
    return None


def _pad_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """给命中结果补齐缺失字段，让上游拿到统一 shape。

    保证 matched_product / matched_products / matched_entity / matched_entities
    都存在（缺失的填 None / []），避免下游 KeyError。
    """
    result.setdefault("matched_product", None)
    result.setdefault("matched_products", [])
    result.setdefault("matched_entity", None)
    result.setdefault("matched_entities", [])
    return result


def _no_reference_result(query: str, hint: str) -> Dict[str, Any]:
    """构造未命中的统一返回结构。"""
    return {
        "has_reference": False,
        "resolved_query": query,
        "matched_product": None,
        "matched_products": [],
        "matched_entity": None,
        "matched_entities": [],
        "reference_type": None,
        "hint": hint,
    }



# ---- 工具集合 ---------------------------------------------------------------

REFERENCE_TOOLS: list = [resolve_reference]
