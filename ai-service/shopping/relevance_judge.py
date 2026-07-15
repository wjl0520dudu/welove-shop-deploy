"""商品检索结果的二次相关性审核。

第一阶段检索负责召回和排序；本模块负责判断候选商品是否真的属于用户图片/文字想找的商品。
LLM judge 不可用时，只在候选品类明显形成多数的情况下做保守过滤，避免为了凑满 top-k 引入异类商品。
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any, Dict, Iterable, List, Optional

from core.config import config
from rag.multimodal_embeddings import _normalize_image_url

logger = logging.getLogger("ai-service.shopping.relevance_judge")


_JUDGE_PROMPT = """你是电商商品检索结果的相关性审核器。
请根据用户的检索意图、用户参考图片和候选商品信息，判断每个候选是否应该展示。

审核原则：
1. 商品必须与图片中的主要物品属于同一商品或同一细分品类；品牌、口味、包装和规格不同不应直接判为不相关。
2. 如果图片只包含一种商品，明显属于另一品类的候选必须判为不相关。
3. 用户文字要求优先于泛化的视觉相似度；不能因为价格、销量高就保留明显异类。
4. 只输出 JSON，不要输出 Markdown 或解释性前缀。

用户文字：{query_text}

候选商品（candidate_index 从 1 开始）：
{candidates}

输出格式：
[{{"product_id": 123, "candidate_index": 1, "relevant": true, "score": 0.95, "reason": "同一细分品类"}}]
"""


def _response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, dict):
                value = part.get("text") or part.get("content")
            else:
                value = getattr(part, "text", None) or getattr(part, "content", None)
            if value:
                chunks.append(str(value))
        return "".join(chunks).strip()
    return str(content or "").strip()


def _parse_json_payload(text: str) -> Any:
    value = (text or "").strip()
    if not value:
        return None
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass

    for start_char, end_char in (("[", "]"), ("{", "}")):
        start = value.find(start_char)
        end = value.rfind(end_char)
        if start >= 0 and end > start:
            try:
                return json.loads(value[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None


def _decision_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("results", "candidates", "items", "judgements", "judgments"):
        if isinstance(payload.get(key), list):
            return [item for item in payload[key] if isinstance(item, dict)]
    return [payload] if any(k in payload for k in ("product_id", "candidate_index", "relevant")) else []


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "相关", "是"}:
            return True
        if normalized in {"false", "no", "n", "0", "不相关", "否"}:
            return False
    return None


def _as_score(value: Any) -> Optional[float]:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(score):
        return None
    return max(0.0, min(1.0, score))


def _candidate_id(item: dict[str, Any]) -> str:
    return str(item.get("product_id") or item.get("id") or "")


def _judge_content(
    query_text: str,
    query_image_url: Optional[str],
    candidates: list[dict[str, Any]],
) -> list[Any]:
    """构造兼容 OpenAI/Qwen vision 格式的 HumanMessage content。"""
    rows: list[str] = []
    image_parts: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        rows.append(json.dumps({
            "candidate_index": index,
            "product_id": candidate.get("product_id"),
            "title": candidate.get("title", ""),
            "brand": candidate.get("brand", ""),
            "category": candidate.get("category", ""),
            "sub_category": candidate.get("sub_category", ""),
            "tags": candidate.get("tags", ""),
            "description": str(candidate.get("description", ""))[:300],
            "image_url": candidate.get("image_url", ""),
        }, ensure_ascii=False))

        image_url = _normalize_image_url(str(candidate.get("image_url") or ""))
        if image_url:
            image_parts.append({
                "type": "image_url",
                "image_url": {"url": image_url},
            })

    prompt = _JUDGE_PROMPT.format(
        query_text=(query_text or "（无文字，仅依据图片判断）"),
        candidates="\n".join(rows),
    )
    content: list[Any] = [{"type": "text", "text": prompt}]
    query_image = _normalize_image_url(query_image_url)
    if query_image:
        content.append({"type": "image_url", "image_url": {"url": query_image}})
    # 候选图片放在用户图片之后，模型可以按候选顺序对照。
    content.extend(image_parts)
    return content


async def judge_candidates(
    llm: Any,
    query_text: str,
    query_image_url: Optional[str],
    candidates: Iterable[dict[str, Any]],
) -> Optional[dict[str, dict[str, Any]]]:
    """调用 LLM judge；失败时返回 None，由上层走确定性兜底。"""
    if not config.SHOPPING_LLM_JUDGE_ENABLED or llm is None:
        return None

    items = list(candidates)[: max(1, config.SHOPPING_LLM_JUDGE_MAX_CANDIDATES)]
    if not items:
        return {}

    try:
        from langchain_core.messages import HumanMessage

        response = await llm.ainvoke(
            [HumanMessage(content=_judge_content(query_text, query_image_url, items))],
            config={"tags": ["ai_internal", "shopping_llm_judge"]},
        )
        payload = _parse_json_payload(_response_text(response))
    except Exception as exc:  # noqa: BLE001
        logger.warning("shopping LLM judge unavailable, use deterministic fallback: %s", exc)
        return None

    decisions: dict[str, dict[str, Any]] = {}
    for raw in _decision_items(payload):
        pid = str(raw.get("product_id") or raw.get("id") or "").strip()
        if not pid:
            try:
                index = int(raw.get("candidate_index"))
                if 1 <= index <= len(items):
                    pid = _candidate_id(items[index - 1])
            except (TypeError, ValueError):
                pid = ""
        if not pid:
            continue

        relevant = _as_bool(raw.get("relevant"))
        score = _as_score(raw.get("score"))
        if relevant is None and score is not None:
            relevant = score >= config.SHOPPING_LLM_JUDGE_MIN_SCORE
        if relevant is None:
            continue
        decisions[pid] = {
            "relevant": relevant,
            "score": score,
            "reason": str(raw.get("reason") or "").strip(),
        }

    minimum = max(1, math.ceil(len(items) * 0.6))
    if len(decisions) < minimum:
        logger.warning("shopping LLM judge returned incomplete decisions: %d/%d", len(decisions), len(items))
        return None
    return decisions


def _category_key(item: dict[str, Any]) -> str:
    for field in ("sub_category", "category"):
        value = str(item.get(field) or "").strip().lower()
        if value:
            return value
    return ""


def category_cohesion_filter(
    candidates: Iterable[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """过滤明显的尾部异类；没有稳定多数时保持原排序。"""
    items = [dict(item) for item in candidates]
    if not items:
        return []

    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        key = _category_key(item)
        if key:
            groups.setdefault(key, []).append(item)
    if not groups:
        return items[:limit]

    dominant_key, dominant_items = max(groups.items(), key=lambda pair: len(pair[1]))
    known_count = sum(len(group) for group in groups.values())
    if len(dominant_items) < 2 or len(dominant_items) / max(known_count, 1) < 0.6:
        return items[:limit]

    first_key = _category_key(items[0])
    if first_key and first_key != dominant_key:
        return items[:limit]

    filtered = [item for item in items if _category_key(item) == dominant_key]
    logger.info(
        "category cohesion fallback removed %d outlier candidates (dominant=%s)",
        len(items) - len(filtered), dominant_key,
    )
    return filtered[:limit]


async def filter_candidates(
    llm: Any,
    query_text: str,
    query_image_url: Optional[str],
    candidates: Iterable[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """LLM judge 优先，失败后使用品类一致性兜底。"""
    items = [dict(item) for item in candidates]
    if not items:
        return []

    scope = items[: max(1, config.SHOPPING_LLM_JUDGE_MAX_CANDIDATES)]
    decisions = await judge_candidates(llm, query_text, query_image_url, scope)
    if decisions is None:
        return category_cohesion_filter(items, limit)

    filtered: list[dict[str, Any]] = []
    for item in scope:
        decision = decisions.get(_candidate_id(item))
        # 未被模型覆盖的候选保留，防止不完整但可用的 judge 输出造成过度过滤。
        if decision is None or decision["relevant"]:
            if decision is not None:
                item["_judge_score"] = decision.get("score")
                item["_judge_reason"] = decision.get("reason")
            filtered.append(item)
    return filtered[:limit]
