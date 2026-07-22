"""DashScope qwen3-vl 多模态 embedding / rerank 封装。

设计目标：
- 图片向量和图文融合向量只服务 product_mm_v2 实验 collection；
- 图片相关错误（URL 无效、格式错误、DashScope 拒绝识别）抛
  `MultimodalImageError`，由 caller 决定"直接失败"还是"降级零向量继续"：
  - 接口层（用户查询）应 catch 抛出后返回 HTTP 400 让用户换图；
  - 同步脚本（批量灌数据）应 catch 后写入零向量 + 记日志，避免单张
    图挂了阻断整批。
- 非图片错误（API key 未配置、DashScope 服务性异常）继续走"降级零向量"
  路径，跟 rag.reranker 的降级策略一致，不阻塞主流程。
- rerank 调用失败时保持候选原顺序（跟 embedding 一样降级不抛）。

URL 归一化：
- PG.product.image_url 存的是 CDN 相对路径（/weloveshop/products/xxx.jpg）；
- DashScope multimodal 要求 HTTP/HTTPS 绝对 URL；
- 本模块所有入口在真正调 API 前统一走 `_normalize_image_url` 拼上 config.IMAGE_BASE_URL。
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any, Dict, List, Optional

import dashscope
from dashscope import MultiModalEmbedding, TextReRank

from app.infrastructure.config import config

logger = logging.getLogger("ai-service.rag.multimodal_embeddings")


class MultimodalImageError(Exception):
    """图片无法被多模态模型识别（URL 无效、404、格式错误等）。

    区别于"DashScope 服务性错误"（API key 未配置、网络异常等）：后者返回
    零向量降级，前者直接抛出让 caller 处理——因为图片本身有问题，重试
    再多次也不会成功。

    携带 `image_url`（归一化后的 URL） + `reason` 便于调用方日志或错误
    响应组装。
    """

    def __init__(self, image_url: str, reason: str):
        self.image_url = image_url
        self.reason = reason
        super().__init__(f"multimodal image invalid: {reason} url={image_url!r}")


# DashScope 返回的图片类错误 code / message 特征（用于分辨"图片错误" vs
# "服务性错误"）。命中任一即认为是图片问题。
_IMAGE_ERROR_CODES = {"InvalidParameter", "InvalidURL", "DataInspectionFailed"}
_IMAGE_ERROR_KEYWORDS = (
    "image url",
    "image is invalid",
    "url is invalid",
    "url or base64",
    "download",
    "unsupported image",
    "invalid image",
)


def _is_image_error(code: str, message: str) -> bool:
    """判断 DashScope 返回是不是图片本身的问题。"""
    code_s = (code or "").strip()
    msg_s = (message or "").lower()
    if code_s in _IMAGE_ERROR_CODES:
        return True
    return any(kw in msg_s for kw in _IMAGE_ERROR_KEYWORDS)


def _normalize_image_url(image_url: str | None) -> str | None:
    """把相对路径的图片地址拼成 DashScope 认可的绝对 URL。

    规则：
    - 空/None：原样返回（调用方会拿零向量兜底）；
    - 已经是 http:// 或 https:// 开头：原样返回；
    - 相对路径（以 / 或 无前缀）：拼 config.IMAGE_BASE_URL。
    """
    if not image_url:
        return image_url
    url = str(image_url).strip()
    if not url:
        return None
    lower = url.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return url

    base = (config.IMAGE_BASE_URL or "").rstrip("/")
    if not base:
        logger.warning("IMAGE_BASE_URL 未配置，相对路径 %r 无法拼成绝对 URL", url)
        return url

    path = url if url.startswith("/") else "/" + url
    return f"{base}{path}"


def zero_image_vector() -> list[float]:
    """返回 image_vector 的零向量。"""
    return [0.0] * int(config.MILVUS_IMAGE_DIM)


def zero_multimodal_vector() -> list[float]:
    """返回 multimodal_vector 的零向量。"""
    return [0.0] * int(config.MILVUS_MULTIMODAL_DIM)


def _resp_output(resp: Any) -> Any:
    """兼容 DashScope response 的 dict / 属性两种访问方式。"""
    if isinstance(resp, dict):
        return resp.get("output") or {}
    return getattr(resp, "output", None) or {}


def _output_get(output: Any, key: str, default: Any = None) -> Any:
    if isinstance(output, dict):
        return output.get(key, default)
    return getattr(output, key, default)


def _fit_vector(vector: Any, dim: int) -> list[float]:
    """把 SDK 返回值整理成指定维度的 list[float]。"""
    if not isinstance(vector, list):
        return [0.0] * dim
    out = [float(x or 0.0) for x in vector[:dim]]
    if len(out) < dim:
        out.extend([0.0] * (dim - len(out)))
    return out


def _extract_first_embedding(resp: Any, dim: int) -> list[float]:
    output = _resp_output(resp)
    embeddings = _output_get(output, "embeddings", []) or []
    if not embeddings:
        return [0.0] * dim

    first = embeddings[0]
    if isinstance(first, dict):
        return _fit_vector(first.get("embedding"), dim)
    return _fit_vector(getattr(first, "embedding", None), dim)


def _append_source(item: dict, source: str) -> None:
    srcs = item.setdefault("recall_sources", [])
    if source not in srcs:
        srcs.append(source)


class DashScopeMultimodalEmbeddings:
    """qwen3-vl embedding + rerank 客户端。

    多模态链路是实验能力，因此初始化不因为缺少 key 抛异常；
    真正调用时降级并写日志，避免影响 v2 文本侧召回。
    """

    def __init__(
        self,
        api_key: str | None = None,
        embedding_model: str | None = None,
        rerank_model: str | None = None,
        image_dim: int | None = None,
        multimodal_dim: int | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key if api_key is not None else config.DASH_SCOPE_API_KEY
        self.embedding_model = embedding_model or config.DASH_SCOPE_MULTI_MODAL_EMBEDDING_MODEL
        self.rerank_model = rerank_model or config.DASH_SCOPE_MULTI_MODAL_RERANK_MODEL
        self.image_dim = int(image_dim or config.MILVUS_IMAGE_DIM)
        self.multimodal_dim = int(multimodal_dim or config.MILVUS_MULTIMODAL_DIM)
        self.base_url = base_url if base_url is not None else config.DASHSCOPE_MAAS_BASE_URL

    def _configure_sdk(self) -> None:
        if self.api_key:
            dashscope.api_key = self.api_key
        if self.base_url:
            dashscope.base_http_api_url = self.base_url

    def embed_image(self, image_url: str | None) -> list[float]:
        """纯图片 embedding → image_vector。

        返回值 / 抛出行为：
        - image_url 为空 / api_key 未配置 → 返回零向量（不视为错误）
        - DashScope 返回图片类错误 → 抛 MultimodalImageError
        - 其他异常（网络、超时、服务不可用）→ 记日志、返回零向量（降级）
        """
        image_url = _normalize_image_url(image_url)
        if not image_url:
            return [0.0] * self.image_dim
        if not self.api_key:
            logger.warning("DASH_SCOPE_API_KEY 未配置，image embedding 返回零向量")
            return [0.0] * self.image_dim

        self._configure_sdk()
        try:
            resp = MultiModalEmbedding.call(
                model=self.embedding_model,
                input=[{"image": image_url}],
                api_key=self.api_key,
                dimension=self.image_dim,
            )
            if getattr(resp, "status_code", None) != HTTPStatus.OK:
                code = str(getattr(resp, "code", "") or "")
                message = str(getattr(resp, "message", "") or "")
                if _is_image_error(code, message):
                    raise MultimodalImageError(image_url, f"{code}: {message}")
                logger.warning(
                    "image embedding 调用失败（服务性错误，降级零向量）: "
                    "status=%s code=%s message=%s",
                    getattr(resp, "status_code", ""), code, message,
                )
                return [0.0] * self.image_dim
            return _extract_first_embedding(resp, self.image_dim)
        except MultimodalImageError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("image embedding 异常，返回零向量：%s", e)
            return [0.0] * self.image_dim

    def embed_fusion(self, text: str | None, image_url: str | None) -> list[float]:
        """图文融合 embedding → multimodal_vector。

        返回值 / 抛出行为（跟 embed_image 对齐）：
        - image_url 为空 / api_key 未配置 → 返回零向量
        - DashScope 返回图片类错误 → 抛 MultimodalImageError
        - 其他异常 → 记日志、返回零向量（降级）
        """
        image_url = _normalize_image_url(image_url)
        if not image_url:
            return [0.0] * self.multimodal_dim
        if not self.api_key:
            logger.warning("DASH_SCOPE_API_KEY 未配置，fusion embedding 返回零向量")
            return [0.0] * self.multimodal_dim

        self._configure_sdk()
        inputs: list[dict[str, str]] = []
        if text and text.strip():
            inputs.append({"text": text.strip()})
        inputs.append({"image": image_url})

        try:
            resp = MultiModalEmbedding.call(
                model=self.embedding_model,
                input=inputs,
                api_key=self.api_key,
                dimension=self.multimodal_dim,
                enable_fusion=True,
            )
            if getattr(resp, "status_code", None) != HTTPStatus.OK:
                code = str(getattr(resp, "code", "") or "")
                message = str(getattr(resp, "message", "") or "")
                if _is_image_error(code, message):
                    raise MultimodalImageError(image_url, f"{code}: {message}")
                logger.warning(
                    "fusion embedding 调用失败（服务性错误，降级零向量）: "
                    "status=%s code=%s message=%s",
                    getattr(resp, "status_code", ""), code, message,
                )
                return [0.0] * self.multimodal_dim
            return _extract_first_embedding(resp, self.multimodal_dim)
        except MultimodalImageError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("fusion embedding 异常，返回零向量：%s", e)
            return [0.0] * self.multimodal_dim

    def multimodal_rerank(
        self,
        query_text: str,
        query_image_url: str | None,
        documents: List[Dict[str, Any]],
        top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """qwen3-vl-rerank 精排。失败时返回原顺序。"""
        if not documents:
            return []

        n = top_n if top_n is not None else len(documents)
        if not self.api_key:
            logger.warning("DASH_SCOPE_API_KEY 未配置，multimodal rerank 退回原顺序")
            return [dict(d) for d in documents[:n]]

        query: dict[str, str] = {}
        if query_text and query_text.strip():
            query["text"] = query_text.strip()
        normalized_query_image = _normalize_image_url(query_image_url)
        if normalized_query_image:
            query["image"] = normalized_query_image
        if not query:
            return [dict(d) for d in documents[:n]]

        doc_inputs: list[dict[str, str]] = []
        for doc in documents:
            parts = [
                str(doc.get("title") or ""),
                str(doc.get("brand") or ""),
                str(doc.get("tags") or ""),
                str(doc.get("description") or "")[:800],
            ]
            text = " ".join(p.strip() for p in parts if p and p.strip())
            item: dict[str, str] = {}
            if text:
                item["text"] = text
            image_url = _normalize_image_url(str(doc.get("image_url") or "").strip())
            if image_url:
                item["image"] = image_url
            doc_inputs.append(item or {"text": str(doc.get("product_id") or "")})

        self._configure_sdk()
        try:
            resp = TextReRank.call(
                model=self.rerank_model,
                query=query,
                documents=doc_inputs,
                top_n=n,
                return_documents=False,
                api_key=self.api_key,
            )
            if getattr(resp, "status_code", None) != HTTPStatus.OK:
                logger.warning(
                    "multimodal rerank 调用失败: status=%s code=%s message=%s，退回原顺序",
                    getattr(resp, "status_code", ""),
                    getattr(resp, "code", ""),
                    getattr(resp, "message", ""),
                )
                return [dict(d) for d in documents[:n]]

            output = _resp_output(resp)
            results = _output_get(output, "results", []) or []
            reranked: list[dict[str, Any]] = []
            for r in results:
                idx = r.get("index") if isinstance(r, dict) else getattr(r, "index", None)
                score = (
                    r.get("relevance_score") if isinstance(r, dict)
                    else getattr(r, "relevance_score", None)
                )
                if idx is None or score is None:
                    continue
                idx = int(idx)
                if not 0 <= idx < len(documents):
                    continue
                item = dict(documents[idx])
                item["rerank_score"] = float(score)
                item["score"] = float(score)
                _append_source(item, "multimodal_rerank")
                reranked.append(item)

            if not reranked:
                logger.warning("multimodal rerank 返回空结果，退回原顺序")
                return [dict(d) for d in documents[:n]]
            return reranked[:n]
        except Exception as e:  # noqa: BLE001
            logger.warning("multimodal rerank 异常，退回原顺序：%s", e)
            return [dict(d) for d in documents[:n]]


_multimodal_embeddings_instance: DashScopeMultimodalEmbeddings | None = None


def get_multimodal_embeddings() -> DashScopeMultimodalEmbeddings:
    """懒加载单例多模态客户端。"""
    global _multimodal_embeddings_instance
    if _multimodal_embeddings_instance is None:
        _multimodal_embeddings_instance = DashScopeMultimodalEmbeddings()
    return _multimodal_embeddings_instance


def embed_image(image_url: str | None) -> list[float]:
    return get_multimodal_embeddings().embed_image(image_url)


def embed_fusion(text: str | None, image_url: str | None) -> list[float]:
    return get_multimodal_embeddings().embed_fusion(text, image_url)


def multimodal_rerank(
    query_text: str,
    query_image_url: str | None,
    documents: List[Dict[str, Any]],
    top_n: Optional[int] = None,
) -> List[Dict[str, Any]]:
    return get_multimodal_embeddings().multimodal_rerank(
        query_text=query_text,
        query_image_url=query_image_url,
        documents=documents,
        top_n=top_n,
    )
