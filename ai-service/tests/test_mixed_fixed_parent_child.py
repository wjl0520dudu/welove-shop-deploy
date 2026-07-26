from unittest.mock import MagicMock

from app.domain.knowledge.models import ChunkMetadata, RetrievalPlan, SearchResult
from app.infrastructure.config import config
from app.infrastructure.retrieval.mixed_fixed_parent_child import (
    CHILD_CHUNK_OVERLAP,
    CHILD_CHUNK_SIZE,
    PARENT_CHUNK_OVERLAP,
    PARENT_CHUNK_SIZE,
    build_mixed_fixed_parent_child_records,
)
from app.infrastructure.retrieval.retriever import Retriever


def test_general_fixed_parent_child_records_use_the_requested_sizes_and_mapping():
    text = "\n\n".join(
        f"section {index}: " + ("evidence " * 90)
        for index in range(1, 8)
    )
    parents, children = build_mixed_fixed_parent_child_records(900001, text, {"source": "test"})

    assert (PARENT_CHUNK_SIZE, PARENT_CHUNK_OVERLAP) == (1000, 100)
    assert (CHILD_CHUNK_SIZE, CHILD_CHUNK_OVERLAP) == (500, 50)
    assert parents and children
    parent_ids = {parent["parent_id"] for parent in parents}
    assert all(parent_id.startswith("doc-900001:mfpc1-p-") for parent_id in parent_ids)
    assert all(child["parent_id"] in parent_ids for child in children)
    for parent_id in parent_ids:
        indices = [child["child_index"] for child in children if child["parent_id"] == parent_id]
        assert indices == list(range(len(indices)))


def test_mixed_retriever_keeps_product_units_and_reconstructs_general_parent(monkeypatch):
    monkeypatch.setattr(config, "RAG_PARENT_CHILD_ENABLED", True)
    monkeypatch.setattr(config, "RAG_PARENT_CHILD_GENERAL_ONLY", True)

    product = SearchResult(
        content="product marketing unit",
        metadata=ChunkMetadata(
            doc_id=100001,
            doc_type="product_knowledge",
            chunk_type="marketing",
            parent_id="",
            title="Product",
        ),
        score=0.9,
    )
    child = SearchResult(
        content="general child evidence",
        metadata=ChunkMetadata(
            doc_id=900001,
            doc_type="general_knowledge",
            chunk_type="child",
            parent_id="doc-900001:mfpc1-p-0000",
            child_index=0,
            title="General",
        ),
        score=0.8,
    )
    parent = SearchResult(
        content="general parent context",
        metadata=ChunkMetadata(
            doc_id=900001,
            doc_type="general_knowledge",
            chunk_type="parent",
            parent_id="doc-900001:mfpc1-p-0000",
            title="General",
        ),
    )
    store = MagicMock()
    store.search.return_value = [product, child]
    store.get_parent_chunks.return_value = [parent]
    reranker = MagicMock()
    reranker.rerank.return_value = [(0, 0.9), (1, 0.8)]

    output = Retriever(vector_store=store, reranker=reranker).retrieve(
        RetrievalPlan(query="test", top_k=2, initial_top_k=2)
    )

    request = store.search.call_args.args[0]
    assert request.filter.chunk_types == ["child", "marketing", "faq", "review"]
    assert [item.content for item in output.results] == ["product marketing unit", "general child evidence"]
    assert "product marketing unit" in output.knowledge_context
    assert "general parent context" in output.knowledge_context
