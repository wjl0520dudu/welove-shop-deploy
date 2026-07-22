"""Recursive text chunking for the recursive_v1 RAG experiment.

This module provides an alternative chunking strategy using LangChain's
RecursiveCharacterTextSplitter, which respects hierarchical separators
(paragraphs → sentences → words) rather than blindly cutting at a fixed
character count.

Used ONLY for the knowledge_recursive_v1 Milvus collection experiment.
Must not be imported by production code paths.
"""

from __future__ import annotations

import hashlib
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.domain.knowledge.models import ChunkMetadata, DocumentChunk


# ---------------------------------------------------------------------------
# Recursive splitter configuration (experiment-fixed: chunk_size=500, overlap=50)
# ---------------------------------------------------------------------------
_RECURSIVE_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    # separators in priority order — splitter tries earlier ones first, falls back
    separators=[
        "\n\n",      # 1. Double newline = paragraph boundary (most preferred)
        "\n",        # 2. Single newline = line break
        "。",        # 3. Chinese full stop
        "；",        # 4. Chinese semicolon
        "，",        # 5. Chinese comma
        ". ",        # 6. English sentence
        " ",         # 7. Word boundary
        "",          # 8. Raw character (last resort)
    ],
    keep_separator=False,
    is_separator_regex=False,
)


def split_recursive_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    """Split text using recursive character splitting.

    Unlike the fixed CharacterTextSplitter (which only splits on the configured
    separator), RecursiveCharacterTextSplitter tries higher-level separators
    first, producing more semantically coherent chunks.

    Args:
        text: Raw input text.
        chunk_size: Maximum characters per chunk (default 500).
        chunk_overlap: Character overlap between adjacent chunks (default 50).

    Returns:
        List of text chunks.
    """
    if not text or not text.strip():
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n\n",
            "\n",
            "。",
            "；",
            "，",
            ". ",
            " ",
            "",
        ],
        keep_separator=False,
        is_separator_regex=False,
    )
    return splitter.split_text(text.strip())


def build_recursive_chunks_from_text(
    text: str,
    doc_id: int,
    title: str = "",
    doc_type: str = "text",
    category_id: int | None = None,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> List[DocumentChunk]:
    """Build DocumentChunk list from raw text using recursive splitting.

    This is the canonical entry point for the recursive_v1 experiment.
    It produces chunks identical in shape to those from document_pipeline.py
    so that the rest of the retrieval pipeline (retriever, reranker, prompts)
    requires no changes.

    Args:
        text: Raw document text.
        doc_id: Document identifier (maps to Milvus doc_id field).
        title: Document title (used in ChunkMetadata.title).
        doc_type: Document type (default "text").
        category_id: Optional category identifier.
        chunk_size: Maximum chunk size in characters.
        chunk_overlap: Overlap between adjacent chunks.

    Returns:
        List of DocumentChunk objects ready for Milvus upsert.
    """
    parts = split_recursive_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    total = len(parts)
    source = title or f"doc_{doc_id}.md"

    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    chunks: List[DocumentChunk] = []
    for idx, content in enumerate(parts):
        chunks.append(
            DocumentChunk(
                content=content,
                metadata=ChunkMetadata(
                    doc_id=doc_id,
                    source=source,
                    title=title or f"doc_{doc_id}",
                    doc_type=doc_type,
                    chunk_type="text",
                    category_id=category_id,
                    chunk_index=idx,
                    total_chunks=total,
                    content_hash=_hash(content),
                ),
            )
        )
    return chunks
