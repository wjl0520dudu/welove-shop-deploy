"""Schema-constrained, low-cost knowledge retrieval planning.

Rules cover stable vocabulary first.  The returned plan contains business
fields only; ``vector_store.build_metadata_filter`` remains the sole place
where those fields become a Milvus expression.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.knowledge.models import MetadataFilter, RetrievalPlan


class KnowledgeQueryPlan(BaseModel):
    rewritten_query: str
    hard_filters: MetadataFilter = Field(default_factory=MetadataFilter)
    soft_terms: list[str] = Field(default_factory=list)
    normalized_terms: list[str] = Field(default_factory=list)
    planner_source: str = "rule"


_TERM_ALIASES = {
    "a醇": "视黄醇", "retinol": "视黄醇", "烟酰安": "烟酰胺",
    "vc": "维生素C", "防晒霜": "防晒", "卸妆水": "卸妆",
}
_DOC_TYPE_TERMS = {"退换货": "policy", "售后": "policy", "说明书": "manual", "常见问题": "faq", "faq": "faq"}


def plan_knowledge_query(query: str, *, top_k: int = 5, search_mode: str = "hybrid", use_rerank: bool = True) -> tuple[RetrievalPlan, KnowledgeQueryPlan]:
    raw = (query or "").strip()
    lowered = raw.lower()
    normalized: list[str] = []
    rewritten = raw
    for alias, canonical in _TERM_ALIASES.items():
        if alias in lowered:
            rewritten = rewritten.replace(alias, canonical).replace(alias.upper(), canonical)
            normalized.append(canonical)

    doc_types = [doc_type for term, doc_type in _DOC_TYPE_TERMS.items() if term in lowered]
    hard = MetadataFilter(doc_types=list(dict.fromkeys(doc_types)) or None)
    soft_terms = [term for term in ("敏感肌", "油皮", "干皮", "夏天", "孕妇") if term in raw]
    plan = RetrievalPlan(
        query=rewritten or raw,
        top_k=top_k,
        search_mode=search_mode if search_mode in {"hybrid", "dense", "bm25", "sparse"} else "hybrid",
        use_rerank=bool(use_rerank),
        doc_types=hard.doc_types or [],
    )
    return plan, KnowledgeQueryPlan(
        rewritten_query=plan.query, hard_filters=hard, soft_terms=soft_terms,
        normalized_terms=list(dict.fromkeys(normalized)),
    )
