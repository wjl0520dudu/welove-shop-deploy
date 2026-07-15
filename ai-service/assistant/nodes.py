# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
from uuid import uuid4
from typing import Any, Callable, Dict, List, Optional
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from agents.state import AssistantState
from agents.prompts import CHITCHAT_PROMPT
from core.errors import ErrorCode
from shopping.agent import ShoppingAgent
from knowledge.agent import KnowledgeAgent

logger = logging.getLogger("ai-service.nodes")

# 闲聊 agent 专用独立 checkpointer，与主图 checkpointer 完全隔离
_chitchat_checkpointer = InMemorySaver()


# ---- 多模态 shopping 推荐话术 prompt --------------------------------
# 有图检索场景下，商品卡片已经通过 search_multimodal_v1 拿到，只需要 LLM
# 把这些卡片和用户 query 结合，写一段自然的推荐话术即可。
# 不走 tool loop，不需要 LLM 决定检索——只做「看图 + 看候选 + 写话术」。
_MULTIMODAL_SHOPPING_PROMPT = """你是电商导购。用户传了一张商品参考图并提出了需求，系统已经通过图文多模态检索找到了一批相似商品，你负责基于这些商品和用户意图写一段自然的推荐话术。

规则：
1. 直接推荐 top 3 商品，不要说"我为您找到了xxx"这种开场白，直接进入正题
2. 每款商品用 1-2 句话说明为什么它匹配用户的需求（价格、卖点、场景）
3. 结尾可以给一句选购建议（如"预算敏感选X，追求品质选Y"）
4. 不要虚构商品信息，只用给出的商品字段
5. 不要说"根据您上传的图片"这类废话，就当作正常推荐来写

## 用户需求
{query_text}

## 检索到的候选商品（按相关度降序）
{product_list}

## 你的推荐（100-200 字，Markdown 格式）
"""


def _format_products_for_prompt(cards: List[Dict[str, Any]], top_n: int = 5) -> str:
    """把 product_cards 列表格式化成 LLM 可读的 Markdown 文本。"""
    lines = []
    for i, c in enumerate(cards[:top_n], start=1):
        price = c.get("price") or c.get("base_price")
        line = (
            f"{i}. **{c.get('title', '')}**（品牌: {c.get('brand') or '未知'}, "
            f"价格: ¥{price}, 品类: {c.get('sub_category') or c.get('category') or '未知'}）"
        )
        desc = (c.get("description") or "").strip()
        if desc:
            line += f"\n   {desc[:120]}"
        lines.append(line)
    return "\n".join(lines) if lines else "（无候选商品）"


async def _multimodal_shopping(
    llm,
    query_text: str,
    image_url: str,
    top_k: int = 5,
) -> Dict[str, Any]:
    """有图 shopping 分支：直接调 search_multimodal_v1，然后让 LLM 写推荐话术。

    不走 ShoppingAgent 的 tool loop，因为文本 LLM 看不到图，让它决定要不要
    调多模态工具没意义；直接程序侧调多模态检索，把结果交给 LLM 生成话术。
    """
    from shopping.multimodal_search import search_multimodal_v1
    from shopping.relevance_judge import filter_candidates

    try:
        # 多召回一批候选，再允许 judge 过滤掉异类；最终仍只返回 top_k，
        # 不为了凑满 top_k 把明显不相关的商品补回来。
        retrieval_top_k = max(int(top_k or 5) * 2, int(top_k or 5))
        results = await search_multimodal_v1(
            query_text=query_text or "",
            query_image_url=image_url,
            top_k=retrieval_top_k,
        )
        results = await filter_candidates(
            llm=llm,
            query_text=query_text or "",
            query_image_url=image_url,
            candidates=results,
            limit=top_k,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("multimodal shopping retrieval failed")
        return {
            "answer": "图片检索暂时不可用，请稍后再试。",
            "task_type": "shopping",
            "error": True,
            "error_code": ErrorCode.SHOPPING_ERROR,
            "message": str(e),
        }

    if not results:
        return {
            "answer": "抱歉，没有找到跟这张图相似的商品，可以换一张更清晰的图或者补充一下你的需求（预算、场景、品牌偏好）。",
            "task_type": "shopping",
            "product_cards": [],
            "sources": [],
            "tool_calls": [],
            "error": False,
        }

    # 让 LLM 基于卡片 + query 写推荐话术
    if llm is None:
        answer = f"已为你找到 {len(results)} 款相似商品，你可以看下面的商品卡片。"
    else:
        prompt = _MULTIMODAL_SHOPPING_PROMPT.format(
            query_text=query_text or "（无文本描述，仅参考图片）",
            product_list=_format_products_for_prompt(results),
        )
        try:
            resp = await llm.ainvoke(prompt)
            answer = str(getattr(resp, "content", "") or "").strip()
        except Exception as e:  # noqa: BLE001
            logger.warning("multimodal shopping 生成推荐话术失败：%s", e)
            answer = ""
        if not answer:
            answer = f"已为你找到 {len(results)} 款相似商品，你可以看下面的商品卡片。"

    # 精简 product_cards 字段（去掉向量分数等评测字段）
    product_cards = []
    for r in results:
        product_cards.append({
            "product_id": r.get("product_id"),
            "title": r.get("title", ""),
            "brand": r.get("brand", ""),
            "price": r.get("price") or r.get("base_price"),
            "base_price": r.get("base_price"),
            "image_url": r.get("image_url", ""),
            "rating": r.get("rating"),
            "sales_count": r.get("sales_count"),
            "sub_category": r.get("sub_category", ""),
            "reason": "图文多模态检索命中",
        })

    return {
        "answer": answer,
        "task_type": "shopping",
        "product_cards": product_cards,
        "sources": [],
        "tool_calls": [{
            "name": "search_multimodal_v1",
            "args": {"query_text": query_text, "query_image_url": image_url, "top_k": top_k},
        }],
        "error": False,
    }


def make_nodes(llm, shopping_agent: Optional[ShoppingAgent] = None,
               knowledge_agent: Optional[KnowledgeAgent] = None) -> Dict[str, Callable]:
    _shopping_holder: Dict[str, Any] = {"agent": shopping_agent}
    _knowledge_holder: Dict[str, Any] = {"agent": knowledge_agent}
    _chitchat_holder: Dict[str, Any] = {"agent": None}

    def get_shopping():
        if _shopping_holder["agent"] is None:
            _shopping_holder["agent"] = ShoppingAgent(llm)
        return _shopping_holder["agent"]

    def get_knowledge():
        if _knowledge_holder["agent"] is None:
            _knowledge_holder["agent"] = KnowledgeAgent(llm)
        return _knowledge_holder["agent"]

    def _get_chitchat_agent():
        if _chitchat_holder["agent"] is None:
            from agents.middleware import build_summarization_middleware
            # 不挂 response_format：让 answer 走纯文本 content，才能被
            # graph.astream 的 messages 流逐 token 吐给前端（豆包式打字机）。
            # ToolStrategy 会把答案塞进 tool_call.args，content 为空，流式被废。
            _chitchat_holder["agent"] = create_agent(
                model=llm,
                checkpointer=_chitchat_checkpointer,
                system_prompt=CHITCHAT_PROMPT,
                middleware=[build_summarization_middleware()],
            )
        return _chitchat_holder["agent"]

    async def shopping_node(state: AssistantState) -> dict:
        # 多模态分支：state 里有 image_url 时走图文多模态检索，
        # 不进 ShoppingAgent 的 LLM tool loop（文本 LLM 看不到图，让它决定
        # 要不要调多模态工具没意义）
        image_url = (state.get("image_url") or "").strip()
        if image_url:
            result = await _multimodal_shopping(
                llm=llm,
                query_text=state.get("question", ""),
                image_url=image_url,
                top_k=5,
            )
            return _merge_result(
                result,
                task_type="shopping",
                extra={"messages": [AIMessage(content=result.get("answer", ""))]},
            )

        try:
            result = await get_shopping().run(
                question=state.get("question", ""),
                messages=_history_messages(state),
                business_memory=state.get("business_memory", {}),
                conversation_id=state.get("conversation_id"),
                user_id=state.get("user_id"),
                jwt_token=state.get("jwt_token"),
            )
        except Exception as e:
            logger.exception("shopping node failed")
            return {
                "answer": "导购 Agent 暂时不可用，请稍后再试。",
                "task_type": "shopping",
                "error": True,
                "error_code": ErrorCode.SHOPPING_ERROR,
                "message": str(e),
                "messages": [AIMessage(content="导购 Agent 暂时不可用，请稍后再试。")],
            }
        return _merge_result(result, task_type="shopping",
                             extra={"messages": [AIMessage(content=result.get("answer", ""))]})

    async def knowledge_node(state: AssistantState) -> dict:
        try:
            messages = _build_agent_messages(state)
            result = await get_knowledge().run(
                messages=messages,
                conversation_id=state.get("conversation_id", ""),
                user_id=state.get("user_id"),
            )
            # 无检索结果兜底：sources 为空 或 has_answer=False 时补一句引导，
            # 但 task_type 保持 knowledge —— 不要伪装成 chitchat，否则前端行为错乱。
            # 具体的"知识库暂无相关信息"由 KNOWLEDGE_PROMPT 约束 LLM 自己说，这里只做兜底 answer 补全。
            has_answer = bool(result.get("has_answer", True))
            sources = result.get("sources") or []
            answer = (result.get("answer") or "").strip()
            if (not has_answer or not sources) and not answer:
                question = state.get("question", "")
                answer = (
                    f"关于「{question}」，我在知识库里暂时没有找到直接相关的资料。"
                    f"你可以换个角度问我，或者提供更具体的场景（比如你的肤质、使用需求），我再帮你分析。"
                )
                result = {**result, "answer": answer}
        except Exception as e:
            logger.exception("knowledge node failed")
            return {
                "answer": "知识检索暂时不可用，请稍后再试。",
                "task_type": "knowledge",
                "error": True,
                "error_code": ErrorCode.KNOWLEDGE_ERROR,
                "message": str(e),
                "messages": [AIMessage(content="知识检索暂时不可用，请稍后再试。")],
            }
        return _merge_result(result, task_type="knowledge",
                             extra={"messages": [AIMessage(content=result.get("answer", ""))]})

    async def chitchat_node(state: AssistantState) -> dict:
        if llm is None:
            return {
                "answer": "AI 助手暂未配置，无法闲聊。",
                "task_type": "chitchat",
                "error": True,
                "error_code": ErrorCode.LLM_NOT_CONFIGURED,
            }
        try:
            messages = _build_agent_messages(state)
            agent = _get_chitchat_agent()
            # recursion_limit=5：chitchat 正常 1-2 步就出结果，5 步防死循环
            result = await agent.ainvoke(
                {"messages": messages},
                config={
                    "configurable": {"thread_id": str(uuid4())},
                    "recursion_limit": 5,
                },
            )
            # answer 直接从最后一条 AI 消息 content 提取（纯文本，可流式）。
            # 去 ToolStrategy 后不再有 structured_response，这里就是主路径。
            answer = ""
            for m in reversed(result.get("messages", [])):
                if isinstance(m, dict):
                    if m.get("type") == "ai" and m.get("content"):
                        answer = str(m.get("content", ""))
                        break
                else:
                    if getattr(m, "type", "") == "ai":
                        content = getattr(m, "content", "")
                        if isinstance(content, str) and content.strip():
                            answer = content
                            break
            answer = answer or "嗯嗯，我在呢~"
        except Exception as e:
            logger.exception("chitchat node failed")
            return {
                "answer": "闲聊回复失败，请稍后再试。",
                "task_type": "chitchat",
                "error": True,
                "error_code": ErrorCode.CHITCHAT_ERROR,
                "message": str(e),
                "messages": [AIMessage(content="闲聊回复失败，请稍后再试。")],
            }
        return {
            "answer": answer,
            "task_type": "chitchat",
            "messages": [AIMessage(content=answer)],
        }

    async def unknown_node(state: AssistantState) -> dict:
        msg = "我可以帮你找商品、推荐，或回答商品知识问题，请告诉我你的需求。"
        return {
            "answer": msg,
            "task_type": "unknown",
            "messages": [AIMessage(content=msg)],
        }

    def format_response(state: AssistantState) -> dict:
        result = {
            "answer": state.get("answer", ""),
            "task_type": state.get("task_type") or state.get("route") or "unknown",
            "product_cards": state.get("product_cards", []),
            "sources": state.get("sources", []),
            "tool_calls": state.get("tool_calls", []),
            "run_id": state.get("run_id"),
            "trace_id": state.get("trace_id"),
            "route": state.get("route"),
            "route_reason": state.get("route_reason"),
            "orchestrator_mode": state.get("orchestrator_mode"),
            "orchestrator_reason": state.get("orchestrator_reason"),
            "sub_questions": state.get("sub_questions", []),
            "sub_results": state.get("sub_results", []),
            "error": bool(state.get("error", False)),
            "error_code": state.get("error_code"),
            "message": state.get("message"),
        }
        return {"result": result}

    return {
        "shopping_node": shopping_node,
        "knowledge_node": knowledge_node,
        "chitchat_node": chitchat_node,
        "unknown_node": unknown_node,
        "format_response": format_response,
    }


def _build_agent_messages(state: AssistantState) -> list:
    """从共享 state 构建传给子 agent 的消息列表。

    子 agent（knowledge/shopping/chitchat）通过 create_agent 运行，需要 {"messages": [...]} 格式。
    这里从 state["messages"] 中提取，带上完整对话历史，实现多 agent 共享记忆。
    """
    messages = state.get("messages") or []
    out = []
    for m in messages:
        if isinstance(m, dict):
            out.append(m)
            continue
        mtype = getattr(m, "type", "")
        content = getattr(m, "content", "")
        if isinstance(content, str) and content.strip():
            if mtype == "human":
                out.append(HumanMessage(content=content))
            elif mtype == "ai":
                out.append(AIMessage(content=content))
    return out


def _merge_result(result: Dict[str, Any], *, task_type: str,
                  extra: Dict[str, Any] = None) -> dict:
    merged: Dict[str, Any] = {}
    for key in ("answer", "product_cards", "sources", "tool_calls", "error", "error_code", "message"):
        if key in result:
            merged[key] = result[key]
    merged.setdefault("answer", "")
    merged.setdefault("task_type", result.get("task_type") or task_type)
    merged.setdefault("product_cards", [])
    merged.setdefault("sources", [])
    merged.setdefault("tool_calls", [])
    merged.setdefault("error", False)
    if extra:
        merged.update(extra)
    return merged


def _history_messages(state: AssistantState) -> list:
    """构建传给 ShoppingAgent 的历史消息列表（dict 格式）。"""
    messages = state.get("messages") or []
    out = []
    for m in messages:
        if isinstance(m, dict):
            out.append(m)
            continue
        mtype = getattr(m, "type", "")
        content = getattr(m, "content", "")
        if mtype == "human":
            out.append({"role": "user", "content": content})
        elif mtype == "ai":
            out.append({"role": "assistant", "content": str(content) if not isinstance(content, str) else content})
        elif mtype == "system":
            out.append({"role": "system", "content": content})
    return out
