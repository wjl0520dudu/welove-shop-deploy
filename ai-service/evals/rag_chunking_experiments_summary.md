# 商品知识库 RAG 分块实验对比

更新日期：2026-07-25

## 1. 目的与范围

本文记录商品知识库的 RAG 分块与检索方案实验。目标是确定默认方案，并明确每组结果能够支持的结论边界。

本文只比较 `knowledge` 场景；商品检索、路由、DeepEval smoke、合同测试和多模态检索报告不属于分块策略实验，不在本表作为方案候选。

当前 `.env` 的默认知识库配置为：

```env
MILVUS_COLLECTION=my_rag_collection
RAG_PARENT_CHILD_ENABLED=false
CHUNK_SIZE=500
CHUNK_OVERLAP=50
```

## 2. 统一评测条件

除特别标记的历史参考项外，正式评测使用：

| 项目 | 固定值 |
|---|---|
| 数据集 | `evals/datasets/agent_golden_cases.jsonl` |
| 数据集指纹 | `d7c852af8570e81f` |
| 评测范围 | 32 条 `knowledge` case |
| Embedding | `text-embedding-v4` |
| Rerank | `qwen3-rerank` |
| 初始召回 | Top20 |
| 最终上下文 | Top5 |
| 回答模型 / RAGAS LLM | `qwen-plus` |
| 检索流程 | hybrid（dense + BM25）-> rerank |

RAGAS 个别样本会因模型输出长度等原因评分失败。因此：

1. Contract、延迟以完整 32 条输入 case 统计；
2. RAGAS 原始均值必须同时写明样本数；
3. 两个方案的正式 RAGAS 结论以每个指标均成功的 case 交集的配对均值为准；
4. `Recall@5`、`MRR@5`、`NDCG@5` 仅在 16 条有 relevance 标注的 case 上计算。

## 3. 当前可形成正式对比的主实验

### 3.1 对比对象

| 方案 | Collection | 商品知识组织 | 通用知识组织 | 运行条件 |
|---|---|---|---|---|
| v2.1 当前复测 | `my_rag_collection` | 营销描述、单条 FAQ、每 3 条评价按语义组装为块 | 固定分块 `500/50` | Commit `d7e245b`；Prompt `110008402b23beba` |
| recursive_v1 + general | `knowledge_recursive_v1` | 商品语义组装后采用递归 `500/50` | 递归分块 `500/50` | Commit `d7e245b`；Prompt `110008402b23beba` |

两次均使用相同数据集、模型、检索参数、32 条 case、当前提交和提示词，因此可以作为当前的**整体 RAG 方案对比**。

但它不是纯粹的“固定切分器 vs 递归切分器”因果实验：两边的商品/通用知识文档构建和 collection 内容也不同。结论应表述为“这两套完整知识库方案的对比”，不能把全部差异归因于 splitter。

### 3.2 当前报告的原始汇总

| 指标 | v2.1 当前复测 | recursive_v1 + general |
|---|---:|---:|
| Answer Relevancy | 0.7693 (n=26) | 0.7747 (n=28) |
| Context Precision | 0.4405 (n=20) | 0.4428 (n=22) |
| Context Recall | 0.6008 (n=20) | 0.5652 (n=22) |
| Faithfulness | 0.6853 (n=26) | 0.6531 (n=28) |
| Recall@5 | 0.8646 | 0.7708 |
| MRR@5 | 0.9062 | 0.8750 |
| NDCG@5 | 0.8571 | 0.7742 |
| Contract Pass Rate | 75.00% | 93.75% |
| P50 / P95 延迟 | 13.30s / 29.50s | 12.25s / 17.29s |

### 3.3 配对 RAGAS 对比

下表按两个报告中均成功产生对应 RAGAS 指标的相同 case 计算，消除各自有效样本数不同造成的偏差。Delta 为“递归方案 - v2.1”。

| 指标 | 配对 case 数 | v2.1 当前复测 | recursive_v1 + general | Delta | 结果 |
|---|---:|---:|---:|---:|---|
| Answer Relevancy | 26 | 0.7693 | 0.7601 | -0.0092 | v2.1 略好 |
| Context Precision | 20 | 0.4405 | 0.4789 | +0.0385 | 递归版更干净 |
| Context Recall | 20 | 0.6008 | 0.5842 | -0.0167 | v2.1 更完整 |
| Faithfulness | 26 | 0.6853 | 0.6615 | -0.0238 | v2.1 更可靠 |

### 3.4 当前结论

`my_rag_collection` 的 v2.1 策略仍应保留为默认线上方案：检索三项指标和配对后的回答相关性、上下文召回、忠实度均更好。递归版只在 Context Precision 上有明确优势，说明其上下文更精简，但带来了召回和回答依据的损失。

当前 v2.1 的 Contract 与 P95 延迟较差，包含路由、超时及 `rag-029` RAGAS `max_tokens` 错误等运行因素；这些指标不能直接归因于分块策略。

主报告：

- `evals/reports/agent-v2.1-rerun-20260725.json`
- `evals/reports/agent-recursive-v1-with-general.json`

## 4. 已完成的历史实验（参考）

下表保留以前做过的分块实验，方便追溯。标记为“参考”的报告不得与第 3 节直接相减得出因果结论。

| 实验 | 日期 / Collection | 数据与版本 | 原始 RAGAS：AR / CP / CR / F | 检索：R@5 / MRR / NDCG | 证据等级与说明 |
|---|---|---|---|---|---|
| v2.1 历史基线 | 07-17；`my_rag_collection` | 32 knowledge；Commit `8800851`；Prompt `f49c...` | 0.8107 / 0.4040 / 0.5561 / 0.6672 | 0.8646 / 0.8958 / 0.8489 | 参考。文档策略与当前 v2.1 相同，但代码和 prompt 均不同。 |
| recursive_v1 商品 only | 07-22；`knowledge_recursive_v1` | 32 knowledge；Commit `39b486f`；Prompt `110008...`；未导入通用知识 | 0.7921 / 0.3947 / 0.4717 / 0.6325 | 0.7292 / 0.8750 / 0.7603 | 消融参考。说明通用知识缺失会显著伤害覆盖，但与 +general 版本提交不同。 |
| v2.3 递归父子 | 07-18；`knowledge_parent_child_v1` | 142 条全场景；Commit `5e5cb04`；Prompt `f49c...` | 0.7411 / 0.3304 / 0.6522 / 0.5804 | 0.4628 / 0.4505 / 0.4304（74 条标注） | 参考。父递归 `1200/160`，子递归 `320/48`；场景和统计口径均不同，不能与 32 条 knowledge-only 横比。 |
| fixed-parent-child-v1 | 07-23；`knowledge_fixed_parent_child_v1` | 32 knowledge；Commit `cbd3e97`；Prompt `110008...` | 0.7701 / 0.3671 / 0.5682 / 0.6197 | 0.8646 / 0.9062 / 0.8623 | 方案探索参考。父固定 `800/100`，子固定 `400/60`，同时改变父子检索、回填和文档组装；提交也不同。 |

缩写：AR = Answer Relevancy，CP = Context Precision，CR = Context Recall，F = Faithfulness，R@5 = Recall@5。

历史报告：

- `evals/reports/agent-v2.1-ragas.local.json`
- `evals/reports/agent-recursive-v1-product-only.json`（与 `agent-recursive-v1.json` 为同次商品 only 结果）
- `evals/reports/agent-v2.3-full.json`
- `evals/reports/agent-fixed-parent-child-v1.json`

## 5. 各方案的知识组织与分块边界

| 方案 | 商品知识 | 通用知识 | 检索结构 |
|---|---|---|---|
| v2.1 | 营销描述、单条 FAQ、每 3 条评价构成语义知识块；短块不应再被无意义拆开 | 固定 `500/50` | 单层 Top5 chunk |
| recursive_v1 | 商品语义组装后递归 `500/50` | 递归 `500/50` | 单层 Top5 chunk |
| v2.3 | 商品相关内容先合为较大文档，再生成父/子递归块 | 同样进入父/子递归块 | 子块召回、rerank，父块回填 |
| fixed-parent-child-v1 | 商品相关内容先合为文档，再生成父/子固定块 | 同样进入父/子固定块 | 子块召回、rerank，父块回填 |

父子方案的弱点不是“父子结构一定无效”，而是商品语义单元在合并和父块回填后可能被稀释；大父块还会把未命中的内容带入回答上下文。这也是它们不能视为只更换切分器的原因。

## 6. 已知评测限制

1. 旧报告中的评测层会将一个真实检索 chunk 按空行拆成多个 `retrieved_contexts`。该问题已在当前代码修复：现在按生成的 `[资料N] 来源：` / `[网络资料N] 来源：` 块头切分；旧报告的 Context Precision、Context Recall 和 Faithfulness 仍应视为历史参考。
2. RAGAS 本身依赖模型调用，存在 `max_tokens` 等偶发评分失败。修复后应重新运行正式对照组，并按相同成功 case 计算配对均值。
3. Contract、路由和端到端延迟会受到模型、网络和运行环境影响。除非以固定运行环境多次重复，否则不把这些波动解释为 chunking 的效果。
4. 不同 commit、prompt 指纹、case 范围或 collection 数据内容的报告只能作为设计参考，不能充当严格对照组。

## 7. 后续实验建议

下一组值得做的正式实验是独立的混合方案：`knowledge_hybrid_v1`。

- 商品知识沿用 v2.1 的语义组装，不把营销描述、FAQ、评价强行合并后再大块切分；
- 通用知识按主题建立父子块；
- 固定当前 commit、prompt、32 条 case、embedding、rerank 和评测实现；
- 与 v2.1 当前复测、recursive_v1 + general 在相同 case 交集上做配对 RAGAS 比较。

在完成评测 context 拆分修复前，不建议继续做大量 chunk 尺寸网格搜索。当前证据显示，商品知识的语义边界和父子回填策略比单纯微调 `500/50` 的数值更值得优先优化。
