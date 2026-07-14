from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from chains.rag_qa_chain import ask_with_rag
from rag.document_pipeline import DocumentIngestionService
from rag.models import ParseRequest, RetrievalPlan
from rag.retriever import get_retriever
from rag.vector_store import create_vector_store

router = APIRouter(prefix="/api/rag", tags=["rag"])

vector_store = create_vector_store()
ingestion_service = DocumentIngestionService(vector_store)


@router.post("/parse")
async def parse_document(request: ParseRequest) -> Dict[str, Any]:
    try:
        return ingestion_service.ingest(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文档解析失败: {exc}") from exc


@router.post("/search")
async def search(plan: RetrievalPlan) -> Dict[str, Any]:
    output = get_retriever().retrieve(plan)
    return {
        "documents": [
            {
                "content": item.content,
                "score": item.score,
                "metadata": item.metadata.dict(),
            }
            for item in output.results
        ],
        "sources": [source.dict() for source in output.sources],
        "knowledge_context": output.knowledge_context,
        "count": len(output.results),
    }


@router.post("/ask")
async def ask(plan: RetrievalPlan) -> Dict[str, Any]:
    return ask_with_rag(plan)


@router.get("/stats")
async def stats() -> Dict[str, Any]:
    return vector_store.stats()


# ================ admin 知识库管理接口 ================

@router.post("/admin/parse")
async def admin_parse(body: Dict[str, Any]) -> Dict[str, Any]:
    """管理员上传知识库文档(从 URL 下载),解析后灌入向量库。

    请求体:
        download_url (str): 文档下载 URL
        doc_id (int): 知识库文档 ID(knowledge_doc.id)
        title (str, optional): 文档标题
        doc_type (str, optional): 文档类型,默认 "md"
        category_id (int, optional): 分类 ID
    """
    download_url = body.get("download_url")
    doc_id = body.get("doc_id")
    if not download_url or not doc_id:
        raise HTTPException(status_code=400, detail="download_url 和 doc_id 为必填")
    try:
        result = await ingestion_service.ingest_from_url(
            download_url=download_url,
            doc_id=int(doc_id),
            title=body.get("title", ""),
            doc_type=body.get("doc_type", "md"),
            category_id=body.get("category_id"),
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文档解析失败: {exc}") from exc


@router.post("/admin/delete")
async def admin_delete(body: Dict[str, Any]) -> Dict[str, Any]:
    """删除知识库文档的向量数据。

    请求体:
        doc_id (int): 知识库文档 ID(knowledge_doc.id)
    """
    doc_id = body.get("doc_id")
    if doc_id is None:
        raise HTTPException(status_code=400, detail="doc_id 为必填")
    try:
        deleted = ingestion_service.delete_by_doc_id(int(doc_id))
        return {"status": "success", "doc_id": doc_id, "deleted_count": deleted}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除失败: {exc}") from exc