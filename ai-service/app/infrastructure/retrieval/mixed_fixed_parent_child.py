"""Fixed parent-child records for general knowledge in the mixed experiment.

Product knowledge is deliberately not handled here: it keeps the v2.1
marketing/FAQ/review semantic units. This module is isolated from the older
all-document fixed parent-child builder so their historical indexes remain
reproducible.
"""
from __future__ import annotations

from typing import Any

from langchain_text_splitters import CharacterTextSplitter


PARENT_CHUNK_SIZE = 1000
PARENT_CHUNK_OVERLAP = 100
CHILD_CHUNK_SIZE = 500
CHILD_CHUNK_OVERLAP = 50
SEPARATOR = "\n\n"

PARENT_SPLITTER = CharacterTextSplitter(
    chunk_size=PARENT_CHUNK_SIZE,
    chunk_overlap=PARENT_CHUNK_OVERLAP,
    separator=SEPARATOR,
)
CHILD_SPLITTER = CharacterTextSplitter(
    chunk_size=CHILD_CHUNK_SIZE,
    chunk_overlap=CHILD_CHUNK_OVERLAP,
    separator=SEPARATOR,
)


def build_mixed_fixed_parent_child_records(
    doc_id: int,
    text: str,
    metadata: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build fixed ``1000/100 -> 500/50`` records for one general document."""
    parents: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []
    for parent_index, parent_content in enumerate(PARENT_SPLITTER.split_text(text)):
        parent_id = f"doc-{doc_id}:mfpc1-p-{parent_index:04d}"
        parents.append({
            "parent_id": parent_id,
            "doc_id": doc_id,
            "content": parent_content,
            **metadata,
        })
        for child_index, child_content in enumerate(CHILD_SPLITTER.split_text(parent_content)):
            children.append({
                "chunk_id": f"{parent_id}:c-{child_index:04d}",
                "parent_id": parent_id,
                "doc_id": doc_id,
                "child_index": child_index,
                "content": child_content,
                **metadata,
            })
    return parents, children
