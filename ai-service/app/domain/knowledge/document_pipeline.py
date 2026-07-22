from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import List

from langchain_text_splitters import CharacterTextSplitter

from app.infrastructure.config import config
from app.domain.knowledge.models import ChunkMetadata, DocumentChunk, ParseRequest


def load_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = path.suffix.lower()
    if ext not in {".txt", ".md"}:
        raise ValueError(f"Unsupported file type in first pass: {ext}")

    return path.read_text(encoding="utf-8")


async def download_text(download_url: str) -> str:
    """从 URL 下载文本内容。支持 txt / md 文件。"""
    import httpx
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(download_url, follow_redirects=True)
        resp.raise_for_status()
        content = resp.text
        if not content or not content.strip():
            raise ValueError(f"Downloaded content is empty: {download_url}")
        return content


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def split_text(text: str, chunk_size: int | None = None, chunk_overlap: int | None = None) -> List[str]:
    chunk_size = chunk_size or config.CHUNK_SIZE
    chunk_overlap = chunk_overlap or config.CHUNK_OVERLAP

    text = clean_text(text)
    if not text:
        return []

    text_splitter = CharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separator="\n\n",
    )
    return text_splitter.split_text(text)


def build_chunks(request: ParseRequest) -> List[DocumentChunk]:
    raw_text = load_text(request.file_path)
    return _build_chunks_from_text(raw_text, request)


def build_chunks_from_text(text: str, doc_id: int, title: str = "",
                            doc_type: str = "text", category_id: int | None = None) -> List[DocumentChunk]:
    """从文本内容直接构建 chunk，不依赖文件系统。"""
    from app.domain.knowledge.models import ParseRequest
    req = ParseRequest(
        file_path=title or f"doc_{doc_id}.md",
        doc_id=doc_id,
        title=title,
        doc_type=doc_type,
        category_id=category_id,
    )
    return _build_chunks_from_text(text, req)


def _build_chunks_from_text(raw_text: str, request: ParseRequest) -> List[DocumentChunk]:
    # Parent-child is behind a feature flag because enabling it requires the
    # corresponding Milvus schema/reindex migration.  The construction is kept
    # here so ingestion and retrieval share one canonical chunk identity.
    if config.RAG_PARENT_CHILD_ENABLED:
        from app.infrastructure.retrieval.parent_child import build_parent_child_records
        cleaned = clean_text(raw_text)
        source = request.file_path or request.title or f"doc_{request.doc_id}.md"
        parents, children = build_parent_child_records(request.doc_id, cleaned, {
            "source": source, "title": request.title or os.path.basename(source),
            "doc_type": request.doc_type, "category_id": request.category_id,
        })
        parent_chunks = [DocumentChunk(content=parent["content"], metadata=ChunkMetadata(
            doc_id=request.doc_id, source=source, title=request.title or os.path.basename(source),
            doc_type=request.doc_type, chunk_type="parent", category_id=request.category_id,
            chunk_index=index, total_chunks=len(parents), content_hash=hash_content(parent["content"]),
            parent_id=parent["parent_id"], child_index=0, index_version="parent_child_v1",
        )) for index, parent in enumerate(parents)]
        child_chunks = [DocumentChunk(content=child["content"], metadata=ChunkMetadata(
            doc_id=request.doc_id, source=source, title=request.title or os.path.basename(source),
            doc_type=request.doc_type, chunk_type="child", category_id=request.category_id,
            chunk_index=index, total_chunks=len(children), content_hash=hash_content(child["content"]),
            parent_id=child["parent_id"], child_index=child["child_index"], index_version="parent_child_v1",
        )) for index, child in enumerate(children)]
        return parent_chunks + child_chunks
    parts = split_text(raw_text)
    total = len(parts)
    source = request.file_path or request.title or f"doc_{request.doc_id}.md"

    chunks: List[DocumentChunk] = []
    for index, content in enumerate(parts):
        chunks.append(
            DocumentChunk(
                content=content,
                metadata=ChunkMetadata(
                    doc_id=request.doc_id,
                    source=source,
                    title=request.title or os.path.basename(source) if source else f"doc_{request.doc_id}",
                    doc_type=request.doc_type,
                    chunk_type="text",
                    category_id=request.category_id,
                    chunk_index=index,
                    total_chunks=len(parts),
                    content_hash=hash_content(content),
                ),
            )
        )
    return chunks


class DocumentIngestionService:
    def __init__(self, vector_store):
        self.vector_store = vector_store

    def ingest(self, request: ParseRequest) -> dict:
        chunks = build_chunks(request)
        inserted = self.vector_store.upsert_chunks(chunks)
        return {
            "status": "success",
            "doc_id": request.doc_id,
            "chunks_count": len(chunks),
            "inserted_count": inserted,
        }

    async def ingest_from_url(self, download_url: str, doc_id: int, title: str = "",
                                doc_type: str = "text", category_id: int | None = None) -> dict:
        """从 URL 下载文档并灌入向量库。"""
        text = await download_text(download_url)
        chunks = build_chunks_from_text(text, doc_id=doc_id, title=title,
                                         doc_type=doc_type, category_id=category_id)
        inserted = self.vector_store.upsert_chunks(chunks)
        return {
            "status": "success",
            "doc_id": doc_id,
            "chunks_count": len(chunks),
            "inserted_count": inserted,
        }

    def delete_by_doc_id(self, doc_id: int) -> dict:
        return self.vector_store.delete_by_doc_id(doc_id)
