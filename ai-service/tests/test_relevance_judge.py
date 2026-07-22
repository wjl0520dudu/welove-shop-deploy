from unittest.mock import AsyncMock

import pytest

from app.domain.shopping.relevance_judge import category_cohesion_filter, filter_candidates


def _item(product_id, sub_category):
    return {
        "product_id": product_id,
        "title": str(product_id),
        "sub_category": sub_category,
    }


def test_category_cohesion_filter_removes_tail_outlier():
    items = [
        _item(1, "方便面"),
        _item(2, "方便面"),
        _item(3, "方便面"),
        _item(4, "方便面"),
        _item(5, "咖啡"),
    ]

    assert [item["product_id"] for item in category_cohesion_filter(items, 5)] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_filter_candidates_uses_judge_decisions(monkeypatch):
    monkeypatch.setattr("shopping.relevance_judge.config.SHOPPING_LLM_JUDGE_ENABLED", True)
    llm = AsyncMock()
    llm.ainvoke.return_value.content = (
        '[{"product_id": 1, "relevant": true, "score": 0.9}, '
        '{"product_id": 2, "relevant": false, "score": 0.1}]'
    )

    result = await filter_candidates(
        llm=llm,
        query_text="方便面",
        query_image_url="https://example.com/query.jpg",
        candidates=[_item(1, "方便面"), _item(2, "咖啡")],
        limit=5,
    )

    assert [item["product_id"] for item in result] == [1]
    assert result[0]["_judge_score"] == 0.9


@pytest.mark.asyncio
async def test_filter_candidates_falls_back_when_judge_fails(monkeypatch):
    monkeypatch.setattr("shopping.relevance_judge.config.SHOPPING_LLM_JUDGE_ENABLED", True)
    llm = AsyncMock()
    llm.ainvoke.side_effect = RuntimeError("vision model unavailable")

    result = await filter_candidates(
        llm=llm,
        query_text="",
        query_image_url="https://example.com/query.jpg",
        candidates=[_item(1, "方便面"), _item(2, "方便面"), _item(3, "咖啡")],
        limit=5,
    )

    assert [item["product_id"] for item in result] == [1, 2]
