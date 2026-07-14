from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import Field

from api.response_adapter import build_error_response, normalize_ai_response
from api.schemas import AIResponse, ChatRequest
from assistant.graph import AssistantGraph
from core.errors import ErrorCode
from core.llm import get_llm


router = APIRouter(prefix="/api/assistant", tags=["assistant"])
logger = logging.getLogger("ai-service.assistant")


class AssistantRunRequest(ChatRequest):
    # 购物车写操作已交给前端，这些字段保留兼容旧调用方，不再被 graph 消费。
    confirmed: bool = Field(False, description="[deprecated] 购物车操作改由前端直接处理")
    cart_action: Optional[str] = Field(None, description="[deprecated] 不再由 Agent 处理")
    product_id: Optional[int] = Field(None, description="[deprecated] 不再由 Agent 处理")
    sku_id: Optional[int] = Field(None, description="[deprecated] 不再由 Agent 处理")
    cart_item_id: Optional[int] = Field(None, description="[deprecated] 不再由 Agent 处理")
    quantity: int = Field(1, ge=1, description="[deprecated] 不再由 Agent 处理")


def _parse_user_id(value: Optional[str]) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@router.post("/run", response_model=AIResponse)
async def run_assistant(request: AssistantRunRequest, http_request: Request) -> AIResponse:
    llm = get_llm()
    # 优先复用中间件生成/透传的 traceId；没有则新建（防御性，正常不会走到）
    trace_id = getattr(http_request.state, "trace_id", None) or str(uuid4())
    if llm is None:
        return build_error_response(
            "LLM 未配置，统一 Agent 暂不可用。",
            trace_id=trace_id,
            error_code=ErrorCode.LLM_NOT_CONFIGURED,
            task_type="unknown",
            answer="当前 AI 服务还没有配置模型，无法运行 Agent。",
        )

    graph = AssistantGraph(llm)
    try:
        result = await graph.run(
            question=request.question,
            context=request.context,
            conversation_id=request.conversation_id,
            user_id=_parse_user_id(request.user_id),
            jwt_token=request.jwt_token,
            trace_id=trace_id,
        )
    except Exception:
        logger.exception("Assistant agent run failed")
        return build_error_response(
            "AI Agent 处理失败。",
            trace_id=trace_id,
            error_code=ErrorCode.ASSISTANT_ERROR,
            task_type="unknown",
            answer="AI Agent 暂时不可用，请稍后再试。",
        )
    return normalize_ai_response(result, trace_id=result.get("trace_id") or trace_id)


def _sse_frame(event_type: str, data: dict) -> str:
    """把 (event_type, data) 编成 SSE 一帧（event/data 双字段 + 双换行）。

    符合 W3C SSE 规范：https://html.spec.whatwg.org/multipage/server-sent-events.html
    """
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


@router.post("/stream")
async def stream_assistant(request: AssistantRunRequest, http_request: Request):
    """流式版本 /run，返回 SSE 事件流。

    事件类型：start / route / token / tool_call / tool_result / final / error / done。
    详见 assistant/graph.py::astream。

    客户端断开检测：每次 yield 前用 Starlette 自带的 `request.is_disconnected()`
    嗅探一次,提前终止 graph.astream,避免 LLM 继续空转烧 token。
    不影响 chat-service 的 doOnCancel 落库语义,仅作为成本侧优化。

    前端使用示例：
        const es = new EventSource('/api/assistant/stream', ...)
        es.addEventListener('token', e => append(JSON.parse(e.data).content))
        es.addEventListener('final', e => renderCards(JSON.parse(e.data).product_cards))
        es.addEventListener('done', () => es.close())
    """
    llm = get_llm()
    trace_id = getattr(http_request.state, "trace_id", None) or str(uuid4())

    async def event_stream() -> AsyncIterator[bytes]:
        if llm is None:
            yield _sse_frame("error", {
                "trace_id": trace_id,
                "error_code": ErrorCode.LLM_NOT_CONFIGURED,
                "message": "当前 AI 服务还没有配置模型，无法运行 Agent。",
            }).encode("utf-8")
            yield _sse_frame("done", {}).encode("utf-8")
            return

        graph = AssistantGraph(llm)
        try:
            async for event in graph.astream(
                question=request.question,
                context=request.context,
                conversation_id=request.conversation_id,
                user_id=_parse_user_id(request.user_id),
                jwt_token=request.jwt_token,
                trace_id=trace_id,
            ):
                # 客户端断开后提前停 LLM,避免空跑 token
                if await http_request.is_disconnected():
                    logger.info(
                        "client disconnected, abort astream trace=%s conv=%s",
                        trace_id, request.conversation_id,
                    )
                    break
                yield _sse_frame(event["type"], event.get("data") or {}).encode("utf-8")
        except Exception as e:  # noqa: BLE001
            logger.exception("Assistant stream failed")
            yield _sse_frame("error", {
                "trace_id": trace_id,
                "error_code": ErrorCode.ASSISTANT_ERROR,
                "message": str(e),
            }).encode("utf-8")
            yield _sse_frame("done", {}).encode("utf-8")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Nginx 反向代理时必须，防止代理缓冲整个流
            "X-Accel-Buffering": "no",
            # 让前端/Java 网关能拿到当前流的 traceId 做关联
            "X-Trace-Id": trace_id,
        },
    )


# ─────────────────────────────────────────────────────────────
# 多模态接口（图文混合）
# ─────────────────────────────────────────────────────────────
# 相较文本接口的唯一差异：request 里可带 image_url（单张 OSS 图片 URL）。
# - 有 image_url + shopping 意图 → shopping_node 走 search_multimodal_v1
#   （三路 + qwen3-vl-rerank）
# - 有 image_url + 非 shopping 意图（少见，如"这张图里的成分能给我讲讲吗"）→
#   路由目前会因 image_url 短路为 shopping；后续如果要走 knowledge 需要
#   多模态问答模型，目前不支持
# - 无 image_url → 完全等价于 /run 或 /stream，走原文本链路

class MultimodalAssistantRunRequest(AssistantRunRequest):
    """带图版本 AssistantRunRequest。

    - image_url 必填（多模态接口的意义就是要有图）
    - question 覆盖为可选（纯图搜商品场景：用户只传图不打字）
    """
    image_url: str = Field(..., description="Single reference image URL (OSS)")
    # 覆盖父类的必填 question：纯图搜索时用户可能只传图。
    question: str = Field("", description="User input text (可选，纯图搜索时可为空)")


def _validate_image_url(image_url: Optional[str]) -> str:
    """校验图片 URL 非空，返回 strip 后的字符串。"""
    if not image_url or not str(image_url).strip():
        raise HTTPException(
            status_code=400,
            detail="image_url is required for multimodal endpoints",
        )
    return str(image_url).strip()


@router.post("/multimodal/run", response_model=AIResponse)
async def run_multimodal_assistant(
    request: MultimodalAssistantRunRequest,
    http_request: Request,
) -> AIResponse:
    """多模态非流式：图 + 文 → 一次性 AIResponse（含 product_cards）。

    Apifox 测试更简单：请求发出后一次返回商品卡片列表和推荐话术。
    """
    image_url = _validate_image_url(request.image_url)

    llm = get_llm()
    trace_id = getattr(http_request.state, "trace_id", None) or str(uuid4())
    if llm is None:
        return build_error_response(
            "LLM 未配置，多模态 Agent 暂不可用。",
            trace_id=trace_id,
            error_code=ErrorCode.LLM_NOT_CONFIGURED,
            task_type="unknown",
            answer="当前 AI 服务还没有配置模型，无法运行多模态 Agent。",
        )

    graph = AssistantGraph(llm)
    try:
        result = await graph.run(
            question=request.question,
            context=request.context,
            conversation_id=request.conversation_id,
            user_id=_parse_user_id(request.user_id),
            jwt_token=request.jwt_token,
            trace_id=trace_id,
            image_url=image_url,
        )
    except Exception:
        logger.exception("Multimodal assistant run failed")
        return build_error_response(
            "多模态 Agent 处理失败。",
            trace_id=trace_id,
            error_code=ErrorCode.ASSISTANT_ERROR,
            task_type="unknown",
            answer="多模态 Agent 暂时不可用，请稍后再试。",
        )
    return normalize_ai_response(result, trace_id=result.get("trace_id") or trace_id)


@router.post("/multimodal/stream")
async def stream_multimodal_assistant(
    request: MultimodalAssistantRunRequest,
    http_request: Request,
):
    """多模态流式：图 + 文 → SSE 事件流。

    事件类型与 /stream 一致（start/route/token/tool_call/tool_result/final/
    error/done）。图搜的推荐话术会通过 token 事件流式吐出。
    """
    image_url = _validate_image_url(request.image_url)

    llm = get_llm()
    trace_id = getattr(http_request.state, "trace_id", None) or str(uuid4())

    async def event_stream() -> AsyncIterator[bytes]:
        if llm is None:
            yield _sse_frame("error", {
                "trace_id": trace_id,
                "error_code": ErrorCode.LLM_NOT_CONFIGURED,
                "message": "当前 AI 服务还没有配置模型，无法运行多模态 Agent。",
            }).encode("utf-8")
            yield _sse_frame("done", {}).encode("utf-8")
            return

        graph = AssistantGraph(llm)
        try:
            async for event in graph.astream(
                question=request.question,
                context=request.context,
                conversation_id=request.conversation_id,
                user_id=_parse_user_id(request.user_id),
                jwt_token=request.jwt_token,
                trace_id=trace_id,
                image_url=image_url,
            ):
                if await http_request.is_disconnected():
                    logger.info(
                        "client disconnected, abort multimodal astream trace=%s conv=%s",
                        trace_id, request.conversation_id,
                    )
                    break
                yield _sse_frame(event["type"], event.get("data") or {}).encode("utf-8")
        except Exception as e:  # noqa: BLE001
            logger.exception("Multimodal assistant stream failed")
            yield _sse_frame("error", {
                "trace_id": trace_id,
                "error_code": ErrorCode.ASSISTANT_ERROR,
                "message": str(e),
            }).encode("utf-8")
            yield _sse_frame("done", {}).encode("utf-8")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Trace-Id": trace_id,
        },
    )
