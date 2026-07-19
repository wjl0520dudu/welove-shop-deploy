"""Versioned, backward-compatible user preference facts.

Legacy profile fields remain readable, while new observations are represented as
facts carrying polarity, source, confidence, timestamps and optional category scope.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Literal, Mapping, Optional

from pydantic import BaseModel, Field


class PreferenceFact(BaseModel):
    aspect: str
    value: Any
    polarity: Literal["like", "dislike"] = "like"
    source: str = "explicit_user_statement"
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    scope: dict[str, Any] = Field(default_factory=dict)


_SINGULAR_ASPECTS = {
    "skin_type", "gender", "budget_min", "budget_max", "budget_preference",
}


def make_preference_fact(
    aspect: str,
    value: Any,
    *,
    polarity: str = "like",
    source: str = "explicit_user_statement",
    confidence: float = 0.8,
    expires_at: Optional[str] = None,
    scope: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return PreferenceFact(
        aspect=aspect,
        value=value,
        polarity=polarity,
        source=source,
        confidence=confidence,
        expires_at=expires_at,
        scope=scope or {},
    ).model_dump()


def merge_preference_facts(
    existing: Iterable[Mapping[str, Any]],
    incoming: Iterable[Mapping[str, Any]],
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Merge facts deterministically; newer conflicting facts replace older ones."""
    merged: list[PreferenceFact] = []
    for raw in [*(existing or []), *(incoming or [])]:
        try:
            fact = PreferenceFact.model_validate(dict(raw))
        except Exception:  # noqa: BLE001
            continue
        value_key = _value_key(fact.value)
        scope_key = _scope_key(fact.scope)
        if fact.aspect in _SINGULAR_ASPECTS:
            merged = [
                old for old in merged
                if not (old.aspect == fact.aspect and _scope_key(old.scope) == scope_key)
            ]
        else:
            merged = [
                old for old in merged
                if not (
                    old.aspect == fact.aspect
                    and _value_key(old.value) == value_key
                    and _scope_key(old.scope) == scope_key
                )
            ]
        merged.append(fact)

    merged.sort(key=lambda item: item.updated_at or "", reverse=True)
    return [item.model_dump() for item in merged[: max(1, limit)]]


def active_preference_facts(
    preferences: Mapping[str, Any] | None,
    *,
    now: Optional[datetime] = None,
) -> list[PreferenceFact]:
    """Read active new-format facts plus virtual facts from legacy profile fields."""
    raw = preferences or {}
    now_value = now or datetime.now(timezone.utc)
    facts: list[PreferenceFact] = []
    for item in raw.get("preference_facts") or []:
        try:
            fact = PreferenceFact.model_validate(item)
        except Exception:  # noqa: BLE001
            continue
        if not _is_expired(fact.expires_at, now_value):
            facts.append(fact)

    facts.extend(_legacy_facts(raw))
    # New facts are authoritative when a legacy field expresses the same aspect/value.
    deduped = merge_preference_facts([], [fact.model_dump() for fact in reversed(facts)])
    return [PreferenceFact.model_validate(item) for item in deduped]


def build_preference_questions(
    preferences: Mapping[str, Any] | None,
    *,
    limit: int = 4,
) -> list[str]:
    """Generate deterministic low-cost recommendation chips from active preferences."""
    facts = active_preference_facts(preferences)
    questions: list[str] = []

    skin = _first_value(facts, "skin_type", polarity="like")
    if skin:
        questions.append(f"按我{skin}的情况，有哪些合适的护肤品？")

    categories = _values(facts, {"category_interest"}, polarity="like")
    categories.extend(
        str((fact.scope or {}).get("category") or "").strip()
        for fact in facts
        if str((fact.scope or {}).get("category") or "").strip()
    )
    categories = _dedupe_text(categories)
    positive = _values(
        facts,
        {
            "preference", "preference_tag", "texture", "feature",
            "budget_preference", "brand_preference",
        },
        polarity="like",
    )
    negative = _values(
        facts,
        {"preference", "preference_tag", "texture", "feature"},
        polarity="dislike",
    )
    category = categories[0] if categories else "好物"
    for value in positive[:2]:
        questions.append(f"有哪些更符合我“{value}”偏好的{category}？")
    if negative:
        questions.append(f"推荐一些不容易出现“{negative[0]}”问题的{category}")

    budget_max = _first_value(facts, "budget_max", polarity="like")
    if budget_max is not None:
        try:
            questions.append(f"{float(budget_max):g} 元以内有哪些适合我的{category}？")
        except (TypeError, ValueError):
            pass

    return _dedupe_text(questions)[: max(0, limit)]


def _legacy_facts(raw: Mapping[str, Any]) -> list[PreferenceFact]:
    facts: list[PreferenceFact] = []

    def add(aspect: str, value: Any, confidence: float = 0.85) -> None:
        if value not in (None, "", []):
            facts.append(PreferenceFact(
                aspect=aspect,
                value=value,
                source="registered_profile",
                confidence=confidence,
                updated_at="1970-01-01T00:00:00+00:00",
            ))

    add("skin_type", raw.get("skin_type"), 0.95)
    add("gender", raw.get("gender"), 0.9)
    add("budget_min", raw.get("budget_min"))
    add("budget_max", raw.get("budget_max"))
    add("budget_preference", raw.get("budget_preference"))
    add("brand_preference", raw.get("brand_preference"))
    add("category_interest", raw.get("category_interest"))
    for tag in _as_list(raw.get("preference_tags")):
        add("preference_tag", tag, 0.9)
    return facts


def _is_expired(value: Optional[str], now: datetime) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed <= now
    except (TypeError, ValueError):
        return False


def _values(
    facts: Iterable[PreferenceFact],
    aspects: set[str],
    *,
    polarity: str,
) -> list[str]:
    return _dedupe_text([
        str(fact.value).strip()
        for fact in facts
        if fact.aspect in aspects and fact.polarity == polarity and str(fact.value).strip()
    ])


def _first_value(
    facts: Iterable[PreferenceFact], aspect: str, *, polarity: str,
) -> Any:
    for fact in facts:
        if fact.aspect == aspect and fact.polarity == polarity:
            return fact.value
    return None


def _as_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    return list(value) if isinstance(value, (list, tuple, set)) else [value]


def _dedupe_text(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _value_key(value: Any) -> str:
    return str(value).strip().lower()


def _scope_key(scope: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(k), str(v)) for k, v in (scope or {}).items() if v not in (None, "")))
