from scripts.ingest_semantic_v1 import (
    build_product_semantic_chunks,
    build_general_topic_chunks,
    split_general_topic_chunks,
)
from scripts.ingest_knowledge_v2 import build_chunks_for_product as build_v21_product_chunks


def test_topic_splitter_keeps_complete_h2_topics_with_document_context():
    content = """# 护肤指南

## 敏感肌护理
- 精简护肤
- 注意保湿

## 防晒建议
- 日常选 SPF30
"""

    chunks = split_general_topic_chunks(content, "护肤知识-测试")

    assert len(chunks) == 2
    assert all(chunk.startswith("【通用知识】护肤指南") for chunk in chunks)
    assert "## 敏感肌护理" in chunks[0]
    assert "## 防晒建议" in chunks[1]


def test_topic_splitter_preserves_document_preamble():
    content = """# 护肤指南

本指南适用于日常基础护理。

## 敏感肌护理
- 精简护肤
"""

    chunks = split_general_topic_chunks(content, "护肤知识-测试")

    assert len(chunks) == 1
    assert "本指南适用于日常基础护理。" in chunks[0]
    assert "## 敏感肌护理" in chunks[0]


def test_long_topic_splits_only_at_complete_h3_subtopics():
    content = """# 手机指南

## 按需求选手机
### 拍照优先
关注传感器、光学防抖和长焦镜头。拍照效果还与算法有关。
### 游戏优先
关注处理器性能、散热系统和高刷新率屏幕。游戏时需要稳定帧率。
"""

    chunks = split_general_topic_chunks(content, "数码知识-测试", max_chars=100)

    assert len(chunks) == 2
    assert all("【通用知识】手机指南" in chunk for chunk in chunks)
    assert all("## 按需求选手机" in chunk for chunk in chunks)
    assert "### 拍照优先" in chunks[0]
    assert "### 游戏优先" in chunks[1]


def test_general_topic_chunks_preserve_single_layer_metadata():
    document = {
        "name": "护肤知识-测试",
        "category_id": 1,
        "content": "# 护肤指南\n\n## 保湿\n- 使用保湿产品\n\n## 防晒\n- 白天注意防晒\n",
    }

    chunks = build_general_topic_chunks(document, 1)

    assert len(chunks) == 2
    assert [chunk.metadata.chunk_index for chunk in chunks] == [0, 1]
    assert all(chunk.metadata.doc_id == 900001 for chunk in chunks)
    assert all(chunk.metadata.product_id == 0 for chunk in chunks)
    assert all(chunk.metadata.doc_type == "general_knowledge" for chunk in chunks)
    assert all(chunk.metadata.chunk_type == "general_topic" for chunk in chunks)
    assert all(chunk.metadata.total_chunks == 2 for chunk in chunks)
    assert all(chunk.metadata.content_hash for chunk in chunks)


def test_product_semantic_chunks_keep_v21_content_units():
    product = {
        "product_id": "p_beauty_001",
        "title": "测试精华",
        "brand": "测试品牌",
        "sub_category": "精华",
        "rag_knowledge": {
            "marketing_description": "主打保湿修护。",
            "official_faq": [{"question": "敏感肌能用吗？", "answer": "建议先局部试用。"}],
            "user_reviews": [
                {"nickname": "A", "rating": 5, "content": "保湿不错"},
                {"nickname": "B", "rating": 4, "content": "吸收很快"},
                {"nickname": "C", "rating": 5, "content": "不会黏腻"},
            ],
        },
    }

    expected = build_v21_product_chunks(product, category_id=1, doc_id_seed=100001)
    actual = build_product_semantic_chunks(product, category_id=1)

    assert [chunk.content for chunk in actual] == [chunk.content for chunk in expected]
    assert [chunk.metadata.chunk_type for chunk in actual] == ["marketing", "faq", "review"]
    assert all(chunk.metadata.total_chunks == 3 for chunk in actual)
    assert all(chunk.metadata.index_version == "semantic_v1" for chunk in actual)
