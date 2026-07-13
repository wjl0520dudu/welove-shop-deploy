# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
import re
from typing import Any, AsyncIterator, Dict
from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.messages import AIMessageChunk, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from agents.memory import get_business_memory
from agents.schemas import IntentDecision, OrchestratorDecision
from agents.prompts import ORCHESTRATOR_PROMPT, ROUTER_PROMPT
from agents.state import AssistantState
from agents import runtime as _runtime  # 用模块引用，运行时动态读 checkpointer/store
from assistant.nodes import make_nodes
from core.errors import ErrorCode
from tools.router_tools import format_business_memory_for_router

logger = logging.getLogger("ai-service.assistant.graph")

class AssistantGraph:
    """Supervisor 编排图：route_intent 路由 -> 子节点 -> format_response。
    主图持有 checkpointer 与 messages 状态，子 agent 不单独 checkpoint。
    子 agent 实例通过 make_nodes 闭包持有，不放进可序列化的 state。
    """

    def __init__(self, llm, shopping_agent=None, knowledge_agent=None):
        self.llm = llm
        self.shopping_agent = shopping_agent
        self.knowledge_agent = knowledge_agent
        self._nodes = make_nodes(llm, shopping_agent, knowledge_agent)
        # 路由器：单次结构化分类，不走 agent 循环。
        # 原先用 create_agent(response_format=ToolStrategy) 会多一次 LLM 往返
        # （schema 注册成工具 → 模型 tool_call → 回 ToolMessage → 再调一次模型 = 2 次）。
        # with_structured_output 是直链：模型一次产出结构化结果，LangChain 客户端解析 = 1 次。
        # method="function_calling" 走工具调用（与原 ToolStrategy 同机制，已验证兼容当前代理）。
        self._router_llm = (
            llm.with_structured_output(IntentDecision, method="function_calling")
            if llm is not None
            else None
        )
        self._orchestrator_llm = (
            _build_structured_llm(llm, OrchestratorDecision, preferred_method="json_schema")
            if llm is not None
            else None
        )
        self.graph = self._build()

    def _build(self):
        g = StateGraph(AssistantState)
        g.add_node("analyze_request", self._analyze_request)
        g.add_node("prepare_subtask", self._prepare_subtask)
        g.add_node("route_intent", self._route)
        g.add_node("shopping", self._nodes["shopping_node"])
        g.add_node("knowledge", self._nodes["knowledge_node"])
        g.add_node("chitchat", self._nodes["chitchat_node"])
        g.add_node("unknown", self._nodes["unknown_node"])
        g.add_node("collect_subtask", self._collect_subtask)
        g.add_node("synthesize_final", self._synthesize_final)
        g.add_node("format_response", self._nodes["format_response"])

        g.add_edge(START, "analyze_request")
        g.add_conditional_edges(
            "analyze_request",
            self._after_analyze,
            {"simple": "route_intent", "complex": "prepare_subtask"},
        )
        g.add_edge("prepare_subtask", "route_intent")
        g.add_conditional_edges("route_intent", lambda s: s.get("route") or "unknown",
                                {"shopping": "shopping", "knowledge": "knowledge",
                                 "chitchat": "chitchat", "unknown": "unknown"})
        for n in ("shopping", "knowledge", "chitchat", "unknown"):
            g.add_conditional_edges(
                n,
                self._after_business_node,
                {"simple": "format_response", "complex": "collect_subtask"},
            )
        g.add_conditional_edges(
            "collect_subtask",
            self._after_collect,
            {"next": "prepare_subtask", "done": "synthesize_final"},
        )
        g.add_edge("synthesize_final", "format_response")
        g.add_edge("format_response", END)
        # 从 runtime 模块动态读，确保拿到的是 init_runtime() 覆盖后的实例
        return g.compile(checkpointer=_runtime.checkpointer, store=_runtime.store)

    async def _analyze_request(self, state: AssistantState) -> dict:
        """判断本轮是否需要 Orchestrator，并在需要时生成任务议程。"""
        question = state.get("question") or ""
        if not question.strip():
            return {
                "original_question": question,
                "orchestrator_mode": "simple",
                "orchestrator_reason": "问题为空",
            }

        if self._orchestrator_llm is None:
            return self._fallback_orchestrator_decision(question, "编排模型未配置")

        history_messages = state.get("messages") or [HumanMessage(question)]
        cid = state.get("conversation_id")
        uid = state.get("user_id")
        context_text = ""
        try:
            memory = await get_business_memory(cid, uid)
            context_text = format_business_memory_for_router(memory)
        except Exception:  # noqa: BLE001
            logger.warning("orchestrator: 读取 business_memory 失败，退化到纯问题分析", exc_info=True)

        messages: list = [SystemMessage(content=ORCHESTRATOR_PROMPT)]
        if context_text:
            messages.append(SystemMessage(content=context_text))
        messages.extend(history_messages)

        try:
            decision = await self._orchestrator_llm.ainvoke(
                messages,
                config={"tags": ["ai_internal"]},
            )
        except Exception:  # noqa: BLE001
            logger.warning("orchestrator: 结构化拆解失败，尝试启发式拆解", exc_info=True)
            return self._fallback_orchestrator_decision(question, "结构化拆解失败")

        if decision is None:
            logger.warning(
                "orchestrator: 结构化拆解返回 None，重试一次 question=%r",
                question,
            )
            try:
                decision = await self._orchestrator_llm.ainvoke(
                    messages,
                    config={"tags": ["ai_internal"]},
                )
            except Exception:  # noqa: BLE001
                logger.warning("orchestrator: 结构化拆解重试失败，尝试启发式拆解", exc_info=True)
                return self._fallback_orchestrator_decision(question, "结构化拆解重试失败")

        if decision is None:
            logger.warning(
                "orchestrator: 结构化拆解重试后仍为空，尝试启发式拆解 question=%r",
                question,
            )
            return self._fallback_orchestrator_decision(question, "结构化拆解返回空")

        normalized = self._normalize_orchestrator_decision(question, decision)
        decision_mode = str(_decision_value(decision, "mode", "simple") or "simple").lower()
        if decision_mode == "complex" and normalized.get("orchestrator_mode") == "simple":
            logger.warning(
                "orchestrator: LLM 声称 complex 但 tasks 不足，尝试启发式补救 question=%r",
                question,
            )
            return self._fallback_orchestrator_decision(question, "LLM 拆解不完整")
        return normalized

    def _normalize_orchestrator_decision(self, question: str, decision: Any) -> dict:
        mode = str(_decision_value(decision, "mode", "simple") or "simple").lower()
        reason = str(_decision_value(decision, "reason", "") or "")
        raw_tasks = _decision_value(decision, "tasks", []) or []
        tasks = _normalize_tasks(raw_tasks)
        if mode != "complex" or len(tasks) < 2:
            return {
                "original_question": question,
                "orchestrator_mode": "simple",
                "orchestrator_reason": reason or "单任务请求",
                "sub_questions": [],
                "sub_results": [],
                "current_subquestion_index": 0,
            }
        return {
            "original_question": question,
            "orchestrator_mode": "complex",
            "orchestrator_reason": reason or "检测到多任务请求",
            "sub_questions": tasks,
            "sub_results": [],
            "current_subquestion_index": 0,
        }

    def _fallback_orchestrator_decision(self, question: str, reason: str) -> dict:
        tasks = _heuristic_split_tasks(question)
        if len(tasks) < 2:
            return {
                "original_question": question,
                "orchestrator_mode": "simple",
                "orchestrator_reason": reason,
                "sub_questions": [],
                "sub_results": [],
                "current_subquestion_index": 0,
            }
        return {
            "original_question": question,
            "orchestrator_mode": "complex",
            "orchestrator_reason": f"{reason}，启发式识别到多问题",
            "sub_questions": tasks,
            "sub_results": [],
            "current_subquestion_index": 0,
        }

    def _after_analyze(self, state: AssistantState) -> str:
        if state.get("orchestrator_mode") == "complex" and len(state.get("sub_questions") or []) >= 2:
            return "complex"
        return "simple"

    def _prepare_subtask(self, state: AssistantState) -> dict:
        tasks = state.get("sub_questions") or []
        idx = int(state.get("current_subquestion_index") or 0)
        if idx < 0 or idx >= len(tasks):
            return {"orchestrator_mode": "simple"}

        task = dict(tasks[idx])
        question = str(task.get("question") or "").strip() or state.get("original_question") or ""
        heading = _format_subtask_heading(idx, len(tasks), question)
        return {
            "question": question,
            "active_subtask": task,
            "answer": "",
            "task_type": None,
            "product_cards": [],
            "sources": [],
            "tool_calls": [],
            "error": False,
            "error_code": None,
            "message": None,
            "subtask_heading": heading,
            "messages": [HumanMessage(content=question)],
        }

    def _after_business_node(self, state: AssistantState) -> str:
        return "complex" if state.get("orchestrator_mode") == "complex" else "simple"

    def _collect_subtask(self, state: AssistantState) -> dict:
        task = dict(state.get("active_subtask") or {})
        idx = int(state.get("current_subquestion_index") or 0)
        result = {
            "id": task.get("id") or f"t{idx + 1}",
            "question": task.get("question") or state.get("question") or "",
            "intent_hint": task.get("intent_hint"),
            "depends_on": task.get("depends_on") or [],
            "route": state.get("route"),
            "route_reason": state.get("route_reason"),
            "task_type": state.get("task_type") or state.get("route") or "unknown",
            "answer": state.get("answer", ""),
            "product_cards": state.get("product_cards", []),
            "sources": state.get("sources", []),
            "tool_calls": state.get("tool_calls", []),
            "error": bool(state.get("error", False)),
            "error_code": state.get("error_code"),
            "message": state.get("message"),
        }
        results = list(state.get("sub_results") or [])
        results.append(result)
        return {
            "sub_results": results,
            "current_subquestion_index": idx + 1,
        }

    def _after_collect(self, state: AssistantState) -> str:
        idx = int(state.get("current_subquestion_index") or 0)
        total = len(state.get("sub_questions") or [])
        return "next" if idx < total else "done"

    def _synthesize_final(self, state: AssistantState) -> dict:
        sub_results = state.get("sub_results") or []
        answer = _build_orchestrator_answer(sub_results)
        product_cards = _dedupe_product_cards(
            card
            for result in sub_results
            for card in (result.get("product_cards") or [])
        )
        sources = _dedupe_sources(
            source
            for result in sub_results
            for source in (result.get("sources") or [])
        )
        tool_calls = [
            call
            for result in sub_results
            for call in (result.get("tool_calls") or [])
        ]
        has_error = any(bool(r.get("error")) for r in sub_results)
        return {
            "answer": answer,
            "task_type": "orchestrator",
            "product_cards": product_cards,
            "sources": sources,
            "tool_calls": tool_calls,
            "route": "orchestrator",
            "route_reason": state.get("orchestrator_reason"),
            "error": has_error,
            "error_code": ErrorCode.ORCHESTRATOR_PARTIAL_ERROR if has_error else None,
            "message": "部分子任务处理失败" if has_error else None,
            "messages": [AIMessage(content=answer)],
        }

    async def _route(self, state: AssistantState) -> dict:
        question = state.get("question")
        if not question:
            return {"route": "unknown", "route_reason": "问题为空"}

        # 直接传 state["messages"]（已通过主图 checkpointer 合并了历史）
        # 不要再拼接第二次 question，否则问题出现两次。
        history_messages = state.get("messages") or [HumanMessage(question)]

        # 把业务上下文（上轮推荐商品、当前关注商品、用户偏好）塞进 Router 的 messages，
        # 让分类能看到"用户在指代什么"。例如 "第二个多少钱" 单看这句无法分类，
        # 但看到 last_product_cards 就能判断这是 shopping 场景（追问具体商品）。
        cid = state.get("conversation_id")
        uid = state.get("user_id")
        context_text = ""
        try:
            memory = await get_business_memory(cid, uid)
            context_text = format_business_memory_for_router(memory)
        except Exception:  # noqa: BLE001
            # Store 读取失败不阻塞分类，退化到纯 messages 分类
            logger.warning("router: 读取 business_memory 失败，退化到纯分类", exc_info=True)

        # ROUTER_PROMPT 作为首条 system 消息置顶；会话上下文作为第二条 system 消息追加。
        # with_structured_output 直链，不再需要 checkpointer / thread_id / recursion_limit。
        router_messages: list = [SystemMessage(content=ROUTER_PROMPT)]
        if context_text:
            router_messages.append(SystemMessage(content=context_text))
        router_messages.extend(history_messages)

        if self._router_llm is None:
            return {"route": "unknown", "route_reason": "路由模型未配置"}

        # with_structured_output 默认 include_raw=False，解析失败会抛异常；
        # 这里兜住，分类失败一律归 unknown，不阻塞主图。
        try:
            decision = await self._router_llm.ainvoke(router_messages)
        except Exception:  # noqa: BLE001
            logger.warning("router: 结构化分类失败，退化到 unknown", exc_info=True)
            return {"route": "unknown", "route_reason": "路由分类失败"}
        if decision is None:
            return {"route": "unknown", "route_reason": "路由分类失败"}
        return {"route": decision.task_type, "route_reason": decision.reason}

    def _make_initial_state(self, **kwargs) -> tuple[AssistantState, str, str]:
        """构造主图初始 state。返回 (state, run_id, trace_id)。"""
        run_id = kwargs.get("run_id") or str(uuid4())
        trace_id = kwargs.get("trace_id") or str(uuid4())
        question = kwargs.get("question", "")
        state: AssistantState = {
            "question": question,
            "conversation_id": kwargs.get("conversation_id"),
            "user_id": kwargs.get("user_id"),
            "jwt_token": kwargs.get("jwt_token"),
            "run_id": run_id,
            "trace_id": trace_id,
            "messages": [HumanMessage(content=question)],
            "error": False,
        }
        return state, run_id, trace_id

    async def run(self, **kwargs) -> dict:
        state, run_id, trace_id = self._make_initial_state(**kwargs)
        conversation_id = state.get("conversation_id")
        final = await self.graph.ainvoke(state, config={"configurable": {"thread_id": conversation_id}})
        result = final.get("result") or {}
        result.setdefault("run_id", run_id)
        result.setdefault("trace_id", trace_id)
        return result

    async def astream(self, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """流式版本的 run()，逐步 yield 结构化事件 dict。

        每个 yield 是 `{"type": "<event_type>", "data": {...}}`。
        由 api/assistant_routes.py 的 SSE 端点转成 `event: <type>\\ndata: {...}\\n\\n`。

        事件类型：
        - start        请求开始
        - route        路由决策完成（shopping / knowledge / chitchat / unknown）
        - token        LLM 增量 token（重复多次）
        - tool_call    工具被调用
        - tool_result  工具返回
        - final        最终完整响应（跟 /run 一致）
        - error        出错
        - done         结束标志（前端可关流）

        用 stream_mode=["updates", "messages"] + subgraphs=True，同时拿到：
        - updates: 每个节点结束时的 state 增量（用于 route / tool_call / tool_result）
        - messages: 主图 + 子图 LLM 产生的每个 AIMessageChunk（token 流）
        - subgraphs: 让子图（ShoppingAgent 内的 create_agent）事件冒泡
        """
        state, run_id, trace_id = self._make_initial_state(**kwargs)
        conversation_id = state.get("conversation_id")

        # start 事件：告诉前端 trace_id / run_id
        yield {
            "type": "start",
            "data": {
                "run_id": run_id,
                "trace_id": trace_id,
                "conversation_id": conversation_id,
            },
        }

        final_result: Dict[str, Any] = {}
        # LangGraph subgraphs=True 时事件格式为 (namespace_tuple, mode, payload)
        # namespace_tuple: 空 = 主图，(node_name, task_id) = 子图
        async for chunk in self.graph.astream(
            state,
            config={"configurable": {"thread_id": conversation_id}},
            stream_mode=["updates", "messages"],
            subgraphs=True,
        ):
            # 兼容 subgraphs=True/False 两种输出结构
            if isinstance(chunk, tuple) and len(chunk) == 3:
                namespace, mode, payload = chunk
            elif isinstance(chunk, tuple) and len(chunk) == 2:
                namespace = ()
                mode, payload = chunk
            else:
                continue

            if mode == "messages":
                # payload = (message_chunk, metadata_dict)
                msg_chunk, meta = payload
                async for event in self._translate_message_event(msg_chunk, meta, namespace):
                    yield event

            elif mode == "updates":
                # payload = {node_name: {state_delta_key: value, ...}}
                for node_name, node_output in (payload or {}).items():
                    async for event in self._translate_update_event(node_name, node_output):
                        yield event
                    # format_response 节点会把整个 result 写到 state["result"]
                    if node_name == "format_response" and isinstance(node_output, dict):
                        final_result = node_output.get("result") or final_result

        # final 事件：完整响应
        final_result.setdefault("run_id", run_id)
        final_result.setdefault("trace_id", trace_id)
        yield {"type": "final", "data": final_result}

        # done 事件：前端可关流
        yield {"type": "done", "data": {}}

    async def _translate_message_event(
        self,
        msg_chunk,
        meta,
        namespace=(),
    ) -> AsyncIterator[Dict[str, Any]]:
        """把 messages 流的 AIMessageChunk 翻译成 token 事件。"""
        # 只流式 LLM 的增量 chunk（AIMessageChunk）。节点写回 state 的完整 AIMessage 会被
        # messages 流再整段发一次，与已逐 token 流过的内容重复（答案发两遍），这里跳过。
        if not isinstance(msg_chunk, AIMessageChunk):
            return
        content = getattr(msg_chunk, "content", "")
        if self._should_suppress_token(meta, namespace, content):
            return
        # content 可能是 str，也可能是 list（多模态 / tool_call 结构）
        if isinstance(content, str) and content:
            yield {"type": "token", "data": {"content": content}}
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                    yield {"type": "token", "data": {"content": part["text"]}}

    def _should_suppress_token(self, meta, namespace, content: Any) -> bool:
        """过滤不应展示给用户的 messages 流片段。"""
        meta = meta or {}
        namespace = namespace or ()

        # 内部结构化调用（如槽位抽取 with_structured_output）会打 ai_internal tag。
        # 不同 LangChain/LangGraph 版本可能把 tags 放在顶层或 metadata/config 下，统一兼容。
        tags = _collect_tags(meta)
        if "ai_internal" in tags:
            return True

        # Tool 节点里的内部 LLM 调用不应进入聊天气泡；否则会把 ShoppingNeed JSON
        # 之类的中间产物按 token 泄漏给前端。
        graph_node = str(meta.get("langgraph_node") or "")
        graph_path = _flatten_namespace(meta.get("langgraph_path") or ())
        namespace_text = " ".join(_flatten_namespace(namespace))
        if graph_node in {"tools", "tool"} or "tools" in graph_path or "tools" in namespace_text:
            return True

        # 主图业务节点返回的 {"messages": [AIMessage(content=完整答案)]} 会被 messages
        # stream 再发一次；这个片段不是 LLM 增量，而是节点回写的完整答案，必须过滤。
        main_nodes = {
            "analyze_request",
            "prepare_subtask",
            "route_intent",
            "shopping",
            "knowledge",
            "chitchat",
            "unknown",
            "collect_subtask",
            "synthesize_final",
            "format_response",
        }
        if not namespace and graph_node in main_nodes:
            return True

        return False

    async def _translate_update_event(self, node_name: str, node_output) -> AsyncIterator[Dict[str, Any]]:
        """把 updates 流翻译成 route / tool_call / tool_result 事件。"""
        if not isinstance(node_output, dict):
            return

        # 1. 路由节点产出 route 字段
        if node_name == "route_intent" and "route" in node_output:
            yield {
                "type": "route",
                "data": {
                    "task_type": node_output.get("route"),
                    "reason": node_output.get("route_reason"),
                },
            }

        if node_name == "analyze_request" and node_output.get("orchestrator_mode") == "complex":
            yield {
                "type": "orchestrator_plan",
                "data": {
                    "mode": "complex",
                    "reason": node_output.get("orchestrator_reason"),
                    "tasks": node_output.get("sub_questions") or [],
                },
            }

        if node_name == "prepare_subtask" and node_output.get("subtask_heading"):
            active = node_output.get("active_subtask") or {}
            yield {
                "type": "orchestrator_subtask",
                "data": {
                    "task": active,
                    "heading": node_output.get("subtask_heading"),
                },
            }
            yield {
                "type": "token",
                "data": {"content": node_output.get("subtask_heading")},
            }

        # 2. 子节点消息里可能含 ToolMessage（工具返回）—— 用于 tool_result
        # 主图节点自己不会直接调工具，工具都在子图（ShoppingAgent 等）内部。
        # subgraphs=True 时子图消息会在 messages 流里冒泡，这里 updates 流一般看不到。
        # 保留结构，未来如果有主图直接调工具的场景可以在这里补充。
        _ = node_name  # 静默 lint


def _decision_value(decision: Any, key: str, default: Any = None) -> Any:
    if isinstance(decision, dict):
        return decision.get(key, default)
    return getattr(decision, key, default)


def _build_structured_llm(llm: Any, schema: Any, *, preferred_method: str):
    try:
        return llm.with_structured_output(schema, method=preferred_method)
    except Exception:  # noqa: BLE001
        logger.warning(
            "structured output method=%s unavailable for %s, fallback to function_calling",
            preferred_method,
            getattr(schema, "__name__", str(schema)),
            exc_info=True,
        )
        return llm.with_structured_output(schema, method="function_calling")


def _normalize_tasks(raw_tasks: list) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_tasks[:5], start=1):
        if hasattr(item, "model_dump"):
            data = item.model_dump()
        elif hasattr(item, "dict"):
            data = item.dict()
        elif isinstance(item, dict):
            data = dict(item)
        else:
            continue

        question = str(data.get("question") or "").strip()
        if not question:
            continue

        task_id = str(data.get("id") or f"t{index}").strip() or f"t{index}"
        if task_id in seen_ids:
            task_id = f"t{index}"
        seen_ids.add(task_id)

        depends_on = data.get("depends_on") or []
        if not isinstance(depends_on, list):
            depends_on = []

        tasks.append({
            "id": task_id,
            "question": question,
            "intent_hint": data.get("intent_hint"),
            "depends_on": [str(v) for v in depends_on if str(v).strip()],
            "reason": str(data.get("reason") or ""),
        })

    valid_ids = {t["id"] for t in tasks}
    for task in tasks:
        task["depends_on"] = [dep for dep in task["depends_on"] if dep in valid_ids and dep != task["id"]]
    return tasks


_HEURISTIC_SPLIT_PATTERN = re.compile(
    r"(?:[？?。；;]\s*)|"
    r"(?:[，,]?\s*(?:然后|还有|另外|顺便|再帮我|再|以及|并且|此外|同时|另|接着)\s*)|"
    r"(?:[，,]\s*(?=(?:第[一二三四五六七八九十0-9]+[个款]|它们|他们|这几款|那几款|上面|前面)))"
)


def _heuristic_split_tasks(question: str) -> list[dict[str, Any]]:
    """LLM planner 不可用时的保守兜底，只处理明显多问句。"""
    parts = [p.strip(" ，,。？?；;") for p in _HEURISTIC_SPLIT_PATTERN.split(question) if p.strip(" ，,。？?；;")]
    if len(parts) < 2:
        return []

    tasks: list[dict[str, Any]] = []
    for idx, part in enumerate(parts[:5], start=1):
        task_id = f"t{idx}"
        depends_on: list[str] = []
        if idx > 1 and re.search(
            r"(这些|它们|他们|她们|上面|前面|刚才|推荐的这些|这几款|那几款|第[一二三四五六七八九十0-9]+[个款])",
            part,
        ):
            depends_on = ["t1"]
        tasks.append({
            "id": task_id,
            "question": part,
            "intent_hint": _guess_intent_hint(part),
            "depends_on": depends_on,
            "reason": "启发式拆分",
        })
    return tasks


def _guess_intent_hint(text: str) -> str:
    if re.search(r"(推荐|找|商品|价格|多少钱|对比|比较|库存|规格|性价比|便宜|贵|评分|销量)", text):
        return "shopping"
    if re.search(r"(成分|功效|原理|怎么用|适合什么|能不能|副作用|禁忌|区别|为什么|浓度)", text):
        return "knowledge"
    if re.search(r"(你好|谢谢|再见|总结|刚才问了什么|你是谁)", text):
        return "chitchat"
    return "unknown"


def _format_subtask_heading(index: int, total: int, question: str) -> str:
    prefix = "我会分成几个部分依次回答：\n\n" if index == 0 else "\n\n"
    return f"{prefix}{index + 1}. {question}\n"


def _build_orchestrator_answer(sub_results: list[dict[str, Any]]) -> str:
    if not sub_results:
        return "我暂时没能完成这个复合问题的拆解，请你换个方式再问一次。"

    parts = ["我会分成几个部分依次回答："]
    for index, result in enumerate(sub_results, start=1):
        question = result.get("question") or f"第 {index} 个问题"
        answer = (result.get("answer") or "").strip()
        if not answer:
            if result.get("error"):
                answer = "这一部分暂时处理失败，请稍后再试。"
            else:
                answer = "这一部分暂时没有得到明确结果。"
        parts.append(f"{index}. {question}\n{answer}")
    return "\n\n".join(parts)


def _dedupe_product_cards(cards_iter) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for card in cards_iter:
        if not isinstance(card, dict):
            continue
        key = str(card.get("product_id") or card.get("id") or card.get("title") or len(out))
        if key in seen:
            continue
        seen.add(key)
        out.append(card)
    return out


def _dedupe_sources(sources_iter) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources_iter:
        if hasattr(source, "model_dump"):
            source = source.model_dump()
        elif hasattr(source, "dict"):
            source = source.dict()
        if not isinstance(source, dict):
            continue
        key = str(
            source.get("url")
            or source.get("doc_id")
            or source.get("doc")
            or source.get("doc_name")
            or source.get("title")
            or len(out)
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(source)
    return out


def _collect_tags(meta: Dict[str, Any]) -> set[str]:
    tags: set[str] = set()
    stack = [meta]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                if key == "tags" and isinstance(value, (list, tuple, set)):
                    tags.update(str(v) for v in value)
                elif key in {"metadata", "config"} and isinstance(value, dict):
                    stack.append(value)
        elif isinstance(item, (list, tuple, set)):
            tags.update(str(v) for v in item)
    return tags


def _flatten_namespace(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, (list, tuple, set)):
        for part in value:
            out.extend(_flatten_namespace(part))
    elif value is not None:
        out.append(str(value))
    return out
