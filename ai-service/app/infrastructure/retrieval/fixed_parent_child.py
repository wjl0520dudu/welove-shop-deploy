"""Fixed-size parent-child chunk construction for the isolated experiment.

This module intentionally does not alter ``parent_child.py``.  The latter is
the v2.3 recursive parent-child implementation; this module is the separately
versioned fixed-size alternative used by ``fixed_parent_child_v1``.
"""
from __future__ import annotations

from typing import Any

from langchain_text_splitters import CharacterTextSplitter


PARENT_CHUNK_SIZE = 800
PARENT_CHUNK_OVERLAP = 100
CHILD_CHUNK_SIZE = 400
CHILD_CHUNK_OVERLAP = 60
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


def build_fixed_parent_child_records(
    doc_id: int,
    text: str,
    metadata: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build fixed-size parent and child records for one source document.

    Parents are first split by the v2.1-compatible ``CharacterTextSplitter``.
    Each parent is then split independently into children.  Child IDs are
    stable within a parent and use a distinct versioned prefix so this index
    cannot be confused with v2.3 recursive parent-child records.
    """
    parents: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []
    for parent_index, parent_content in enumerate(PARENT_SPLITTER.split_text(text)):
        parent_id = f"doc-{doc_id}:fpc1-p-{parent_index:04d}"
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
