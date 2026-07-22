# Orchestrator 测试数据与测试结果

## 背景

本次功能增强名为 `Orchestrator`，目标是让 ai-service 识别并处理多问题、多意图、带依赖的复合请求。

核心链路：

```text
analyze_request
  -> simple: route_intent -> worker -> format_response
  -> complex: prepare_subtask -> route_intent -> worker -> collect_subtask
      -> has_more ? prepare_subtask : synthesize_final -> format_response
```

## 本地自动化测试结果（2026-07-13 更新，全部通过）

在 `d:\dev\env\conda_envs\wlagt` 环境跑通：

| 测试项 | 命令 | 结果 |
| --- | --- | --- |
| AssistantGraph 单元测试 | `python -m pytest ai-service/tests/test_assistant_graph.py -v` | ✅ 13/13 |
| API 契约测试 | `python -m pytest ai-service/tests/test_api_contract.py -v` | ✅ 15/15 |
| 流式过滤测试 | `python -m pytest ai-service/tests/test_assistant_stream_filtering.py -v` | ✅ 4/4 |
| 真实 LLM 拆解（qwen-plus） | `python ai-service/scripts/test_orchestrator_planner.py` | ✅ 8/8（连跑 3 轮共 24 次调用 0 失败） |

已新增/调整的测试：

- `test_orchestrator_executes_complex_tasks_in_order` — 3 任务顺序 + 依赖 + 聚合
- `test_orchestrator_prepare_subtask_stream_heading` — SSE 分段标题事件
- `test_orchestrator_metadata_preserved` — API 契约保留 orchestrator 字段
- `test_analyze_request_falls_back_when_llm_returns_none` — LLM 空响应 → 启发式兜底（Bug 2 回归）
- `test_analyze_request_falls_back_when_llm_returns_empty_complex` — LLM 声称 complex 但 tasks 空 → 启发式补救（Bug 2 回归）
- `test_heuristic_splits_second_item_reference` — 启发式识别"第 X 个"追问代词（Bug 3 回归）
- 原有 AssistantGraph 路由测试已显式固定为 `orchestrator_mode=simple`，验证旧链路不受影响。

## DeepSeek V4 Pro 建议测试数据

### 1. 单意图简单推荐

输入：

```text
给我推荐一款适合油皮的防晒
```

预期：

- `orchestrator_mode=simple`
- `task_type=shopping`
- 不生成 `sub_questions`
- 返回商品推荐话术与 `product_cards`

### 2. 单意图多细节，不应拆解

输入：

```text
烟酰胺是什么、怎么用、有什么注意事项？
```

预期：

- `orchestrator_mode=simple`
- `task_type=knowledge`
- 由 KnowledgeAgent 一次性分点回答
- 不应拆成 3 个子任务

### 3. 跨意图复合问题

输入：

```text
给我推荐适合油皮的防晒，然后我还想知道烟酰胺是什么成分，还有你推荐的这些价格对比如何？
```

预期拆解：

```json
[
  {"id": "t1", "question": "给我推荐适合油皮的防晒", "intent_hint": "shopping", "depends_on": []},
  {"id": "t2", "question": "烟酰胺是什么成分？", "intent_hint": "knowledge", "depends_on": []},
  {"id": "t3", "question": "你推荐的这些商品价格对比如何？", "intent_hint": "shopping", "depends_on": ["t1"]}
]
```

预期：

- `orchestrator_mode=complex`
- 最终 `task_type=orchestrator`
- `sub_results` 长度为 3
- 第 1、3 个子任务走 shopping，第 2 个走 knowledge
- 最终答案按 1/2/3 分段
- `product_cards` 聚合推荐商品，重复商品去重
- `sources` 聚合知识来源

### 4. 依赖型商品追问

输入：

```text
推荐三款补水面霜，然后比较这些哪个更便宜，第二个含什么成分？
```

预期：

- `orchestrator_mode=complex`
- 子任务 2、3 均依赖推荐结果
- “比较这些哪个更便宜”走 shopping compare/detail 能力
- “第二个含什么成分”如果指向具体商品，应走 shopping 的 `answer_product_detail`

### 5. 多个独立知识问题

输入：

```text
烟酰胺和VC能一起用吗？视黄醇晚上怎么用？
```

预期：

- 可以为 `complex`，拆成两个 knowledge 子任务
- 两个子任务无依赖
- 最终答案按两个部分输出

### 6. 闲聊或元问题

输入：

```text
你还记得我刚才问了什么吗？
```

预期：

- `orchestrator_mode=simple`
- `task_type=chitchat`
- 不拆解

### 7. 用户补充澄清信息

前置：上一轮 Agent 追问“你的肤质和预算是？”

输入：

```text
油皮，预算 200 以内
```

预期：

- `orchestrator_mode=simple`
- 作为上一轮 pending shopping need 的补充，不拆解
- 走 shopping 推荐链路

### 8. 明显但 planner 失败时的启发式兜底

输入：

```text
推荐一款防晒，然后说说烟酰胺的功效，还有这些商品哪个便宜
```

预期：

- 如果结构化 planner 调用失败，启发式兜底应拆出至少 2 个任务
- 含“这些商品哪个便宜”的任务应依赖 `t1`

## DeepSeek 测试时重点观察

1. 是否过度拆解同一意图问题。
2. 是否漏拆跨意图问题。
3. `depends_on` 是否能覆盖“这些/它们/第二个/刚才推荐的”。
4. 复杂问题最终答案是否完整覆盖全部子问题。
5. `product_cards` 和 `sources` 是否在最终响应里保留。
6. 流式模式下是否先输出分段标题，再依次输出各子任务答案。
