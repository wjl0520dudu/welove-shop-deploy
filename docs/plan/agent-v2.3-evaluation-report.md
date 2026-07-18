# Agent 架构优化 V2.3 评测报告

> 生成时间：2026-07-18
> 数据集：agent_golden_cases.jsonl（142 条）
> 模型：qwen-plus
> 配置：MILVUS_COLLECTION=knowledge_parent_child_v1, RAG_PARENT_CHILD_ENABLED=true
> 基线：V2.2（agent-v2.2-deepeval.local.json）
> 报告文件：evals/reports/agent-v2.3-full.json

---

## 一、全局指标 vs V2.2

| 指标 | V2.2 | V2.3 | 变化 | 说明 |
|---|---|---|---|---|
| Contract Pass Rate | 73.24% | 67.61% | **-5.6%** | 退化 |
| Task Success Rate | 47.18% | 40.85% | **-6.3%** | 退化 |
| P50 延迟 | 11897ms | 7696ms | **-35%** | 改善 |
| P95 延迟 | 24098ms | 17810ms | **-26%** | 改善 |
| TC (Task Completion) | 0.7606 | 0.6243 | **-0.136** | 退化 |
| TR (Tool Correctness) | 0.6972 | 0.6514 | **-0.046** | 轻微退化 |
| RAGAS Faithfulness | 0.6672 | 0.5804 | **-0.087** | 退化 |
| RAGAS Context Precision | 0.4040 | 0.3304 | **-0.074** | 退化 |
| RAGAS Context Recall | 0.5561 | 0.6522 | **+0.096** | 改善 |
| RAGAS Answer Relevancy | 0.8107 | 0.7411 | **-0.070** | 退化 |

---

## 二、场景分解

| 场景 | V2.2 TC | V2.3 TC | V2.2 TR | V2.3 TR | V2.2 Contract | V2.3 Contract | 判断 |
|---|---|---|---|---|---|---|---|
| shopping | 0.7141 | 0.3761 | 0.4348 | 0.4022 | 65.22% | 50.00% | 🔴 严重退化 |
| knowledge | 0.9163 | 0.9219 | 0.8438 | 0.8125 | 90.62% | 96.88% | 🟢 稳定 |
| chitchat | 0.5859 | 0.6484 | 0.9688 | 0.9062 | 78.12% | 81.25% | 🟢 改善 |
| multi_agent | 0.6683 | 0.4625 | 0.4167 | 0.3333 | 58.33% | 41.67% | 🔴 退化 |
| multimodal_shopping | 0.7250 | 0.7150 | 0.8000 | 0.7500 | 65.00% | 55.00% | 🟡 轻微退化 |

---

## 三、根因分析（按严重程度排序）

### Bug 1：商品检索召回率减半（最严重）

**现象**：shopping 场景无商品卡片的 case 从 15/46 翻倍到 31/46。

**根因**：`ai-service/shopping/retrieval.py` 的 `build_retrieval_plan()` 函数（约第 383-414 行）。V2.2 在候选不足时通过 `relaxed_filters` 自动放宽预算（1.2 倍）和仅按类目重试：

```python
# V2.2 逻辑（被删除）
relaxed: List[Dict[str, Any]] = []
if need.budget_max is not None:
    relaxed.append({**filters, "budget_max": need.budget_max * 1.2})
if need.category:
    relaxed.append({"category": need.category})
```

V2.3 将 `relaxed_filters` 改为空列表 `[]`，导致候选不足时没有任何兜底召回：

```python
# V2.3 当前代码（有问题）
relaxed: List[Dict[str, Any]] = []  # 永远为空，不再触发 relaxed recall
```

**影响范围**：数码（手机/笔记本/耳机）、食品（咖啡/气泡水/方便面）、运动鞋等品类几乎全部召回失败。这些品类本身商品量少，不放宽过滤就无结果。

**修复方向**：恢复 `relaxed_filters`，但区分 hard/soft 字段。只放宽 soft 字段（预算、类目），不放宽 hard 字段（用户明确说的"200 元以内"不能放宽）。

---

### Bug 2：答案质量下降（Dispatcher 路径）

**现象**：Dispatcher 正确选择了工具（`dispatch_source: rule` 的 24 个 case 工具都对），但 TC 平均只有 0.39。

**根因**：`ai-service/shopping/agent.py` 的 `_compose_capability_answer()` 函数（约第 316-341 行），用模板拼装答案：

```python
def _compose_capability_answer(capability: str, payload: Dict[str, Any]) -> str:
    if capability == "recommend":
        cards = payload.get("product_cards") or []
        lines = ["为你找到以下商品："]
        for card in cards[:3]:
            lines.append(f"- {card.get('title', '商品')}（{price} 元）：{reason}")
        return "\n".join(lines)
```

这个模板生成的答案非常生硬，缺少商品描述、推荐理由和自然语言过渡。V2.2 的 `create_agent` 路径由 LLM 自由生成自然语言答案，质量高得多。

**修复方向**：`_compose_capability_answer` 不改用模板，改为调用 LLM（基于 Capability 返回的 product_cards/facts）生成自然语言回答。或者直接复用 `create_agent` 只做表达层（禁止工具选择）。

---

### Bug 3：Multimodal 图片搜索退化

**现象**：`img-001`、`img-002`、`img-004` 的 `tool_calls` 为空，V2.2 有 `search_multimodal_v1`。

**根因**：`ai-service/assistant/nodes.py` 的 `_multimodal_shopping` 函数（约第 81-130 行）。新增的 `extract_explicit_product_filters` 和 `enforce_explicit_product_filters` 可能在某些路径下导致空结果。

**排查方向**：检查 `img-001`（"找和图片同款的衣服"）的 `hard_filters` 是否太严格，导致 `search_multimodal_v1` 返回空。

---

### Bug 4：路由错误

**现象**：shop-019（"小棕瓶的成分是什么"）、shop-034（"敏感肌用什么护肤品"）、shop-037（"有没有健身推荐"）被路由到 knowledge 而非 shopping。

**根因**：顶层 Router 将成分查询归为 knowledge，但 golden dataset 期望这些走 shopping。Dispatcher 的规则匹配未能覆盖这些边界 case。

**修复方向**：在 Dispatcher 规则中增加"成分查询且商品名已知"→ `detail` 的规则。

---

### Bug 5：DeepEval TR=0.0 误判

**现象**：`expected_tools: []` 的 case 全部 TR=0.0（如 shop-020、shop-023 等）。

**根因**：`ai-service/evals/agent_judges.py` 的 `evaluate_with_deepeval()` 函数（约第 50-52 行），当 `expected_tools` 为空时，`ToolCorrectnessMetric` 把调用了工具当作"多余工具"，扣分到 0。

**修复方向**：在 `evaluate_with_deepeval` 中，当 `expected_tools` 为空时跳过 `ToolCorrectnessMetric`，或设置 `expected_tools` 为 `actual_tools`。

---

## 四、修复优先级

| 优先级 | Bug | 文件 | 预计影响 |
|---|---|---|---|
| **P0** | Bug 1：检索召回 | `shopping/retrieval.py` `build_retrieval_plan()` | 恢复 ~16 个 case 的卡片 |
| **P0** | Bug 2：答案质量 | `shopping/agent.py` `_compose_capability_answer()` | 提升 TC 0.39→0.60+ |
| **P1** | Bug 3：Multimodal 退化 | `assistant/nodes.py` `_multimodal_shopping()` | 恢复 3 个 case |
| **P1** | Bug 4：路由错误 | `shopping/dispatcher.py` `dispatch_shopping_capability()` | 修复 ~4 个 case |
| **P2** | Bug 5：TR 误判 | `evals/agent_judges.py` `evaluate_with_deepeval()` | 修正 ~20 个 case 的 TR 分数 |

---

## 五、当前代码位置

所有改动文件（共 13 个修改 + 3 个新增）：

```
ai-service/
  shopping/
    dispatcher.py          # 新增：Hybrid Dispatcher
    agent.py               # 修改：集成 Dispatcher + _compose_capability_answer
    schemas.py             # 修改：新增 ProductFilterPlan
    retrieval.py           # 修改：build_retrieval_plan + _enforce_hard_filters
    multimodal_search.py   # 修改：extract/confirm_explicit_product_filters
  assistant/
    graph.py               # 修改：DAG evidence/execution_contract
    nodes.py               # 修改：multimodal 传入 hard_filters
    orchestration.py       # 修改：TaskEvidence + TaskExecutionResult
  rag/
    query_planner.py       # 新增：KnowledgeQueryPlan + 词典标准化
    parent_child.py        # 新增：父子分块构建/聚合/窗口
    retriever.py           # 修改：父子分块检索链路
    vector_store.py        # 修改：Milvus parent_id/child_index 字段
    document_pipeline.py   # 修改：父子分块入库（feature flag）
    models.py              # 修改：ChunkMetadata 新增字段
  knowledge/
    agent.py               # 修改：集成 query_planner
  core/
    config.py              # 修改：RAG_PARENT_CHILD_ENABLED 配置项
```

---

## 六、评测数据

完整原始数据在 `ai-service/evals/reports/agent-v2.3-full.json`（2.1MB），V2.2 基线在 `ai-service/evals/reports/agent-v2.2-deepeval.local.json`（1.7MB）。

每条 case 包含：`contract`（Contract Test 详细检查）、`judge`（DeepEval TC/TR 分数和理由）、`ragas`（RAGAS 分数）、`response`（完整 graph 输出）。