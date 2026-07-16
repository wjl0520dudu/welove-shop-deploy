"""Low-cost personalization for shopping retrieval results."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional

from agents.preferences import (
    PreferenceFact,
    active_preference_facts,
    make_preference_fact,
)
from core.config import config
from shopping.schemas import ShoppingNeed


_POSITIVE_ASPECTS = {
    "preference", "preference_tag", "texture", "feature",
    "brand_preference", "budget_preference",
}


def apply_user_preferences(
    need: ShoppingNeed,
    preferences: Mapping[str, Any] | None,
) -> tuple[ShoppingNeed, dict[str, Any]]:
    """Fill missing stable fields and attach long-term soft-ranking signals.

    Current-turn fields remain authoritative. Long-term facts never overwrite an
    explicit brand, budget, skin type, positive preference or avoid condition.
    """
    facts = [fact for fact in active_preference_facts(preferences) if _scope_matches(fact, need.category)]
    data = need.model_dump()

    applied_skin_fact = None
    if not need.skin_type:
        applied_skin_fact = _first_fact(facts, "skin_type", "like")
        if applied_skin_fact is not None:
            data["skin_type"] = _normalize_skin_type(str(applied_skin_fact.value))
    applied_budget_facts: list[PreferenceFact] = []
    profile_budget_min = None
    if need.budget_min is None:
        budget_min = _first_fact(facts, "budget_min", "like")
        if budget_min is not None:
            profile_budget_min = _as_float(budget_min.value)
            data["personalization_budget_min"] = profile_budget_min
            applied_budget_facts.append(budget_min)
    profile_budget_max = None
    if need.budget_max is None:
        budget_max = _first_fact(facts, "budget_max", "like")
        if budget_max is not None:
            profile_budget_max = _as_float(budget_max.value)
            data["personalization_budget_max"] = profile_budget_max
            applied_budget_facts.append(budget_max)

    explicit_positive = {_norm(v) for v in [*need.preferences, *need.must_have, *need.nice_to_have]}
    explicit_negative = {_norm(v) for v in need.avoid}
    profile_positive: list[str] = []
    profile_negative: list[str] = []
    applied: list[dict[str, Any]] = []

    for fact in facts:
        value = str(fact.value or "").strip()
        normalized = _norm(value)
        if not value:
            continue
        if fact.polarity == "like" and fact.aspect in _POSITIVE_ASPECTS:
            if normalized not in explicit_positive and normalized not in explicit_negative:
                profile_positive.append(value)
                applied.append(fact.model_dump())
        elif fact.polarity == "dislike" and fact.aspect in _POSITIVE_ASPECTS:
            if normalized not in explicit_positive and normalized not in explicit_negative:
                profile_negative.append(value)
                applied.append(fact.model_dump())

    if applied_skin_fact is not None and data.get("skin_type"):
        profile_positive.append(str(data["skin_type"]))
        applied.append(applied_skin_fact.model_dump())
    applied.extend(fact.model_dump() for fact in applied_budget_facts)

    data["personalization_preferences"] = _dedupe(profile_positive)
    data["personalization_avoid"] = _dedupe(profile_negative)
    data["applied_preference_facts"] = applied
    personalized = ShoppingNeed(**data)
    return personalized, {
        "skin_type_applied": bool(not need.skin_type and personalized.skin_type),
        "budget_applied": bool(
            profile_budget_min is not None or profile_budget_max is not None
        ),
        "positive": personalized.personalization_preferences,
        "avoid": personalized.personalization_avoid,
        "fact_count": len(applied),
    }


def facts_from_shopping_need(
    current_need: ShoppingNeed,
    *,
    query: str,
    category: Optional[str],
) -> list[dict[str, Any]]:
    """Reuse the existing need-parser output; no extra preference LLM call."""
    facts: list[dict[str, Any]] = []
    scope = {"category": category} if category else {}
    medium_expiry = (datetime.now(timezone.utc) + timedelta(days=180)).isoformat()
    short_expiry = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()

    if current_need.skin_type:
        facts.append(make_preference_fact(
            "skin_type", current_need.skin_type,
            confidence=0.98,
        ))
    if category:
        for value in current_need.preferences:
            facts.append(make_preference_fact(
                "preference", value, confidence=0.9, expires_at=medium_expiry, scope=scope,
            ))
        for value in current_need.avoid:
            facts.append(make_preference_fact(
                "preference", value, polarity="dislike", confidence=0.95,
                expires_at=medium_expiry, scope=scope,
            ))

    preference_language = any(word in (query or "") for word in ("喜欢", "偏好", "优先", "常用", "只要"))
    if category and current_need.brand and preference_language:
        facts.append(make_preference_fact(
            "brand_preference", current_need.brand, confidence=0.85,
            expires_at=medium_expiry, scope=scope,
        ))
    budget_language = any(word in (query or "") for word in ("预算", "以内", "不超过", "最多", "左右"))
    if category and budget_language and current_need.budget_min is not None:
        facts.append(make_preference_fact(
            "budget_min", current_need.budget_min, confidence=0.8,
            expires_at=short_expiry, scope=scope,
        ))
    if category and budget_language and current_need.budget_max is not None:
        facts.append(make_preference_fact(
            "budget_max", current_need.budget_max, confidence=0.8,
            expires_at=short_expiry, scope=scope,
        ))
    return facts


def personalized_rerank_candidates(
    candidates: Iterable[dict[str, Any]],
    preferences: Mapping[str, Any] | None,
    *,
    category: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Soft-rerank multimodal candidates using database text fields only."""
    items = [dict(item) for item in candidates]
    if len(items) < 2 or not preferences:
        return items

    inferred_category = category or _dominant_category(items)
    need, trace = apply_user_preferences(ShoppingNeed(category=inferred_category), preferences)
    positive = need.personalization_preferences
    negative = need.personalization_avoid
    if need.skin_type:
        positive = _dedupe([*positive, need.skin_type])
    if (
        not positive
        and not negative
        and need.personalization_budget_min is None
        and need.personalization_budget_max is None
    ):
        return items

    from shopping.ranking import _expand_synonyms

    positive_terms = {term for value in positive for term in _expand_synonyms([value])}
    negative_terms = {term for value in negative for term in _expand_synonyms([value])}
    # Keep retrieval order as the dominant prior while allowing a strong preference
    # match to swap nearby candidates. The full list is not flattened to 1..0.
    denominator = max(len(items) * 4, 1)

    for index, item in enumerate(items):
        text = _candidate_text(item)
        matched = [value for value in positive if any(term in text for term in _expand_synonyms([value]))]
        conflicts = [value for value in negative if any(term in text for term in _expand_synonyms([value]))]
        positive_score = len({term for term in positive_terms if term in text}) / max(len(positive_terms), 1)
        negative_score = len({term for term in negative_terms if term in text}) / max(len(negative_terms), 1)
        price = _as_float(item.get("price") or item.get("base_price"))
        budget_adjustment = 0.0
        if need.personalization_budget_max is not None and price is not None:
            budget_adjustment = 0.05 if price <= need.personalization_budget_max else -0.08
        if need.personalization_budget_min is not None and price is not None and price < need.personalization_budget_min:
            budget_adjustment -= 0.03
        base_order_score = 1.0 - index / denominator
        item["_personalization_score"] = round(positive_score - negative_score, 4)
        item["_personalization_matches"] = matched
        item["_personalization_conflicts"] = conflicts
        preference_weight = max(0.0, min(0.5, config.PERSONALIZATION_MULTIMODAL_WEIGHT))
        item["_personalized_rank_score"] = round(
            base_order_score * (1.0 - preference_weight)
            + positive_score * preference_weight
            - negative_score * config.PERSONALIZATION_NEGATIVE_PENALTY
            + budget_adjustment,
            6,
        )
        item["_personalization_trace"] = trace

    return sorted(items, key=lambda item: item.get("_personalized_rank_score", 0.0), reverse=True)


def _scope_matches(fact: PreferenceFact, category: Optional[str]) -> bool:
    scoped_category = str((fact.scope or {}).get("category") or "").strip()
    if not scoped_category:
        return True
    if not category:
        return False
    current = str(category).strip()
    return scoped_category in current or current in scoped_category


def _first_fact(facts: Iterable[PreferenceFact], aspect: str, polarity: str) -> Optional[PreferenceFact]:
    candidates = [
        fact for fact in facts
        if fact.aspect == aspect and fact.polarity == polarity
    ]
    return max(candidates, key=lambda fact: (fact.confidence, fact.updated_at), default=None)


def _dominant_category(items: list[dict[str, Any]]) -> Optional[str]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get("sub_category") or item.get("category") or "").strip()
        if value:
            counts[value] = counts.get(value, 0) + 1
    return max(counts, key=counts.get) if counts else None


def _candidate_text(item: Mapping[str, Any]) -> str:
    return " ".join(str(item.get(key) or "") for key in (
        "title", "brand", "category", "sub_category", "tags", "description",
    ))


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_skin_type(value: str) -> str:
    mapping = {
        "干性": "干皮", "油性": "油皮", "敏感": "敏感肌",
        "混合性": "混合肌", "中性": "中性肌",
    }
    text = str(value or "").strip()
    return mapping.get(text, text)


def _dedupe(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out
