# RAG 分块实验对比与结论

## 1. 结论摘要

当前知识库的默认线上方案应继续使用 **v2.1 单层固定分块 `500 / 50`**。

固定父子优化版（父 `800 / 100`、子 `400 / 60`）是一个有效的“高召回备选”：它明显修复了 v2.3 的父子方案在上下文噪声上的问题，且检索排序优于 v2.1；但回答相关性、忠实度和上下文精度仍没有超过 v2.1，同时 P95 延迟更高。

单层递归分块与原始递归父子分块均不建议继续作为候选默认方案。

## 2. 实验范围与统一条件

- Golden Dataset：`evals/datasets/agent_golden_cases.jsonl`
- 数据集指纹：`d7c852af8570e81f`
- 主评测范围：32 条 `knowledge` case
- Embedding：`text-embedding-v4`
- Rerank：`qwen3-rerank`
- 初始召回：`RAG_INITIAL_TOP_K=20`
- 最终检索：Top5
- 回答模型与 RAGAS LLM：`qwen-plus`
- 检索链路：hybrid（dense + BM25）→ rerank；父子方案对**子块**进行 rerank，再按父块聚合并回填父块。

> RAGAS 存在个别评分失败（例如回答超过 `max_tokens`），因此报告同时保留原始均值和按相同成功评分 case 配对后的均值。跨版本判断以“配对均值”为主。

## 3. 方案与参数

| 版本 | 方案 | 切分器与参数 | 检索/回填 |
|---|---|---|---|
| v2.1 | 单层固定分块 | `CharacterTextSplitter(500 / 50)` | 单层 chunk 检索、rerank、Top5 回答 |
| v2.3 | 递归父子分块 | 父 `RecursiveCharacterTextSplitter(1200 / 160)`；子 `RecursiveCharacterTextSplitter(320 / 48)` | 子检索 → 子 rerank → 父块回填 |
| recursive-v1 | 单层递归分块 | `RecursiveCharacterTextSplitter(500 / 50)` | 单层 chunk 检索、rerank、Top5 回答 |
| fixed-parent-child-v1 | 固定父子优化版 | 父 `CharacterTextSplitter(800 / 100)`；子 `CharacterTextSplitter(400 / 60)` | 子检索 → 子 rerank → 父块回填 |

固定父子优化版使用独立 Milvus collection：`knowledge_fixed_parent_child_v1`，不会覆盖 v2.1、v2.3 或 recursive-v1 的索引。

## 4. RAGAS 原始汇总

原始汇总按每份报告实际成功评分的样本计算，样本数并不完全相同，仅用于观察趋势。

| 指标 | v2.1 | v2.3 | 单层递归 | 固定父子优化版 |
|---|---:|---:|---:|---:|
| Answer Relevancy | 0.8107 (n=27) | 0.7411 (n=31) | 0.7921 (n=26) | 0.7701 (n=27) |
| Context Precision | 0.4040 (n=22) | 0.3304 (n=23) | 0.3947 (n=20) | 0.3671 (n=22) |
| Context Recall | 0.5561 (n=22) | 0.6522 (n=23) | 0.4717 (n=20) | 0.5682 (n=22) |
| Faithfulness | 0.6672 (n=27) | 0.5804 (n=31) | 0.6325 (n=26) | 0.6197 (n=27) |

## 5. 严格配对的 RAGAS 对比

### 5.1 v2.1 vs v2.3 vs 固定父子优化版

以下指标仅使用三个版本都成功获得该指标的相同 case：Faithfulness / Answer Relevancy 为 26 条；Context Precision / Recall 为 21 条。

| 指标 | v2.1 固定 | v2.3 递归父子 | 固定父子优化版 | 优化版相对 v2.3 |
|---|---:|---:|---:|---:|
| Faithfulness | 0.6744 | 0.5630 | 0.6310 | +0.0680 |
| Answer Relevancy | 0.8163 | 0.7442 | 0.7695 | +0.0253 |
| Context Precision | 0.4054 | 0.3301 | 0.3846 | +0.0545 |
| Context Recall | 0.5825 | 0.6191 | 0.5952 | -0.0239 |

解释：缩小父块、增大子块并改用固定切分后，v2.3 的噪声问题得到明显缓解；代价是牺牲了一部分 v2.3 的最高 Recall，但仍保留了高于 v2.1 的 Context Recall。

### 5.2 单层递归 vs 固定父子优化版

以下指标仅使用两个版本都成功获得该指标的相同 case：Faithfulness / Answer Relevancy 为 25 条；Context Precision / Recall 为 20 条。

| 指标 | 单层递归 | 固定父子优化版 | 结论 |
|---|---:|---:|---|
| Faithfulness | 0.6464 | 0.6415 | 基本持平，单层递归略高 |
| Answer Relevancy | 0.7844 | 0.7721 | 单层递归略高 |
| Context Precision | 0.3947 | 0.3538 | 单层递归更干净 |
| Context Recall | 0.4717 | 0.6000 | 固定父子显著更高 |

解释：父子结构有效解决了单层递归的证据覆盖不足，但父块回填仍会增加无关内容，因此 Precision 和回答质量略受影响。

## 6. 检索指标

v2.1、单层递归和固定父子优化版均基于相同的 16 条带检索相关性标注 case，可直接比较。

| 指标 | v2.1 固定 | 单层递归 | 固定父子优化版 |
|---|---:|---:|---:|
| Recall@5 | 0.8646 | 0.7292 | 0.8646 |
| MRR@5 | 0.8958 | 0.8750 | 0.9062 |
| NDCG@5 | 0.8489 | 0.7603 | 0.8623 |

结论：固定父子优化版的 Recall@5 已追平 v2.1，MRR@5、NDCG@5 还略高，说明子块检索与 rerank 的候选排序质量最好。v2.3 的 retrieval summary 覆盖 74 条跨场景标注 case，和上述 16 条 knowledge case 口径不同，未在此表直接比较。

## 7. 服务与性能指标

| 指标 | v2.1 固定 | v2.3 递归父子* | 单层递归 | 固定父子优化版 |
|---|---:|---:|---:|---:|
| Knowledge Contract Pass Rate | 87.50% | 96.88% | 93.75% | 87.50% |
| P50 延迟 | 14.13s | 7.70s | 11.96s | 13.72s |
| P95 延迟 | 18.32s | 17.81s | 17.04s | 22.85s |

\* v2.3 的 latency 来源于 142 条全量 case，不能严格与 32 条 knowledge-only 运行完全等价；仅作参考。

固定父子优化版的 P95 延迟高于 v2.1 约 4.5 秒，不满足本实验“P95 不超过 v2.1 1.15 倍”的目标。Contract 指标还受到路由、模型输出和运行环境影响，不应单独归因于分块。

## 8. 关键发现

1. **v2.1 固定单层是综合最优解。** 它的 Answer Relevancy、Context Precision、Faithfulness 均为四组中最佳或最稳定，且 Recall@5 没有损失。
2. **父子结构的核心收益是召回和排序。** 固定父子优化版的 Recall@5 与 v2.1 持平，MRR/NDCG 更高；它适合“不能漏掉关联证据”的问题。
3. **v2.3 的主要问题是大父块回填造成噪声。** 从父 `1200` 缩至 `800` 后，Faithfulness、Precision、Answer Relevancy 均显著恢复，支持该判断。
4. **子块过小与递归单层都会伤害覆盖。** 单层递归 `500/50` 的 Context Recall 和 Recall@5 最低；提高子块到 `400` 并保留父子召回后，覆盖得到恢复。
5. **父子回填仍有天然取舍。** 即使参数优化后，固定父子仍低于 v2.1 的 Precision/Faithfulness：回填的父块比单层 Top5 chunk 更容易携带无关信息。

## 9. 最终决策

| 方案 | 决策 | 使用场景 |
|---|---|---|
| v2.1 固定单层 `500/50` | 保留为默认线上方案 | 常规商品知识问答，追求整体回答质量和稳定性 |
| 固定父子优化版：父 `800/100`、子 `400/60` | 保留为可选实验/高召回方案 | 对漏召回更敏感、允许较多上下文和较高延迟的场景 |
| v2.3 递归父子：父 `1200/160`、子 `320/48` | 淘汰 | 父块回填噪声过大 |
| 单层递归 `500/50` | 不继续投入 | 没有相对 v2.1 或固定父子优化版的明确优势 |

## 10. 后续建议

本轮已完成两组低成本实验，足以支持当前默认方案选择，**不建议再继续进行分块尺寸网格搜索**。

若未来必须继续优化高召回父子方案，优先研究“命中子块附近窗口回填”或“按父块去重后的上下文预算”，而不是继续单纯调大/调小 chunk。这是因为当前 `build_local_parent_windows()` 仍按父块内容回填，父子方案的剩余问题已经主要是上下文选择，而非纯切分尺寸。

## 11. 关联报告

- `agent-v2.1-ragas.local.json`
- `agent-v2.3-full.json`
- `agent-recursive-v1.json`
- `agent-fixed-parent-child-v1.json`
- `agent-fixed-parent-child-v1-comparison.json`
