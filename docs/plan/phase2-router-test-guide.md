# Phase 2 低成本路由可靠性测试指南

## 1. 测试目标

本指南用于验证“高确定性规则 → Structured LLM Router → 低置信度澄清兜底”的完整链路。

重点确认：

1. 明确的 Shopping、Knowledge、Chitchat 和图片请求不调用 Router LLM；
2. 混合、指代或规则无法判断的表达只调用一次 Structured Router；
3. LLM 置信度低于阈值时不进入错误 Agent，而是返回 `unknown` 和澄清问题；
4. DAG 子任务优先复用 `intent_hint`，明显冲突时允许高确定性规则覆盖；
5. 普通响应、SSE route 事件和 DAG `sub_results` 均包含完整路由轨迹；
6. 离线评测能够输出 Route Accuracy、误路由率、低置信度率和规则直达率。

## 2. 本次新增配置

```env
ROUTER_RULE_MIN_CONFIDENCE=0.90
ROUTER_LOW_CONFIDENCE_THRESHOLD=0.65
ROUTER_ORCHESTRATOR_HINT_CONFIDENCE=0.90
```

- `ROUTER_RULE_MIN_CONFIDENCE`：规则达到该阈值时直接路由；
- `ROUTER_LOW_CONFIDENCE_THRESHOLD`：LLM 低于该阈值时进入安全兜底；
- `ROUTER_ORCHESTRATOR_HINT_CONFIDENCE`：复用 DAG 子任务 `intent_hint` 时记录的置信度。

## 3. 自动化测试

在 `ai-service` 目录执行：

```powershell
python -m pytest tests/test_router_reliability.py -q
python -m pytest tests/test_assistant_graph.py -q
python -m pytest tests/test_api_contract.py -q
```

如需检查整个 AI Service 回归：

```powershell
python -m pytest -q
```

如果本地缺少 PostgreSQL、Redis、Milvus、DashScope 或 Java 服务，应记录具体跳过/失败项，不要把外部依赖失败误判为路由逻辑失败。

## 4. 规则离线评测

规则模式不调用 LLM，也不执行业务 Agent：

```powershell
python -m evals.run_router_eval --mode rules
```

它用于检查：

- 哪些 Case 能被高确定性规则直接覆盖；
- 规则本身是否出现静默误路由；
- 哪些 Case 被保守地交给 LLM/澄清兜底。

注意：规则模式的 `route_accuracy` 不是混合路由最终准确率。规则未命中的 Case 会记为 `unknown`，其价值是衡量规则覆盖率和规则精度。

## 5. 混合路由离线评测

配置可用 LLM 后执行：

```powershell
python -m evals.run_router_eval --mode hybrid --output evals/reports/router-hybrid.json
```

该命令只调用路由，不执行 Shopping/Knowledge/Chitchat Agent，因此成本远低于完整 E2E 评测。高确定性规则 Case 不产生 LLM 调用，只有未命中规则的 Case 才调用模型。

报告包括：

```json
{
  "route_accuracy": 0.0,
  "misroute_rate": 0.0,
  "low_confidence_rate": 0.0,
  "rule_direct_rate": 0.0
}
```

不要在未实际运行时填写或引用任何指标数值。

### 指标定义

- `Route Accuracy`：最终 route 等于 expected route 的 Case 比例；
- `Misroute Rate`：进入了错误业务 Agent，且没有触发安全兜底的 Case 比例；
- `Low-confidence Rate`：最终进入 `unknown` 或触发 fallback 的 Case 比例；
- `Rule Direct Rate`：由规则直接完成路由、无需 Router LLM 的 Case 比例。

`Low-confidence Rate` 并不是越低越好。对于确实含糊的问题，澄清比静默误路由更安全，因此应结合 `Misroute Rate` 和失败样本一起看。

## 6. API 契约检查

普通 `/api/assistant/run` 响应应包含：

```json
{
  "route": "shopping",
  "route_reason": "...",
  "route_confidence": 0.94,
  "route_source": "rule",
  "rule_route": "shopping",
  "rule_confidence": 0.94,
  "rule_reason": "...",
  "llm_route": null,
  "llm_confidence": null,
  "llm_reason": "",
  "route_fallback_used": false
}
```

`route_source` 可能值：

- `rule`：高确定性规则直接路由；
- `rule_override`：规则覆盖明显冲突的 Orchestrator hint；
- `orchestrator_hint`：DAG 子任务复用结构化计划的 hint；
- `llm`：规则未命中，由 Structured Router 决策；
- `fallback`：空问题、模型失败、返回空结果或低置信度澄清。

SSE `route` 事件应包含同类诊断字段：

```text
event: route
data: {"task_type":"shopping","confidence":0.94,"source":"rule",...}
```

## 7. 必测人工 Case

| 输入 | 期望 route | 期望 source | 说明 |
|---|---|---|---|
| `推荐一款防晒` | shopping | rule | 规则直达 |
| `烟酰胺有什么功效` | knowledge | rule | 规则直达 |
| `你好` | chitchat | rule | 独立问候 |
| 上传图片 + `找同款` | shopping | rule | 多模态直达 |
| `我想买防晒，但不知道怎么选` | 取决于 LLM 语义判断 | llm/fallback | 混合信号，不应由规则强判 |
| `帮我看看这个`，无上下文 | unknown | fallback | 低置信度时澄清 |
| DAG hint=shopping，子问题=`烟酰胺有什么功效` | knowledge | rule_override | 明显冲突纠正 |

## 8. 验收建议

建议以当前 Golden Dataset 为 V1，后续按真实误判样本增量扩充，不要只增加容易命中的关键词 Case。

最低验收要求：

1. 自动化测试全部通过；
2. 明确规则 Case 不调用 Structured Router；
3. 混合 Case 的 LLM 调用次数为一次；
4. 低置信度 Case 不进入 Shopping/Knowledge Agent；
5. API 与 SSE 可以区分 rule、LLM 和 fallback；
6. 混合评测报告无静默高风险误路由，所有失败 Case 可从轨迹字段定位原因。
