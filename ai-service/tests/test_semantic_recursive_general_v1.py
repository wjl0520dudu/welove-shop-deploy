from scripts.ingest_knowledge_v2 import build_chunks_for_product as build_v21_product_chunks
from scripts.ingest_semantic_recursive_general_v1 import (
    build_general_recursive_chunks,
    build_product_semantic_chunks,
    compare_general_with_fixed,
)


def test_product_chunks_remain_the_v21_semantic_units():
    product = {
        "product_id": "p_beauty_001",
        "title": "Test serum",
        "brand": "Test brand",
        "sub_category": "serum",
        "rag_knowledge": {
            "marketing_description": "Hydrates and supports the skin barrier.",
            "official_faq": [{"question": "Can sensitive skin use it?", "answer": "Patch test first."}],
            "user_reviews": [
                {"nickname": "A", "rating": 5, "content": "Hydrating"},
                {"nickname": "B", "rating": 4, "content": "Absorbs fast"},
                {"nickname": "C", "rating": 5, "content": "Not sticky"},
            ],
        },
    }

    expected = build_v21_product_chunks(product, category_id=1, doc_id_seed=100001)
    actual = build_product_semantic_chunks(product, category_id=1)

    assert [chunk.content for chunk in actual] == [chunk.content for chunk in expected]
    assert [chunk.metadata.chunk_type for chunk in actual] == ["marketing", "faq", "review"]
    assert all(chunk.metadata.total_chunks == 3 for chunk in actual)
    assert all(chunk.metadata.index_version == "semantic_recursive_general_v1" for chunk in actual)


def test_general_recursive_chunks_have_single_layer_metadata():
    document = {
        "name": "General test",
        "category_id": 1,
        "content": "# Guide\n\n## First\n" + ("Evidence. " * 90),
    }

    chunks = build_general_recursive_chunks(document, 1)

    assert chunks
    assert [chunk.metadata.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.metadata.doc_id == 900001 for chunk in chunks)
    assert all(chunk.metadata.product_id == 0 for chunk in chunks)
    assert all(chunk.metadata.doc_type == "general_knowledge" for chunk in chunks)
    assert all(chunk.metadata.chunk_type == "general_recursive" for chunk in chunks)
    assert all(chunk.metadata.total_chunks == len(chunks) for chunk in chunks)
    assert all(chunk.metadata.content_hash for chunk in chunks)


def test_fixed_comparison_covers_all_general_documents():
    rows = compare_general_with_fixed()

    assert len(rows) == 8
    assert all({"fixed_count", "recursive_count", "matching_positions", "identical"} <= row.keys() for row in rows)
