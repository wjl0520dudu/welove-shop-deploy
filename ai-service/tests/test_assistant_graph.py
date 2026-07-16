import asyncio
from unittest.mock import MagicMock

from agents.schemas import IntentDecision, OrchestratorDecision
from agents.memory import remember_product_cards, get_business_memory
from assistant.graph import AssistantGraph, _heuristic_split_tasks
from assistant.orchestration import PlanValidationError, build_task_levels


def clear_business_memory():
    """老测试遗留的钩子，现在业务记忆按 conversation_id 隔离，测试用不同 cid 即可，
    这里保留空实现避免 import 失败。"""
    pass


def _dummy_llm():
    """构造一个够用的 llm mock：只需要 `.with_structured_output(...)` 不报错即可。

    AssistantGraph.__init__ 里调 `llm.with_structured_output(IntentDecision, method="function_calling")`
    产出 `self._router_llm`，但被 _patch_router 覆盖 _route 后 _router_llm 根本用不上，
    所以返回值是啥无所谓。历史用 llm=_dummy_llm() 直接抛 AttributeError。
    """
    llm = MagicMock()
    llm.with_structured_output.return_value = MagicMock()
    return llm


class FakeShoppingAgent:
    def __init__(self):
        self.calls = []

    async def run(self, *, question, messages, business_memory,
                  conversation_id=None, user_id=None, jwt_token=None):
        # 记录调用参数供断言（包括 business_memory，用于跨轮共享测试）
        self.calls.append({
            "question": question,
            "business_memory": business_memory,
            "conversation_id": conversation_id,
        })
        product_cards = [{"product_id": 7, "title": "安耐晒", "brand": "Shiseido"}]
        # 真的 ShoppingAgent 会把 product_cards 写进 Store（供下一轮跨轮记忆读取）
        # Fake agent 也得模拟这个行为，否则 test_business_memory_shared_across_turns 拿不到
        if conversation_id:
            try:
                await remember_product_cards(conversation_id, user_id, product_cards)
            except Exception:  # noqa: BLE001
                pass
        return {
            "answer": "找到的防晒商品如下。",
            "task_type": "shopping",
            "product_cards": product_cards,
            "sources": [], "tool_calls": [], "error": False,
        }


class FakeKnowledgeAgent:
    def __init__(self):
        self.calls = []

    async def run(self, *, messages, conversation_id="", user_id=None):
        # knowledge_node 调 .run（不是 .ask）；参数是 messages / conversation_id / user_id
        # question 从 messages 里最后一条 human message 取（供老测试断言）
        last_user = ""
        for m in reversed(messages or []):
            role = getattr(m, "type", "") or (m.get("role", "") if isinstance(m, dict) else "")
            content = getattr(m, "content", "") if not isinstance(m, dict) else m.get("content", "")
            if role in ("human", "user") and content:
                last_user = content
                break
        self.calls.append({"question": last_user, "conversation_id": conversation_id})
        return {
            "answer": "防晒霜的成分主要包括二氧化钛等。",
            "task_type": "knowledge",
            "sources": [{"doc_id": 1, "doc_name": "成分手册"}],
            "has_answer": True,
            "error": False,
        }


def _patch_router(monkeypatch, route):
    """让 AssistantGraph._route 直接返回预设 route，跳过真 LLM。

    历史版本 patch 的是 `assistant.graph.classify_intent`（老 API），但当前 graph
    走 `_route` 方法内部的 `self._router_llm.ainvoke(...)`（with_structured_output 直链）
    ，那个函数已经被移除。这里改成 patch `AssistantGraph._route` 本身，
    覆盖面更精确、不依赖 LLM 的具体实现。
    """
    async def fake_route(self, state):
        return {"route": route, "route_reason": "test"}

    monkeypatch.setattr("assistant.graph.AssistantGraph._route", fake_route)


def _patch_simple_orchestrator(monkeypatch):
    async def fake_analyze(self, state):
        return {
            "original_question": state.get("question", ""),
            "orchestrator_mode": "simple",
            "orchestrator_reason": "test simple",
            "sub_questions": [],
            "sub_results": [],
            "current_subquestion_index": 0,
        }

    monkeypatch.setattr("assistant.graph.AssistantGraph._analyze_request", fake_analyze)


class FakePlanner:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    async def ainvoke(self, *args, **kwargs):
        self.calls += 1
        if not self.responses:
            return None
        if len(self.responses) == 1:
            return self.responses[0]
        return self.responses.pop(0)


def _patch_complex_orchestrator(monkeypatch):
    async def fake_analyze(self, state):
        return {
            "original_question": state.get("question", ""),
            "orchestrator_mode": "complex",
            "orchestrator_reason": "test complex",
            "sub_questions": [
                {
                    "id": "t1",
                    "question": "给我推荐适合油皮的防晒",
                    "intent_hint": "shopping",
                    "depends_on": [],
                    "use_image": False,
                    "reason": "推荐商品",
                },
                {
                    "id": "t2",
                    "question": "烟酰胺是什么成分？",
                    "intent_hint": "knowledge",
                    "depends_on": [],
                    "use_image": False,
                    "reason": "知识查询",
                },
                {
                    "id": "t3",
                    "question": "你推荐的这些商品价格对比如何？",
                    "intent_hint": "shopping",
                    "depends_on": ["t1"],
                    "use_image": False,
                    "reason": "依赖推荐结果做对比",
                },
            ],
            "sub_results": [],
            "current_subquestion_index": 0,
        }

    async def fake_route(self, state):
        question = state.get("question", "")
        route = "knowledge" if "成分" in question else "shopping"
        return {"route": route, "route_reason": f"route for {question}"}

    monkeypatch.setattr("assistant.graph.AssistantGraph._analyze_request", fake_analyze)
    monkeypatch.setattr("assistant.graph.AssistantGraph._route", fake_route)


def test_router_routes_to_shopping(monkeypatch):
    async def run():
        clear_business_memory()
        _patch_simple_orchestrator(monkeypatch)
        _patch_router(monkeypatch, "shopping")
        shopping = FakeShoppingAgent()
        graph = AssistantGraph(llm=_dummy_llm(), shopping_agent=shopping, knowledge_agent=FakeKnowledgeAgent())
        result = await graph.run(question="推荐一款防晒", conversation_id="c1", user_id=1)
        assert result["task_type"] == "shopping"
        assert result["product_cards"][0]["product_id"] == 7
        assert shopping.calls[0]["question"] == "推荐一款防晒"
    asyncio.run(run())


def test_router_routes_to_knowledge(monkeypatch):
    async def run():
        _patch_simple_orchestrator(monkeypatch)
        _patch_router(monkeypatch, "knowledge")
        knowledge = FakeKnowledgeAgent()
        graph = AssistantGraph(llm=_dummy_llm(), shopping_agent=FakeShoppingAgent(), knowledge_agent=knowledge)
        result = await graph.run(question="防晒霜的成分是什么")
        assert result["task_type"] == "knowledge"
        assert result["sources"][0]["doc_name"] == "成分手册"
        assert knowledge.calls[0]["question"] == "防晒霜的成分是什么"
    asyncio.run(run())


def test_router_routes_to_chitchat(monkeypatch):
    async def run():
        _patch_simple_orchestrator(monkeypatch)
        _patch_router(monkeypatch, "chitchat")
        # chitchat_node 内部会跟 llm 交互；用 RunnableLambda 构造可组合的假 LLM。
        # AssistantGraph 构造时会调 llm.with_structured_output(...)，为此在外面套一层
        # duck-type mock 让它不炸（真正的 chitchat 走 llm 本身，不走 _router_llm）。
        from langchain_core.runnables import RunnableLambda
        from langchain_core.messages import AIMessage
        async def _fake_llm(messages, config=None, **kwargs):
            return AIMessage(content="你好呀！有什么想买的吗？")
        chitchat_llm = RunnableLambda(_fake_llm)
        # 给它加个 .with_structured_output（AssistantGraph.__init__ 需要）
        chitchat_llm.with_structured_output = lambda *a, **k: MagicMock()
        graph = AssistantGraph(llm=chitchat_llm, shopping_agent=FakeShoppingAgent(),
                               knowledge_agent=FakeKnowledgeAgent())
        result = await graph.run(question="你好")
        assert result["task_type"] == "chitchat"
        assert "你好" in result["answer"]
    asyncio.run(run())



def test_router_routes_to_unknown(monkeypatch):
    async def run():
        _patch_simple_orchestrator(monkeypatch)
        _patch_router(monkeypatch, "unknown")
        graph = AssistantGraph(llm=_dummy_llm(), shopping_agent=FakeShoppingAgent(), knowledge_agent=FakeKnowledgeAgent())
        result = await graph.run(question="随便说点啥")
        assert result["task_type"] == "unknown"
        assert result["answer"]
    asyncio.run(run())


def test_no_llm_routes_to_unknown(monkeypatch):
    async def run():
        _patch_simple_orchestrator(monkeypatch)
        _patch_router(monkeypatch, "unknown")
        graph = AssistantGraph(llm=None, shopping_agent=None, knowledge_agent=None)
        result = await graph.run(question="推荐一款防晒")
        assert result["task_type"] == "unknown"
    asyncio.run(run())


def test_business_memory_shared_across_turns(monkeypatch):
    """跨轮记忆：第一轮 shopping 写入的 last_product_cards，第二轮从 Store 读到。

    真的 ShoppingAgent.run 内部自己从 Store 拿 memory（不依赖 state["business_memory"]），
    所以断言点改成"直接查 Store"，不再断言 shopping.calls[i]["business_memory"]。
    """
    async def run():
        clear_business_memory()
        _patch_simple_orchestrator(monkeypatch)
        _patch_router(monkeypatch, "shopping")
        shopping = FakeShoppingAgent()
        graph = AssistantGraph(llm=_dummy_llm(), shopping_agent=shopping,
                               knowledge_agent=FakeKnowledgeAgent())
        await graph.run(question="推荐一款防晒", conversation_id="c-mem", user_id=42)

        # 第一轮跑完，Store 里应该有 last_product_cards（FakeShoppingAgent 内部会写）
        mem = await get_business_memory("c-mem", 42)
        assert mem.get("last_product_cards")
        assert mem["last_product_cards"][0]["product_id"] == 7

        # 第二轮再跑一次，Store 里的记忆继续存在（未被清空）
        shopping.calls.clear()
        await graph.run(question="第一个怎么样", conversation_id="c-mem", user_id=42)
        mem2 = await get_business_memory("c-mem", 42)
        assert mem2.get("last_product_cards")
    asyncio.run(run())


def test_error_node_returns_error_fields(monkeypatch):
    async def run():
        _patch_simple_orchestrator(monkeypatch)
        _patch_router(monkeypatch, "shopping")
        class BoomShopping:
            async def run(self, **kwargs):
                raise RuntimeError("boom")
        graph = AssistantGraph(llm=_dummy_llm(), shopping_agent=BoomShopping(), knowledge_agent=FakeKnowledgeAgent())
        result = await graph.run(question="推荐一款防晒")
        assert result["error"] is True
        assert result["error_code"] == "AI_SHOPPING_ERROR"
    asyncio.run(run())


def test_run_id_and_trace_id_present(monkeypatch):
    async def run():
        _patch_simple_orchestrator(monkeypatch)
        _patch_router(monkeypatch, "unknown")
        graph = AssistantGraph(llm=_dummy_llm(), shopping_agent=None, knowledge_agent=None)
        result = await graph.run(question="hi", conversation_id="c-rt")
        assert result["run_id"]
        assert result["trace_id"]
    asyncio.run(run())


def test_orchestrator_executes_complex_tasks_in_order(monkeypatch):
    async def run():
        _patch_complex_orchestrator(monkeypatch)
        shopping = FakeShoppingAgent()
        knowledge = FakeKnowledgeAgent()
        graph = AssistantGraph(llm=_dummy_llm(), shopping_agent=shopping, knowledge_agent=knowledge)

        result = await graph.run(
            question="给我推荐适合油皮的防晒，然后我还想知道烟酰胺是什么成分，还有你推荐的这些价格对比如何？",
            conversation_id="c-orch",
            user_id=8,
        )

        assert result["task_type"] == "orchestrator"
        assert result["orchestrator_mode"] == "complex"
        assert [c["question"] for c in shopping.calls] == [
            "给我推荐适合油皮的防晒",
            "你推荐的这些商品价格对比如何？",
        ]
        assert knowledge.calls[0]["question"] == "烟酰胺是什么成分？"
        assert len(result["sub_results"]) == 3
        assert result["task_levels"] == [["t1", "t2"], ["t3"]]
        assert [item["status"] for item in result["sub_results"]] == ["success", "success", "success"]
        assert result["sub_questions"][2]["depends_on"] == ["t1"]
        assert shopping.calls[1]["business_memory"]["last_product_cards"][0]["product_id"] == 7
        assert result["product_cards"][0]["product_id"] == 7
        assert result["sources"][0]["doc_name"] == "成分手册"
        assert "1. 给我推荐适合油皮的防晒" in result["answer"]
        assert "2. 烟酰胺是什么成分？" in result["answer"]
        assert "3. 你推荐的这些商品价格对比如何？" in result["answer"]
    asyncio.run(run())


def test_orchestrator_prepare_subtask_stream_heading():
    async def run():
        graph = AssistantGraph.__new__(AssistantGraph)
        events = []
        async for event in graph._translate_update_event(
            "prepare_subtask",
            {
                "active_subtask": {"id": "t1", "question": "给我推荐防晒"},
                "subtask_heading": "我会分成几个部分依次回答：\n\n1. 给我推荐防晒\n",
            },
        ):
            events.append(event)

        assert events[0]["type"] == "orchestrator_subtask"
        assert events[1] == {
            "type": "token",
            "data": {"content": "我会分成几个部分依次回答：\n\n1. 给我推荐防晒\n"},
        }
    asyncio.run(run())


def test_initial_state_clears_previous_task_and_image_scope():
    graph = AssistantGraph.__new__(AssistantGraph)
    first, _, _ = graph._make_initial_state(question="找同款", image_url="/a.jpg")
    second, _, _ = graph._make_initial_state(question="只问知识")
    assert first["image_url"] == "/a.jpg"
    assert second["image_url"] == ""
    assert second["active_subtask"] == {}
    assert second["orchestrator_plan_error"] == ""


def test_orchestrator_execute_dag_streams_ordered_results():
    async def run():
        graph = AssistantGraph.__new__(AssistantGraph)
        sub_results = [
            {"id": "t1", "question": "问题一", "status": "success", "route": "shopping", "answer": "答案一"},
            {"id": "t2", "question": "问题二", "status": "success", "route": "knowledge", "answer": "答案二"},
        ]
        events = []
        async for event in graph._translate_update_event("execute_dag", {"sub_results": sub_results}):
            events.append(event)

        assert [event["type"] for event in events] == [
            "orchestrator_subtask", "orchestrator_subtask", "token",
        ]
        assert "1. 问题一" in events[-1]["data"]["content"]
        assert "2. 问题二" in events[-1]["data"]["content"]
    asyncio.run(run())


def test_build_task_levels_rejects_duplicate_illegal_and_cycle():
    duplicate = [
        {"id": "t1", "question": "a", "depends_on": []},
        {"id": "t1", "question": "b", "depends_on": []},
    ]
    try:
        build_task_levels(duplicate)
        assert False, "duplicate task ids must be rejected"
    except PlanValidationError as exc:
        assert "重复任务 ID" in str(exc)

    illegal = [
        {"id": "t1", "question": "a", "depends_on": []},
        {"id": "t2", "question": "b", "depends_on": ["missing"]},
    ]
    try:
        build_task_levels(illegal)
        assert False, "missing dependency must be rejected"
    except PlanValidationError as exc:
        assert "依赖不存在" in str(exc)

    cyclic = [
        {"id": "t1", "question": "a", "depends_on": ["t2"]},
        {"id": "t2", "question": "b", "depends_on": ["t1"]},
    ]
    try:
        build_task_levels(cyclic)
        assert False, "cyclic dependency must be rejected"
    except PlanValidationError as exc:
        assert "循环" in str(exc)

    too_many = [
        {"id": f"t{i}", "question": str(i), "depends_on": []}
        for i in range(1, 7)
    ]
    try:
        build_task_levels(too_many, max_tasks=5)
        assert False, "task count limit must be enforced"
    except PlanValidationError as exc:
        assert "超过上限" in str(exc)

    too_deep = [
        {"id": "t1", "question": "1", "depends_on": []},
        {"id": "t2", "question": "2", "depends_on": ["t1"]},
        {"id": "t3", "question": "3", "depends_on": ["t2"]},
    ]
    try:
        build_task_levels(too_deep, max_depth=2)
        assert False, "dependency depth limit must be enforced"
    except PlanValidationError as exc:
        assert "依赖深度" in str(exc)


def test_orchestrator_runs_same_level_tasks_concurrently(monkeypatch):
    async def run():
        started = 0
        both_started = asyncio.Event()

        async def wait_for_peer():
            nonlocal started
            started += 1
            if started == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), timeout=0.5)

        class BarrierShopping(FakeShoppingAgent):
            async def run(self, **kwargs):
                await wait_for_peer()
                return await super().run(**kwargs)

        class BarrierKnowledge(FakeKnowledgeAgent):
            async def run(self, **kwargs):
                await wait_for_peer()
                return await super().run(**kwargs)

        async def fake_analyze(self, state):
            return {
                "original_question": state.get("question", ""),
                "orchestrator_mode": "complex",
                "orchestrator_reason": "parallel test",
                "sub_questions": [
                    {"id": "t1", "question": "推荐防晒", "intent_hint": "shopping", "depends_on": [], "use_image": False},
                    {"id": "t2", "question": "烟酰胺是什么", "intent_hint": "knowledge", "depends_on": [], "use_image": False},
                ],
                "sub_results": [],
            }

        monkeypatch.setattr("assistant.graph.AssistantGraph._analyze_request", fake_analyze)
        graph = AssistantGraph(
            llm=_dummy_llm(),
            shopping_agent=BarrierShopping(),
            knowledge_agent=BarrierKnowledge(),
        )
        result = await asyncio.wait_for(graph.run(question="两个独立问题", conversation_id="c-par"), timeout=1)
        assert result["task_levels"] == [["t1", "t2"]]
        assert all(item["status"] == "success" for item in result["sub_results"])
    asyncio.run(run())


def test_orchestrator_failure_isolated_and_dependency_blocked(monkeypatch):
    async def run():
        calls = 0

        class BoomShopping:
            async def run(self, **kwargs):
                nonlocal calls
                calls += 1
                raise RuntimeError("shopping boom")

        async def fake_analyze(self, state):
            return {
                "original_question": state.get("question", ""),
                "orchestrator_mode": "complex",
                "orchestrator_reason": "failure test",
                "sub_questions": [
                    {"id": "t1", "question": "推荐商品", "intent_hint": "shopping", "depends_on": [], "use_image": False},
                    {"id": "t2", "question": "解释烟酰胺", "intent_hint": "knowledge", "depends_on": [], "use_image": False},
                    {"id": "t3", "question": "比较这些商品", "intent_hint": "shopping", "depends_on": ["t1"], "use_image": False},
                ],
                "sub_results": [],
            }

        monkeypatch.setattr("assistant.graph.AssistantGraph._analyze_request", fake_analyze)
        graph = AssistantGraph(
            llm=_dummy_llm(), shopping_agent=BoomShopping(), knowledge_agent=FakeKnowledgeAgent(),
        )
        result = await graph.run(question="复合问题", conversation_id="c-failure")
        by_id = {item["id"]: item for item in result["sub_results"]}
        assert by_id["t1"]["status"] == "failed"
        assert by_id["t2"]["status"] == "success"
        assert by_id["t3"]["status"] == "blocked"
        assert by_id["t3"]["error_code"] == "AI_ORCHESTRATOR_DEPENDENCY_FAILED"
        assert calls == 1
        assert result["error"] is True
        assert result["error_code"] == "AI_ORCHESTRATOR_PARTIAL_ERROR"
    asyncio.run(run())


def test_orchestrator_task_timeout_does_not_drop_independent_result(monkeypatch):
    async def run():
        class SlowShopping:
            async def run(self, **kwargs):
                await asyncio.sleep(0.2)
                return {"answer": "late", "task_type": "shopping", "error": False}

        async def fake_analyze(self, state):
            return {
                "original_question": state.get("question", ""),
                "orchestrator_mode": "complex",
                "orchestrator_reason": "timeout test",
                "sub_questions": [
                    {"id": "t1", "question": "慢推荐", "intent_hint": "shopping", "depends_on": [], "use_image": False},
                    {"id": "t2", "question": "解释烟酰胺", "intent_hint": "knowledge", "depends_on": [], "use_image": False},
                ],
                "sub_results": [],
            }

        monkeypatch.setattr("assistant.graph.AssistantGraph._analyze_request", fake_analyze)
        monkeypatch.setattr("assistant.graph.config.ORCHESTRATOR_TASK_TIMEOUT_SECONDS", 0.03)
        graph = AssistantGraph(
            llm=_dummy_llm(), shopping_agent=SlowShopping(), knowledge_agent=FakeKnowledgeAgent(),
        )
        result = await graph.run(question="超时隔离", conversation_id="c-timeout")
        by_id = {item["id"]: item for item in result["sub_results"]}
        assert by_id["t1"]["status"] == "timeout"
        assert by_id["t1"]["error_code"] == "AI_ORCHESTRATOR_TASK_TIMEOUT"
        assert by_id["t2"]["status"] == "success"
    asyncio.run(run())


def test_invalid_orchestrator_plan_returns_stable_error():
    graph = AssistantGraph.__new__(AssistantGraph)
    decision = {
        "mode": "complex",
        "reason": "bad plan",
        "tasks": [
            {"id": "t1", "question": "a", "intent_hint": "shopping", "depends_on": ["t2"]},
            {"id": "t2", "question": "b", "intent_hint": "knowledge", "depends_on": ["t1"]},
        ],
    }
    result = graph._normalize_orchestrator_decision("test", decision)
    assert result["error"] is True
    assert result["error_code"] == "AI_ORCHESTRATOR_PLAN_INVALID"
    assert "循环" in result["message"]


def test_complex_image_is_scoped_to_shopping_task(monkeypatch):
    async def run():
        multimodal_calls = []

        async def fake_multimodal(*, llm, query_text, image_url, top_k):
            multimodal_calls.append({"query_text": query_text, "image_url": image_url})
            return {
                "answer": "找到图片中的同类商品。",
                "task_type": "shopping",
                "product_cards": [{"product_id": 88, "title": "方便面"}],
                "sources": [],
                "tool_calls": [],
                "error": False,
            }

        async def fake_analyze(self, state):
            return {
                "original_question": state.get("question", ""),
                "orchestrator_mode": "complex",
                "orchestrator_reason": "image scope test",
                "sub_questions": [
                    {"id": "t1", "question": "找同类商品", "intent_hint": "shopping", "depends_on": [], "use_image": True},
                    {"id": "t2", "question": "方便面适合减脂期吗", "intent_hint": "knowledge", "depends_on": [], "use_image": False},
                ],
                "sub_results": [],
            }

        monkeypatch.setattr("assistant.graph.AssistantGraph._analyze_request", fake_analyze)
        monkeypatch.setattr("assistant.nodes._multimodal_shopping", fake_multimodal)
        knowledge = FakeKnowledgeAgent()
        graph = AssistantGraph(
            llm=_dummy_llm(), shopping_agent=FakeShoppingAgent(), knowledge_agent=knowledge,
        )
        result = await graph.run(
            question="按图片找商品，并解释是否适合减脂",
            image_url="/weloveshop/uploads/noodle.jpg",
            conversation_id="c-image-dag",
        )
        assert len(multimodal_calls) == 1
        assert knowledge.calls[0]["question"] == "方便面适合减脂期吗"
        assert [item["route"] for item in result["sub_results"]] == ["shopping", "knowledge"]
        assert [item["use_image"] for item in result["sub_results"]] == [True, False]
    asyncio.run(run())


def test_analyze_request_falls_back_when_llm_returns_none():
    async def run():
        graph = AssistantGraph(llm=_dummy_llm(), shopping_agent=FakeShoppingAgent(), knowledge_agent=FakeKnowledgeAgent())
        graph._orchestrator_llm = FakePlanner(None, None)

        result = await graph._analyze_request({
            "question": "推荐三款补水面霜，然后比较这些哪个更便宜，第二个含什么成分？",
            "conversation_id": "c-none",
            "user_id": 1,
        })

        assert graph._orchestrator_llm.calls == 2
        assert result["orchestrator_mode"] == "complex"
        assert len(result["sub_questions"]) == 3
        assert result["sub_questions"][1]["depends_on"] == ["t1"]
        assert result["sub_questions"][2]["depends_on"] == ["t1"]
    asyncio.run(run())


def test_analyze_request_falls_back_when_llm_returns_empty_complex():
    async def run():
        graph = AssistantGraph(llm=_dummy_llm(), shopping_agent=FakeShoppingAgent(), knowledge_agent=FakeKnowledgeAgent())
        graph._orchestrator_llm = FakePlanner(
            OrchestratorDecision(mode="complex", reason="多任务但未给 tasks", tasks=[]),
        )

        result = await graph._analyze_request({
            "question": "推荐三款补水面霜，然后比较这些哪个更便宜，第二个含什么成分？",
            "conversation_id": "c-empty-complex",
            "user_id": 1,
        })

        assert result["orchestrator_mode"] == "complex"
        assert len(result["sub_questions"]) == 3
        assert result["sub_questions"][0]["question"] == "推荐三款补水面霜"
    asyncio.run(run())


def test_heuristic_splits_second_item_reference():
    tasks = _heuristic_split_tasks("推荐三款补水面霜，然后比较这些哪个更便宜，第二个含什么成分？")

    assert [t["question"] for t in tasks] == [
        "推荐三款补水面霜",
        "比较这些哪个更便宜",
        "第二个含什么成分",
    ]
    assert [t["intent_hint"] for t in tasks] == ["shopping", "shopping", "knowledge"]
    assert tasks[1]["depends_on"] == ["t1"]
    assert tasks[2]["depends_on"] == ["t1"]


# ─────────────────────────────────────────────────────────────
# 多模态（image_url）分支测试
# ─────────────────────────────────────────────────────────────

def test_multimodal_shopping_route_shortcut(monkeypatch):
    """有 image_url 时，_route 直接判 shopping，不走 router LLM。"""
    async def run():
        _patch_simple_orchestrator(monkeypatch)
        graph = AssistantGraph(llm=_dummy_llm(), shopping_agent=FakeShoppingAgent(),
                               knowledge_agent=FakeKnowledgeAgent())
        decision = await graph._route({
            "question": "找同款",
            "image_url": "/weloveshop/products/c1/xxx.jpg",
        })
        assert decision["route"] == "shopping"
        assert "多模态" in decision["route_reason"]
    asyncio.run(run())


def test_multimodal_shopping_node_bypasses_shopping_agent(monkeypatch):
    """带 image_url 的 shopping_node 直接调 search_multimodal_v1，跳过 ShoppingAgent。

    校验点：
    - 走多模态检索返回商品卡片
    - ShoppingAgent.run 完全没被调用
    - 结果里的 tool_calls 记录了 search_multimodal_v1
    """
    async def run():
        _patch_simple_orchestrator(monkeypatch)

        # patch multimodal 检索：不真调向量库
        multimodal_calls = []
        async def fake_search_multimodal_v1(query_text, query_image_url, top_k=5, filters=None):
            multimodal_calls.append({
                "query_text": query_text,
                "query_image_url": query_image_url,
                "top_k": top_k,
            })
            return [
                {"product_id": 42, "title": "跑鞋", "brand": "Nike",
                 "base_price": 499, "image_url": "/x.jpg",
                 "sub_category": "跑鞋"},
                {"product_id": 43, "title": "跑鞋2", "brand": "Adidas",
                 "base_price": 599, "image_url": "/y.jpg",
                 "sub_category": "跑鞋"},
            ]
        monkeypatch.setattr(
            "shopping.multimodal_search.search_multimodal_v1",
            fake_search_multimodal_v1,
        )

        # 让写推荐话术的 LLM 走 fake，返回固定文本
        from langchain_core.runnables import RunnableLambda
        async def fake_llm(prompt, config=None, **kwargs):
            from langchain_core.messages import AIMessage
            return AIMessage(content="这两款都很适合日常穿搭。")
        llm = RunnableLambda(fake_llm)
        # 满足 __init__ 里的 with_structured_output 调用
        llm.with_structured_output = MagicMock(return_value=MagicMock())

        # ShoppingAgent 若被调用会抛异常暴露
        class BoomShoppingAgent:
            async def run(self, **kwargs):
                raise AssertionError("ShoppingAgent should not be called when image_url is set")

        graph = AssistantGraph(llm=llm, shopping_agent=BoomShoppingAgent(),
                               knowledge_agent=FakeKnowledgeAgent())
        result = await graph.run(
            question="找一双跟这个类似的跑鞋",
            image_url="/weloveshop/products/c3/p_clothes_003_live.jpg",
            conversation_id="c-mm",
            user_id=1,
        )

        assert len(multimodal_calls) == 1
        assert multimodal_calls[0]["query_image_url"] == "/weloveshop/products/c3/p_clothes_003_live.jpg"
        assert result["task_type"] == "shopping"
        assert [c["product_id"] for c in result["product_cards"]] == [42, 43]
        assert any(tc["name"] == "search_multimodal_v1" for tc in result["tool_calls"])
        # 推荐话术来自 fake LLM
        assert "日常穿搭" in result["answer"]
    asyncio.run(run())


def test_text_only_still_uses_shopping_agent(monkeypatch):
    """无 image_url 时保持走 ShoppingAgent，不动原链路。"""
    async def run():
        clear_business_memory()
        _patch_simple_orchestrator(monkeypatch)
        _patch_router(monkeypatch, "shopping")
        shopping = FakeShoppingAgent()
        graph = AssistantGraph(llm=_dummy_llm(), shopping_agent=shopping,
                               knowledge_agent=FakeKnowledgeAgent())
        result = await graph.run(question="推荐一款防晒", conversation_id="c-text-only")
        # ShoppingAgent 被调用了（多模态路径不会调它）
        assert len(shopping.calls) == 1
        assert result["product_cards"][0]["product_id"] == 7
    asyncio.run(run())


def test_image_only_no_question_still_works(monkeypatch):
    """纯图搜索：question 为空 + 有 image_url，仍能走多模态分支。"""
    async def run():
        _patch_simple_orchestrator(monkeypatch)

        async def fake_search_multimodal_v1(query_text, query_image_url, top_k=5, filters=None):
            # 纯图搜索时 query_text 应为空
            assert not (query_text or "").strip()
            return [
                {"product_id": 99, "title": "同款跑鞋", "brand": "Nike",
                 "base_price": 599, "image_url": "/z.jpg", "sub_category": "跑鞋"},
            ]
        monkeypatch.setattr(
            "shopping.multimodal_search.search_multimodal_v1",
            fake_search_multimodal_v1,
        )

        # LLM 走 fake，不生成话术也行
        from langchain_core.runnables import RunnableLambda
        async def fake_llm(prompt, config=None, **kwargs):
            from langchain_core.messages import AIMessage
            return AIMessage(content="根据你上传的图片，找到这款相似商品。")
        llm = RunnableLambda(fake_llm)
        llm.with_structured_output = MagicMock(return_value=MagicMock())

        graph = AssistantGraph(llm=llm, shopping_agent=FakeShoppingAgent(),
                               knowledge_agent=FakeKnowledgeAgent())
        result = await graph.run(
            question="",  # 纯图搜索
            image_url="/weloveshop/products/c3/p_clothes_003_live.jpg",
            conversation_id="c-image-only",
            user_id=1,
        )

        assert result["task_type"] == "shopping"
        assert result["product_cards"][0]["product_id"] == 99
        # route_reason 里应有"带图请求"标记，证明走了多模态短路
        assert "多模态" in (result.get("route_reason") or "")
    asyncio.run(run())
