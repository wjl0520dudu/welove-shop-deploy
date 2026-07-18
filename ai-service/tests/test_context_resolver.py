from assistant.context_resolver import resolve_turn_context


TEXT_CARDS = [
    {"product_id": 11, "title": "旧的文字推荐 A"},
    {"product_id": 12, "title": "旧的文字推荐 B"},
]
IMAGE_CARDS = [
    {"product_id": 21, "title": "图片命中 A"},
    {"product_id": 22, "title": "图片命中 B"},
]


def test_compare_reference_prefers_latest_multimodal_message_artifact():
    result = resolve_turn_context(
        question="这两款对比一下",
        business_memory={"last_product_cards": TEXT_CARDS},
        conversation_history=[
            {"id": 1, "role": "assistant", "product_cards": TEXT_CARDS},
            {"id": 2, "role": "user", "content": "帮我找图里的同款", "image_url": "https://img.example/q.jpg"},
            {"id": 3, "role": "assistant", "image_url": "https://img.example/q.jpg", "product_cards": IMAGE_CARDS},
            {"id": 4, "role": "user", "content": "这两款对比一下"},
        ],
    )

    assert result["context_resolution"]["reference_message_id"] == 3
    assert result["business_memory"]["last_product_cards"] == IMAGE_CARDS
    assert result["business_memory"]["active_product_set"]["source_type"] == "multimodal_retrieval"


def test_two_product_reference_is_clarified_when_source_has_three_cards():
    result = resolve_turn_context(
        question="那两款哪个好？",
        business_memory={},
        conversation_history=[
            {"id": 3, "role": "assistant", "product_cards": IMAGE_CARDS + [{"product_id": 23, "title": "图片命中 C"}]},
        ],
    )

    assert result["context_resolution"]["needs_clarification"] is True
    assert result["business_memory"].get("last_product_cards") is None


def test_non_reference_does_not_replace_existing_product_memory():
    result = resolve_turn_context(
        question="敏感肌要注意什么？",
        business_memory={"last_product_cards": TEXT_CARDS},
        conversation_history=[{"id": 3, "role": "assistant", "product_cards": IMAGE_CARDS}],
    )

    assert result["business_memory"]["last_product_cards"] == TEXT_CARDS
    assert result["context_resolution"]["has_reference"] is False


def test_ordinal_reference_preserves_product_memory_and_sets_has_reference():
    """场景 3: '第二个多少钱' — 引用上轮推荐中的具体商品序号。"""
    result = resolve_turn_context(
        question="第二个多少钱",
        business_memory={"last_product_cards": TEXT_CARDS},
        conversation_history=[
            {"id": 1, "role": "assistant", "product_cards": TEXT_CARDS},
        ],
    )

    assert result["context_resolution"]["has_reference"] is True
    assert result["context_resolution"]["reference_source"] == "message_artifact"
    assert result["context_resolution"]["reference_message_id"] == 1
    assert result["context_resolution"]["needs_clarification"] is False
    # "第二个" 不是 "这两款"，所以 asks_for_two=False → selected = cards（全部）
    assert result["business_memory"]["last_product_cards"] == TEXT_CARDS
    assert result["business_memory"]["active_product_set"]["source_type"] == "recommendation"


def test_ordinal_reference_matches_singleton():
    """场景 3: '第一个适合什么肤质' — 单数序号仍触发指代。"""
    result = resolve_turn_context(
        question="第一个适合什么肤质",
        business_memory={"last_product_cards": TEXT_CARDS},
        conversation_history=[
            {"id": 1, "role": "assistant", "product_cards": TEXT_CARDS + [{"product_id": 13, "title": "旧推荐 C"}]},
        ],
    )

    assert result["context_resolution"]["has_reference"] is True
    assert result["context_resolution"]["needs_clarification"] is False


def test_context_query_without_reference_preserves_business_memory():
    """场景 3: '适合什么肤质'（无序号/指代词）— has_reference=False，business_memory 不丢失。"""
    result = resolve_turn_context(
        question="适合什么肤质",
        business_memory={"last_product_cards": IMAGE_CARDS},
        conversation_history=[{"id": 1, "role": "assistant", "product_cards": TEXT_CARDS}],
    )

    assert result["context_resolution"]["has_reference"] is False
    # 非指代性问题不会覆盖 business_memory
    assert result["business_memory"]["last_product_cards"] == IMAGE_CARDS
