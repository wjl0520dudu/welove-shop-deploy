# Agent 优化集中测试交接清单

> 用途：本轮 Agent 架构优化完成后的集中测试说明。执行者应在已启动 PostgreSQL、Milvus、相关 Java 服务与可用 LLM/Embedding 配置的环境中运行。

## 1. 变更范围

- Shopping Hybrid Capability Dispatcher；
- 交易动作 MVP 明确拒绝/引导；
- 商品严格过滤及图文检索预算过滤；
- Knowledge Query Planner（词典标准化、文档类型过滤）；
- 父子分块构建、子块 Rerank 后回填父块；
- DAG 任务执行证据契约。

## 2. 必跑静态检查

在 `ai-service` 下执行：

```powershell
python -m compileall shopping assistant rag knowledge core -q
python -m pytest tests/test_recommend_capability.py tests/test_shopping_high_level_tools.py tests/test_assistant_graph.py -q
```

## 3. Shopping Dispatcher 用例

验证响应中的 `tool_calls[0].tool_name`、`capability`（如存在）与商品卡片：

| 输入 | 期望 capability/tool | 关键断言 |
|---|---|---|
| 推荐一双 200 元以内的鞋 | `recommend` / `recommend_products` | 所有卡片 `price <= 200`，`status=1` |
| 比较刚才前两款 | `compare` / `compare_products` | 无法定位两件商品时只澄清，不改走推荐 |
| 第二款多少钱 | `detail` / `answer_product_detail` | 使用会话商品卡片定位商品 |
| 根据我的偏好推荐 | `user_context` 或 `recommend` | 不出现无关工具调用 |
| 帮我加入购物车 | `transaction_unsupported` | 不调用 Java 写接口，不声称“已加购” |

同时运行现有：

```powershell
python scripts/verify_shopping_e2e.py
python scripts/verify_shopping_focus_and_compare.py
```

## 4. 商品与多模态硬约束

| 输入 | 期望 |
|---|---|
| 推荐 200 元以内的鞋，候选不足 | 返回少于 3 个也可以；绝不能出现价格 > 200 的卡片 |
| 上传鞋图：找同款，200 元以内 | `search_multimodal_v1` trace 内含 `hard_filters.budget_max=200`；最终卡片价格均不超预算 |
| 上传方便面图片 | Judge 后仅保留结构化类目/商品事实合理的候选；不为凑 top_k 补异类商品 |

## 5. Knowledge Query Planner

| 输入 | 期望 |
|---|---|
| A 醇怎么用 | `query_plan.rewritten_query` 标准化为“视黄醇” |
| 退换货说明 | `query_plan.hard_filters.doc_types` 含 `policy` |
| 敏感肌使用 VC | 肤质属于 soft term，不应因为不存在精确 metadata 而零召回 |

检查 `search_knowledge` 的 ToolMessage，确认返回 `query_plan`，并验证其从未输出原始 Milvus expr。

## 6. 父子分块迁移与评测

默认 `RAG_PARENT_CHILD_ENABLED=false`，旧索引必须保持可用。开启前的前置条件：

1. 使用包含 `parent_id`、`child_index` 的新 Milvus collection；不要在旧 collection 原地切换；
2. 全量重新入库，确保同一文档同时有 `chunk_type=parent` 与 `chunk_type=child`；
3. 抽查 child 均有 `parent_id`，并能按该 ID 查询 parent；
4. 设置 `RAG_PARENT_CHILD_ENABLED=true` 后再重启 AI 服务。

开启后验证：

```text
child hybrid recall → child rerank → parent 聚合 → parent local window
```

运行 RAG 评测并与 `docs/phase-test-results.local.md` 的基线比较：Recall@5、MRR@5、NDCG@5、Context Precision、Context Recall、Faithfulness、P95。

## 7. DAG 回归

使用至少三类复杂请求：并行的商品+知识问题、依赖“推荐后对比”的问题、图片+知识混合问题。

- 同层无依赖任务并发；
- 依赖任务仅消费上游 cards/sources/evidence；
- 上游失败后下游为 `blocked`；
- `sub_results[*].execution_contract` 存在，且包含 `status/evidence/product_cards/sources`；
- 聚合卡片去重且仍满足硬约束。

## 8. 通过标准

仅在同一 golden 数据集、同一模型和同一外部服务环境下比较。重点目标：

- Shopping Tool Correctness >= 0.70；
- Shopping Task Success >= 0.55；
- Multi-Agent Tool Correctness >= 0.65；
- Context Precision >= 0.60，且 Recall@5 不低于 0.84；
- Knowledge P95 不较基线恶化超过 15%。

若任何严格预算/类目 case 输出不符合事实的商品卡片，视为阻塞问题；若父子索引迁移失败，保持 feature flag 关闭并回报，不得切换线上默认索引。

## 9. 父子分块已导入后的集中测试步骤

### 9.1 测试范围确认

本次新 collection 仅服务 KnowledgeAgent：`MILVUS_COLLECTION=knowledge_parent_child_v1`。不要执行 `ingest_products_to_milvus.py`，不要修改 `product_mm_collection` 或 `product_mm_v2`；它们仍服务 ShoppingAgent 的商品、图片和图文向量检索。

### 9.2 环境与索引检查

确认：

```env
MILVUS_COLLECTION=knowledge_parent_child_v1
RAG_PARENT_CHILD_ENABLED=true
```

对已导入文档抽样检查：

- 同一 `doc_id` 同时存在 `chunk_type=parent` 与 `chunk_type=child`；
- `child.parent_id` 非空，且对应 parent 存在；
- `documents[*]` 为 child 命中，`knowledge_context` 为父块回填上下文；
- `MetadataFilter` 的 `doc_id/category_id/product_id/doc_type/chunk_type` 过滤仍可用；
- 无 `ChunkMetadata`、`parent_id`、`child_index` 未定义或 collection schema 缺字段错误。

### 9.3 必测检索样本

至少覆盖：

| Case | 断言 |
|---|---|
| 敏感肌可以使用兰蔻小黑瓶吗 | child 命中相关 FAQ/说明，父块上下文包含完整注意事项 |
| 敏感肌使用视黄醇注意事项 | Rerank 后 child 相关，`knowledge_context` 具备完整使用建议 |
| 退换货说明 | Query Planner 输出 `doc_types=[policy]`；若库内不存在应明确无答案，不可编造 |
| 上一轮第二个成分怎么用 | 指代消解后 Query 正确，来源可追溯 |
| 与知识库无关问题 | 无低分内容硬答，遵守 fallback/拒答策略 |

### 9.4 评测与结论模板

对旧、新 collection 分别运行相同评测，记录：

```text
检索：Recall@5 / MRR@5 / NDCG@5
RAGAS：Context Precision / Context Recall / Faithfulness / Answer Relevancy
性能：Knowledge P50 / P95 / 错误率
```

结论必须写明 collection 名称、feature flag、模型、数据集版本、样本数和运行时间。若 Context Precision/Faithfulness 提升但 Recall@5、MRR@5 明显下降，不能直接切换，需分析 parent/child 尺寸、overlap 与 Rerank top_n。
