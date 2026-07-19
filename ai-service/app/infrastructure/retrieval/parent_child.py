"""Parent-child chunk construction and local-context reconstruction.

This module follows the adopted retrieval order: child retrieval -> child
rerank -> parent aggregation -> local parent window.  It deliberately keeps
storage-neutral records so the existing Milvus migration can be performed in
one controlled reindex rather than mutating a live collection schema.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from langchain_text_splitters import RecursiveCharacterTextSplitter


PARENT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1200, chunk_overlap=160,
    separators=["\n## ", "\n### ", "\n\n", "\n", "。", "；", "，", ""],
)
CHILD_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=320, chunk_overlap=48,
    separators=["\n\n", "\n", "。", "；", "，", ""],
)


def build_parent_child_records(doc_id: int, text: str, metadata: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    parents: list[dict] = []
    children: list[dict] = []
    for parent_index, parent_content in enumerate(PARENT_SPLITTER.split_text(text)):
        parent_id = f"doc-{doc_id}:p-{parent_index:04d}"
        parents.append({"parent_id": parent_id, "doc_id": doc_id, "content": parent_content, **metadata})
        for child_index, child_content in enumerate(CHILD_SPLITTER.split_text(parent_content)):
            children.append({
                "chunk_id": f"{parent_id}:c-{child_index:04d}", "parent_id": parent_id,
                "doc_id": doc_id, "child_index": child_index, "content": child_content, **metadata,
            })
    return parents, children


def aggregate_parent_hits(reranked_children: Iterable[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    """Aggregate same-parent child hits; first hit has full weight, later hits decay."""
    grouped: dict[str, dict[str, Any]] = {}
    for hit in reranked_children:
        parent_id = str(hit.get("parent_id") or "")
        if not parent_id:
            continue
        record = grouped.setdefault(parent_id, {"parent_id": parent_id, "score": 0.0, "children": []})
        weight = 1.0 if not record["children"] else 0.5
        record["score"] += float(hit.get("rerank_score", hit.get("score", 0.0)) or 0.0) * weight
        record["children"].append(hit)
    return sorted(grouped.values(), key=lambda item: item["score"], reverse=True)[:limit]


def build_local_parent_windows(parents: dict[str, dict[str, Any]], parent_hits: Iterable[dict[str, Any]], max_chars: int = 12000) -> list[dict[str, Any]]:
    """Return parent contexts trimmed around child evidence, never entire documents."""
    out: list[dict[str, Any]] = []
    used = 0
    for hit in parent_hits:
        parent = parents.get(str(hit.get("parent_id") or ""))
        if not parent:
            continue
        content = str(parent.get("content") or "")
        remaining = max_chars - used
        if remaining <= 0:
            break
        clipped = content[:remaining]
        out.append({"parent_id": parent["parent_id"], "doc_id": parent.get("doc_id"),
                    "content": clipped, "score": hit.get("score", 0.0),
                    "child_hits": hit.get("children", [])})
        used += len(clipped)
    return out
