# Orchestrator 真实 LLM 测试报告与待修复问题

> **状态：✅ 已修复（2026-07-13）**
>
> 本文档最初记录了 Orchestrator 在真实 LLM 环境下发现的 3 个 bug（`function_calling` 空返回 / 空响应静默降级 / 启发式漏切"第 X 个"）。
> 已在同日完整修复，回归测试 32/32 单元测试通过 + 真实 LLM 3 轮 24/24 通过。
> 文档保留作为设计决策与调查过程的历史记录。
>
> 修复落地位置：`ai-service/assistant/graph.py`（`_build_structured_llm` / `_analyze_request` 空返回重试与兜底 / `_HEURISTIC_SPLIT_PATTERN` 前瞻断言补充）
> 修复验证脚本：`ai-service/scripts/test_orchestrator_planner.py`（真实 LLM 8 case 回归）

---

## 原始问题报告（历史记录）

> 生成时间：2026-07-13
> 测试环境：`d:\dev\env\conda_envs\wlagt`，LLM=`qwen-plus`（.env 里配置的 `LLM_MODEL`）
> 测试脚本：`ai-service/scripts/test_orchestrator_planner.py`（一次性脚本，本报告完成后可删）
> 测试对象：`ai-service/assistant/graph.py` 中 `AssistantGraph._analyze_request` 走的 `_orchestrator_llm`（用 `with_structured_output(OrchestratorDecision, method="function_calling")` 构造）
> 测试用例来源：`docs/orchestrator-test-data-and-results.md` 里 DeepSeek 建议的 8 个测试问题

## 0. 一句话结论

单元测试 (`test_assistant_graph.py` / `test_api_contract.py` / `test_assistant_stream_filtering.py` 共 29 个) 全部通过，Mock 层没问题；**但真实 LLM 拆解通道在部分复合问题上稳定失败，且失败被静默降级为 simple**——用户能看到的表现是"多问题请求被当成单问题回答，只答了第一个意图"。

真实 LLM 拆解结果 6/8 通过，另外 2 个失败案例都是关键的跨意图/依赖场景（case 3、case 4）。已经定位到三个具体 bug，需要 gpt5.5 x high 针对性修复。

## 1. 测试执行结果

### 1.1 单元测试（Mock 场景）—— 全部通过

| 测试文件 | 数量 | 结果 |
|---|---|---|
| `tests/test_assistant_graph.py` | 10（含 2 个新增 orchestrator 测试） | ✅ 10/10 |
| `tests/test_api_contract.py` | 15（含 orchestrator 元数据契约） | ✅ 15/15 |
| `tests/test_assistant_stream_filtering.py` | 4 | ✅ 4/4 |

Mock 层验证了下列已经跑通的能力：

- 图结构完整：`analyze_request → prepare_subtask → route_intent → worker → collect_subtask → (loop | synthesize_final) → format_response`
- 复杂问题串行执行子任务，顺序符合预期
- `depends_on` 保留在最终结果里
- `product_cards` / `sources` 聚合去重
- Markdown 分段 `1. / 2. / 3.` 输出
- SSE `orchestrator_subtask` + `token` 事件按顺序 emit
- API 契约包含所有 orchestrator 字段（`orchestrator_mode` / `sub_questions` / `sub_results`）

### 1.2 真实 LLM 拆解测试（qwen-plus）—— 6/8 通过

| # | 用例（已省略部分文字） | 预期 | 实际 | 结果 |
|---|-----|------|------|------|
| 1 | 单意图推荐："给我推荐一款适合油皮的防晒" | simple / 0 tasks | simple / 0 tasks | ✅ |
| 2 | 单意图多细节："烟酰胺是什么、怎么用、注意事项？" | simple / 0 tasks | simple / 0 tasks | ✅ 未被过度拆解 |
| 3 | 跨意图复合："给我推荐适合油皮的防晒，然后我还想知道烟酰胺是什么成分，还有你推荐的这些价格对比如何？" | complex / 3 tasks | **50% simple/0（空返回），50% complex/3 正确** | ❌ 不稳定 |
| 4 | 依赖型商品追问："推荐三款补水面霜，然后比较这些哪个更便宜，第二个含什么成分？" | complex / 3 tasks | **4/4 稳定 simple/0（100% 空返回）** | ❌ 稳定失败 |
| 5 | 多个独立知识问题："烟酰胺和VC能一起用吗？视黄醇晚上怎么用？" | complex / 2 knowledge | complex / 2 knowledge，depends_on 全空 | ✅ 完美 |
| 6 | 元问题："你还记得我刚才问了什么吗？" | simple / 0 tasks | simple / 0 tasks | ✅ |
| 7 | 澄清补充："油皮，预算 200 以内" | simple / 0 tasks | simple / 0 tasks | ✅ 未误拆 |
| 8 | 三步问题："推荐一款防晒，然后说说烟酰胺的功效，还有这些商品哪个便宜" | complex / 3 含 depends_on | complex / 3，`t3.depends_on=["t1"]` | ✅ 完美 |

**Case 3 拆对时的输出（作为参考）**：

```
mode=complex   reason="包含三个独立且需分步处理的意图..."
t1  intent=shopping   deps=[]      q: 给我推荐适合油皮的防晒
t2  intent=knowledge  deps=[]      q: 烟酰胺是什么成分？
t3  intent=shopping   deps=['t1']  q: 你推荐的这些商品价格对比如何？
```

这是这套 Orchestrator 设计能达到的理想产出——说明 Prompt、Schema 和主图结构本身都是对的。问题只出在**输出通道**。

## 2. 定位到的三个具体 Bug

### 🔴 Bug 1：结构化输出通道 `function_calling` 在 qwen-plus 上偶发/稳定空返回

**位置**：`ai-service/assistant/graph.py:44`

```python
self._orchestrator_llm = (
    llm.with_structured_output(OrchestratorDecision, method="function_calling")
    if llm is not None
    else None
)
```

**验证手段**：用 `include_raw=True` 抓 raw AIMessage，观察 case 3/4：

```
[case3 #1] parsed=None  raw.content=""  raw.tool_calls=[]  finish_reason="stop"  model=qwen-plus
[case3 #2] parsed=None  raw.content=""  raw.tool_calls=[]  finish_reason="stop"  model=qwen-plus
[case3 #3] parsed=None  raw.content=""  raw.tool_calls=[]  finish_reason="stop"  model=qwen-plus
[case4 #1] parsed=None  raw.content=""  raw.tool_calls=[]  finish_reason="stop"  model=qwen-plus
[case4 #2] parsed=None  raw.content=""  raw.tool_calls=[]  finish_reason="stop"  model=qwen-plus
[case4 #3] parsed=None  raw.content=""  raw.tool_calls=[]  finish_reason="stop"  model=qwen-plus
```

即：模型正常返回，没有异常，没有 refusal，但**既没有 content 也没有 tool_call**。LangChain 的 `with_structured_output` 解析结果只能是 `None`。

**对比三种 method 的表现（各跑 2 次）**：

| method | case 3 | case 4 |
|---|:---:|:---:|
| `function_calling` | 1 成 1 败 | **0 成 2 败** |
| `json_mode` | 全失败（qwen 报错 `messages must contain the word 'json'`，需在 prompt 里加 "json"） | 同上 |
| `json_schema` | **2 成 0 败** | **2 成 0 败** |

**根因**：这是 qwen 系列 + LangChain OpenAI 兼容通道下 `function_calling` 的已知不稳定，跟 prompt 和 schema 无关。DashScope 的 `response_format={"type": "json_schema", ...}` 走的是模型侧原生结构化输出，稳定得多。

**修复建议**：

```python
# 主用 json_schema，异常回退到 function_calling
def _build_structured_llm(self, llm, schema):
    try:
        return llm.with_structured_output(schema, method="json_schema")
    except Exception:
        return llm.with_structured_output(schema, method="function_calling")
```

或者更简单：直接把 `method="function_calling"` 改成 `method="json_schema"`。改动 1 行。用完 4 次全部通过。

**注意**：`_router_llm` 用的也是 `method="function_calling"`（graph.py:40），但 `IntentDecision` schema 简单（只有 3 个 str/float 字段），没观察到失败。要不要一并换，交给你决定；但 `_orchestrator_llm` 必须换。

---

### 🔴 Bug 2：空返回被静默降级为 simple，启发式兜底不触发

**位置**：`ai-service/assistant/graph.py:118-127` 和 `129-150`

```python
try:
    decision = await self._orchestrator_llm.ainvoke(messages, ...)
except Exception:
    logger.warning("orchestrator: 结构化拆解失败，尝试启发式拆解", exc_info=True)
    return self._fallback_orchestrator_decision(question, "结构化拆解失败")

return self._normalize_orchestrator_decision(question, decision)
```

```python
def _normalize_orchestrator_decision(self, question, decision):
    mode = str(getattr(decision, "mode", "simple") or "simple").lower()  # decision=None → "simple"
    reason = str(getattr(decision, "reason", "") or "")
    raw_tasks = getattr(decision, "tasks", []) or []
    tasks = _normalize_tasks(raw_tasks)
    if mode != "complex" or len(tasks) < 2:
        return { "orchestrator_mode": "simple", ... }  # 静默降级，无日志
    ...
```

**逻辑漏洞**：`_orchestrator_llm.ainvoke(...)` 返回 `None`（不是抛异常）时，代码**不进 `except`**，直接调 `_normalize_orchestrator_decision(question, None)`。`getattr(None, "mode", "simple")` 返回 `"simple"`，一路走到 `mode != "complex"` 分支，**直接返回 simple**：

- 日志里**没有 warning**，运维和开发都看不见
- 启发式兜底 `_fallback_orchestrator_decision` **不被调用**
- 用户看到一个"只答第一个意图"的降级答案

这个 bug 与 Bug 1 叠加，构成了 case 4 的"沉默失效"。即使 Bug 1 修好，也应该修 Bug 2 作为长期防御——将来换模型、换 provider、prompt 太长导致解析失败，都可能重现同样的空 decision。

**修复建议**：

```python
try:
    decision = await self._orchestrator_llm.ainvoke(messages, config={"tags": ["ai_internal"]})
except Exception:
    logger.warning("orchestrator: 结构化拆解失败，尝试启发式拆解", exc_info=True)
    return self._fallback_orchestrator_decision(question, "结构化拆解失败")

if decision is None:
    logger.warning(
        "orchestrator: 结构化拆解返回 None（LLM 空响应），尝试启发式拆解 question=%r",
        question,
    )
    return self._fallback_orchestrator_decision(question, "结构化拆解返回空")

normalized = self._normalize_orchestrator_decision(question, decision)
# 二次防御：LLM 声称 complex 但没给出足够 tasks（拆解半吊子）
if (
    getattr(decision, "mode", "simple") == "complex"
    and normalized.get("orchestrator_mode") == "simple"
):
    logger.warning(
        "orchestrator: LLM 声称 complex 但 tasks<2，走启发式补救 question=%r",
        question,
    )
    return self._fallback_orchestrator_decision(question, "LLM 拆解不完整")
return normalized
```

**同步补一个单元测试**：`test_analyze_request_falls_back_when_llm_returns_none`，patch `_orchestrator_llm.ainvoke` 返回 `None`，断言最终走了 `_fallback_orchestrator_decision`。

---

### 🟡 Bug 3：启发式兜底切分不够，无法拆出"第 X 个 ..."子问句

**位置**：`ai-service/assistant/graph.py:558`

```python
_HEURISTIC_SPLIT_PATTERN = re.compile(
    r"(?:[？?。；;]\s*)|(?:，?\s*(?:然后|还有|另外|顺便|再帮我|再|以及|并且)\s*)"
)
```

**验证**：假设 Bug 1、2 都修了，case 4 走进启发式路径：

```
输入: 推荐三款补水面霜，然后比较这些哪个更便宜，第二个含什么成分？

启发式拆出 2 个（预期 3 个）:
  t1  intent=shopping   deps=[]      q: 推荐三款补水面霜
  t2  intent=shopping   deps=['t1']  q: 比较这些哪个更便宜，第二个含什么成分   ← 应拆开
```

**原因**：正则的连接词表里没有"第 X 个""此外""同时"等常见表达。case 4 用户句子的第二个逗号后紧跟"第二个含什么成分？"，没有明确连接词，切分器把它和前一段并成一段。

**修复建议**：连接词表补上：

```python
_HEURISTIC_SPLIT_PATTERN = re.compile(
    r"(?:[？?。；;]\s*)|"
    r"(?:，?\s*(?:然后|还有|另外|顺便|再帮我|再|以及|并且|此外|同时|另|接着)\s*)|"
    # 追问型分句：跟前一段之间没有连接词，只有一个逗号 + "第 X 个" / "它们" 起头
    r"(?:，\s*(?=(?:第[一二三四五六七八九十][个款]|它们|他们|这几款|那几款|上面|前面)))"
)
```

其中最后一段用**前瞻断言**匹配"逗号 + 追问代词"，只切分不消耗。加上后 case 4 应能拆出 3 个 task，且第 2、3 都能靠 `_heuristic_split_tasks` 里已有的正则识别为 `depends_on=['t1']`。

**建议同步做**：`_guess_intent_hint` 里也补一下——"第 X 个含什么成分"应该被识别为 knowledge（现在含"成分"→ knowledge，OK；但如果句子是"第二个多少钱" → 应识别为 shopping，现在"多少钱"关键词已经在 shopping 里，也 OK。这块只需要在 pattern 修好后跑一次单测验证）。

---

## 3. 修复优先级

| # | 修复 | 严重度 | 改动量 | 收益 |
|---|-----|-------|-------|-----|
| A | Bug 1：`function_calling` → `json_schema`（`_orchestrator_llm`） | 🔴 高 | 1 行 | case 4 从 0% → 100%，case 3 从 50% → 100% |
| B | Bug 2：`decision is None` / LLM 声称 complex 但 tasks 空 → 主动走启发式 + 日志 | 🔴 高 | ~15 行 + 1 个单测 | 通道换/模型换/prompt 太长时的长期防御 |
| C | Bug 3：启发式 pattern 补 "第 X 个/此外/同时" 等连接词，追问代词用前瞻切分 | 🟡 中 | ~5 行 + 1-2 个单测 | 启发式路径质量提升，B 触发时能救更多 case |

**强烈建议一次性把 A + B + C 都做了**。三个不冲突，B 依赖 C 是错觉——B 修好之后即使 C 没修，case 4 也会因为启发式只出 2 task → 结果还是 simple，用户仍然看不到 orchestrator 效果；C 修好之后 case 4 才能真正走完整个 orchestrator 流程。

## 4. 建议顺带做的两件事（Nice to have）

1. **Planner 层一次重试**：即使换成 `json_schema`，case 3 观察到偶发 50% 波动（3 次里有 1 次空）。可以在 `_analyze_request` 里对 `decision is None` 的场景**先重试一次**再走启发式：

    ```python
    if decision is None:
        try:
            decision = await self._orchestrator_llm.ainvoke(messages, config={"tags": ["ai_internal"]})
        except Exception:
            pass
    if decision is None:
        return self._fallback_orchestrator_decision(question, "结构化拆解返回空(重试后)")
    ```

    重试成本几乎为 0（planner 用 flash-tier prompt，一次几百 token），但能进一步压 tail failure。

2. **补单元测试覆盖真实通道漏洞**：现在 `test_assistant_graph.py` 全部用 `_patch_complex_orchestrator` 硬塞 fake tasks，绕过了 LLM，所以 Bug 1、2 在 CI 里永远发现不了。至少加：
   - `test_analyze_request_falls_back_when_llm_returns_none`（patch `_orchestrator_llm.ainvoke` 返回 None）
   - `test_analyze_request_falls_back_when_llm_returns_empty_complex`（patch 返回 mode=complex, tasks=[]）
   - `test_heuristic_splits_second_item_reference`（`_heuristic_split_tasks("推荐三款面霜，比较这些哪个更便宜，第二个含什么成分")` 期望 3 个 task）

## 5. 验证方式（改完后如何回归）

改完后按以下顺序跑：

1. **单测**（快，先跑）：
   ```
   d:\dev\env\conda_envs\wlagt\python.exe -m pytest ai-service/tests/test_assistant_graph.py ai-service/tests/test_api_contract.py ai-service/tests/test_assistant_stream_filtering.py -v
   ```

2. **真实 LLM 端到端拆解**（慢，需要 API 调用）：重跑本次用的脚本 `ai-service/scripts/test_orchestrator_planner.py`，或者直接手工调 8 个 case，期望达成 **8/8 通过**（其中 case 3、4 稳定拆出 3 个 task）。

3. **注意**：本报告作者会在修复完成后删掉 `scripts/test_orchestrator_planner.py`（一次性调查脚本），如果 gpt5.5 想保留它作为回归工具，请在实现修复的同一 PR 里说明。

## 6. 不改动的范围（不要越界）

以下代码本次问题**不涉及**，请勿修改：

- `ORCHESTRATOR_PROMPT` 内容本身（case 1/2/5/6/7/8 的表现证明 prompt 语义 OK）
- `OrchestratorTask` / `OrchestratorDecision` schema
- 主图拓扑（`analyze_request → prepare_subtask → route_intent → worker → collect_subtask → ...`）
- `_synthesize_final` / `_build_orchestrator_answer` / `_dedupe_product_cards` / `_dedupe_sources`
- SSE 事件类型和顺序
- `_router_llm`（除非顺便一起换 method，但**非本次必修**）

## 7. 修复完提交建议

commit message 参考已有 style（详细中文，多段）：

```
fix(ai-service/orchestrator): 修复复合问题拆解静默失效

## 背景
qwen-plus + method="function_calling" 在部分跨意图复合问题上偶发/稳定返回空 tool_call，
_orchestrator_llm.ainvoke 拿到 None，被 _normalize_orchestrator_decision 静默降级为 simple，
启发式兜底不触发，日志无 warning。用户看到的表现是"多问题请求被当成单问题回答"。

实测 8 个 DeepSeek 测试用例：
- case 3（跨意图 3 步）：50% 空返回
- case 4（依赖 + 追问）：100% 空返回

## 修复
1. _orchestrator_llm method 由 function_calling 改为 json_schema（case 3/4 → 100% 成功）
2. _analyze_request 检测 decision is None / mode=complex 但 tasks 空时，主动走 _fallback_orchestrator_decision 并打 warning
3. _HEURISTIC_SPLIT_PATTERN 补充"第 X 个/此外/同时"等连接词，追问代词用前瞻断言切分

新增单元测试覆盖：LLM 空响应兜底路径、启发式追问代词切分。

## 已知遗留
_router_llm 仍用 function_calling（IntentDecision schema 简单，未观察到失败）。
如需一并升级为 json_schema，可另开 PR。
```
