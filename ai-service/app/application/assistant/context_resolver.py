"""Turn-level context resolution for the assistant graph.

This module deliberately does *not* decide business intent or execute tools.  It
turns persisted chat artifacts into a small, scoped context snapshot before the
router and child agents run.  This prevents a later recommendation from silently
overwriting the product set referred to by "这两款".
"""
from __future__ import annotations

import re
from typing import Any, Mapping


_REFERENCE_RE = re.compile(r"这(?:两|2)款|那(?:两|2)款|它们|他们|这几个|那几个|第[一二三四五六七八九123456789]+个")
_COMPARE_RE = re.compile(r"对比|比较|哪个好|哪款好|性价比")


def _as_cards(message: Mapping[str, Any]) -> list[dict[str, Any]]:
    cards = message.get("product_cards") or message.get("productCards") or []
    return [dict(card) for card in cards if isinstance(card, Mapping)]


def _latest_product_artifact(history: list[Mapping[str, Any]]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Return the nearest assistant message that actually rendered cards."""
    for message in reversed(history):
        if str(message.get("role") or "") != "assistant":
            continue
        cards = _as_cards(message)
        if cards:
            return dict(message), cards
    return None, []


def resolve_turn_context(
    *,
    question: str,
    conversation_history: list[Mapping[str, Any]] | None,
    business_memory: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Resolve product references from persisted message artifacts.

    The message artifact is authoritative for a follow-up.  ``last_product_cards``
    remains a compatibility cache, but may not replace an immediately preceding
    multimodal recommendation.
    """
    history = list(conversation_history or [])
    memory = dict(business_memory or {})
    artifact, cards = _latest_product_artifact(history)
    text = (question or "").strip()
    is_reference = bool(_REFERENCE_RE.search(text))
    is_compare = bool(_COMPARE_RE.search(text))

    result: dict[str, Any] = {
        "has_reference": is_reference,
        "reference_source": "none",
        "reference_message_id": None,
        "resolved_product_ids": [],
        "needs_clarification": False,
        "clarification": "",
    }
    if not cards or not (is_reference or is_compare):
        return {"business_memory": memory, "context_resolution": result}

    # "这两款" is only deterministic when the referenced response itself has two
    # cards.  Selecting the first two out of three would be a silent hallucination.
    asks_for_two = bool(re.search(r"(?:这|那)(?:两|2)款", text))
    if asks_for_two and len(cards) != 2:
        result.update({
            "reference_source": "message_artifact",
            "reference_message_id": artifact.get("id") if artifact else None,
            "needs_clarification": True,
            "clarification": "我看到上一条推荐里不止两款商品。你想对比哪两款？可以直接说商品名或序号。",
        })
        return {"business_memory": memory, "context_resolution": result}

    selected = cards[:2] if asks_for_two else cards
    memory["last_product_cards"] = selected
    if len(selected) == 1:
        memory["last_focused_product"] = selected[0]
    memory["active_product_set"] = {
        "source_message_id": artifact.get("id") if artifact else None,
        "source_type": "multimodal_retrieval" if artifact and artifact.get("image_url") else "recommendation",
        "product_ids": [card.get("product_id") or card.get("id") for card in selected],
    }
    result.update({
        "reference_source": "message_artifact",
        "reference_message_id": artifact.get("id") if artifact else None,
        "resolved_product_ids": memory["active_product_set"]["product_ids"],
    })
    return {"business_memory": memory, "context_resolution": result}
