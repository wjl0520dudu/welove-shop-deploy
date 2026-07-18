# Agent V2.4 最小回归修复与测试指引

> 目标：以 V2.2 为质量基线，修复 V2.3 的真实回退；不新增复杂 Agent 架构，不牺牲用户明确的预算、品牌、在售状态约束。

## 1. V2.4 修复范围

### 1.1 文本商品检索：类目别名标准化

V2.3 将 LLM 解析出的自然语言类目直接用于 Milvus 精确过滤和最终硬过滤，造成语义可召回、最终却被删除的问题。

V2.4 新增 `ai-service/shopping/category_resolver.py`，用小型、可审计的 catalog 别名表将常见表达转换为数据库 `sub_category`：

| 用户表达 | 标准类目 |
|---|---|
| 抗初老精华 / 抗老精华 | 精华 |
| 防晒霜 / 防晒乳 | 防晒 |
| 方便面 | 方便食品 |
| 跑鞋 / 运动鞋 / 碳板跑鞋 | 跑步鞋 |
| 黑咖啡 | 咖啡 |
| 真无线耳机 | 真无线耳机 |

`护肤品`、`提神饮品` 等宽泛或主观表达无法安全映射时，不再写进精确 filter，只保留为语义检索 query。

显式预算、品牌和商品状态仍为硬约束。V2.4 恢复召回不足时的 fallback，但只移除类目 filter，让原始 query 做语义补召回；不会恢复 V2.2 的“预算 × 1.2”放宽逻辑。补召回结果在返回卡片前仍会校验预算、品牌和在售状态。

### 1.2 图文商品检索：复用相同标准化

`multimodal_search.py` 不再维护一套原始词匹配 filter，而是复用 `normalize_product_category`。这样 `方便面` 不会再错误过滤为数据库不存在的类目值，避免 dense/BM25/image 三路召回同时归零。

### 1.3 复杂请求：补齐低成本短路保护

在跳过 Orchestrator 前，新增以下多目标识别：

- `各一款`；
- `一款 A、一款 B`；
- `一款 A 和一款 B`。

命中后会进入已有 Orchestrator/DAG，不修改 DAG 的执行模型。

### 1.4 路由修复：商品属性查询不再误入知识库

V2.3 将 `成分`、`功效`、`作用`、`原理`、`用法`、`浓度` 归入 `_KNOWLEDGE_PATTERNS`，导致 "小棕瓶的成分是什么" 等查询被顶层 Router 路由到 Knowledge，实际应走 Shopping Detail。

V2.4 双层修复：

1. **Router**（`assistant/router.py`）：新增 `_PRODUCT_ATTRIBUTE_QUERY` 正则匹配 `{商品名}的{属性词}` 模式。命中时在 `knowledge_hits` 检测之前返回 `route=shopping`，避免知识路由抢断。
2. **Dispatcher**（`shopping/dispatcher.py`）：`_DETAIL_RE` 的条件从 `(cards or focused)` 扩展为 `(cards or focused or _PRODUCT_ATTR_IN_QUERY.search(text))`，使得首轮对话（无商品记忆）也能将此类查询分派到 `detail` Capability。

修复前 Router 和 Dispatcher 都无法正确处理，导致 shop-019（"小棕瓶的成分是什么"）被路由到 knowledge、shop-034（"敏感肌用什么护肤品"）、shop-037（"有没有健身推荐"）等边界 case 也受影响。

### 1.5 Dispatcher：保留确定性能力选择，恢复表达质量

Dispatcher 仍直接执行已确定的 Capability，避免再让模型选择工具；但在 Capability 已经返回 cards/facts 后，增加一次无工具、仅基于结构化事实的 LLM 表达调用。

该表达层：

- 不允许调用工具；
- 不允许编造商品、价格、库存、成分或功效；
- 失败时回退到原有确定性模板；
- 对空结果、澄清与异常不增加 LLM 调用。

### 1.6 评测修正

- golden 未声明 `required_tools`：跳过 DeepEval ToolCorrectness，避免把正常工具调用判成额外调用；
- 历史 `search_products` 与当前高层 `recommend_products` 视为同一“商品发现”能力，Contract 与 DeepEval 都兼容。

安全拒绝、RAGAS 基线可比性不在本次代码修复范围内；V2.4 全量报告中应将它们与普通 Task Completion 分开解读。

## 2. 重点回归样本

### 2.1 Shopping：必须恢复商品卡片

```powershell
python -m evals.run_agent_eval --direct --case-id shop-004 --case-id shop-005 --case-id shop-006 --case-id shop-013 --case-id shop-015 --case-id shop-036 --case-id shop-044
```

预期：每个 case 都有非空 `product_cards`；显式预算 case 不出现超预算商品。

### 2.5 路由修复：属性查询正确走 Shopping/Detail

```powershell
python -m evals.run_agent_eval --direct --case-id shop-019 --case-id shop-034 --case-id shop-037
```

预期：

- `route=shopping`（不再是 `knowledge`）；
- `tool_calls` 包含 `answer_product_detail` 或 `recommend_products`；
- `product_cards` 非空；

### 2.2 Multimodal：验证标准类目 filter

```powershell
python -m evals.run_agent_eval --direct --case-id img-001 --case-id img-002 --case-id img-004 --case-id img-013
```

预期：

- `tool_calls` 包含 `search_multimodal_v1`；
- `product_cards` 非空；
- `img-001` 为方便食品，`img-002` 为跑步鞋，`img-004` 为真无线耳机；
- `img-013` 返回运动 T 恤，不被图片中的跑鞋类目错误限制。

若没有召回到商品，`tool_calls` 仍必须记录 `search_multimodal_v1` 且 `status=completed_empty`。这表示检索已执行、但候选在召回或后续过滤阶段归零，不能误判为“工具未调用”。

工具参数中的 `retrieval_counts` 会记录 `after_recall`、`after_judge`、`after_personalization`、`after_hard_filters`。测试报告应据此判断问题发生在召回、Judge 还是约束过滤，不要仅凭空卡片推断。

### 2.3 DAG：验证多目标不再短路

```powershell
python -m evals.run_agent_eval --direct --case-id dag-008 --case-id dag-010 --case-id dag-011 --case-id dag-012
```

预期：

- `route=orchestrator`；
- `orchestrator_mode=complex`；
- `sub_results` 数量与子任务数一致；
- 无依赖任务可并行执行。

### 2.4 评测工具口径

```powershell
python -m evals.run_agent_eval --direct --deepeval --case-id shop-024 --case-id shop-031 --case-id rag-012
```

预期：未配置 `required_tools` 的 case，`judge.metrics.tool_correctness` 为：

```json
{
  "score": null,
  "passed": true,
  "reason": "skipped: required_tools is not specified for this case"
}
```

## 3. 全量验收

由测试 Agent 在环境服务正常时执行：

```powershell
python -m evals.run_agent_eval --direct --deepeval --ragas --baseline evals/reports/agent-v2.2-deepeval.local.json --output evals/reports/agent-v2.4-full.local.json --markdown-output evals/reports/agent-v2.4-full.local.md
```

注意：V2.2 是 `recorded`，V2.4 是 `direct`，全局延迟和 LLM Judge 分数仅作方向性参考。若需要严谨的 RAGAS 回归，需以相同 Knowledge case 子集分别运行旧/新 collection。

V2.4 最低验收线：

| 指标 | V2.3 | V2.4 最低目标 |
|---|---:|---:|
| Shopping Contract Pass | 50.00% | > 65.22%（V2.2） |
| Multi-Agent Contract Pass | 41.67% | > 58.33%（V2.2） |
| Multimodal Contract Pass | 55.00% | > 65.00%（V2.2） |
| Recall@5 | 0.4628 | > 0.6250（V2.2） |
| MRR@5 | 0.4505 | > 0.6322（V2.2） |
| NDCG@5 | 0.4304 | > 0.5930（V2.2） |
| P95 latency | 17.81s | <= 24.10s（V2.2） |
| 显式预算/品牌约束违反 | 未单列 | 0 |

若某一项未达标，测试 Agent 应从报告中摘出失败 case 的 `input`、`route`、`tool_calls`、`product_cards` 和 Contract failure reasons；不要只报告一个总分。
