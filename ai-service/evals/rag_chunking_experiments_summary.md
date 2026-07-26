# 商品与通用知识 RAG 分块实验档案

更新时间：2026-07-26

本文记录商品知识库和通用知识库所有已执行的 RAG 分块实验。它用于回顾设计、定位对应脚本和报告，并明确哪些结果可以比较，哪些只能作为历史参考。

## 1. 术语与数据边界

知识库由两类数据组成：

| 数据类型 | 内容 | 当前推荐的组织原则 |
|---|---|---|
| 商品知识 | 每个商品的营销描述、官方 FAQ、用户评价 | 保留业务语义边界：营销描述一个块、每条 FAQ 一个块、每 3 条评价一个块 |
| 通用知识 | 8 篇静态商品/护肤/数码/服饰/食品知识文档，`doc_id=900001..900008` | 可按固定长度、递归边界或 Markdown 主题进行切分 |

这里的“商品语义块”是确定性规则，不是由大模型自动识别：

1. 一条营销描述组成一个 `marketing` 块。
2. 一组问答组成一个 `faq` 块。
3. 每 3 条评价组成一个 `review` 块。

`500/50`、`1000/100` 等参数均为字符级 `chunk_size/chunk_overlap`，不是 token 数。检索默认采用 hybrid（dense + BM25）-> rerank，初始 Top20，最终 Top5。

## 2. 评测口径

当前知识问答评测集为 `evals/datasets/agent_golden_cases.jsonl`：

| 项目 | 固定值 |
|---|---|
| 场景 | 32 条 `knowledge` case |
| 数据集指纹 | `d7c852af8570e81f` |
| Embedding | `text-embedding-v4` |
| Rerank | `qwen3-rerank` |
| 回答模型 / RAGAS LLM | `qwen-plus` |
| 检索标注 | 16 条 case 有 relevance 标注，用于 Recall@5、MRR@5、NDCG@5 |

RAGAS 会受模型输出、网络和 `max_tokens` 影响，四项指标的有效样本数可能不同。因此：

- 原始均值必须同时看样本数 `n`。
- 比较两个报告时，以两边都成功产出该指标的相同 case ID 的配对均值为准。
- Contract、延迟、路由超时属于端到端运行现象，不能单独归因于分块策略。

## 3. 策略全景

### 3.1 当前“混合数据组织”实验

这些实验都保留商品知识的语义单元；变化只在通用知识的切分方式或检索回填方式。

| 策略 | Collection | 商品知识 | 通用知识 | 检索形式 | 灌入脚本 |
|---|---|---|---|---|---|
| v2.1 固定单层 | `my_rag_collection` | 语义块直存 | 固定 `500/50` | 单层 Top5 | `ingest_knowledge_v2.py` |
| recursive_v1 + general | `knowledge_recursive_v1` | 语义组装后递归 `500/50` | 递归 `500/50` | 单层 Top5 | `ingest_recursive_v1.py` |
| semantic_v1 | `knowledge_semantic_v1` | 语义块直存 | Markdown `##` 主题块；过大主题再按 `###` 分割 | 单层 Top5 | `ingest_semantic_v1.py` |
| mixed fixed parent-child | `knowledge_mixed_fixed_parent_child_v1` | 语义块直存，不走父子回填 | 父固定 `1000/100`，子固定 `500/50` | 商品块直出；通用子块召回/rerank 后回填父窗口 | `ingest_mixed_fixed_parent_child_v1.py` |
| semantic + recursive general | `knowledge_semantic_recursive_general_v1` | 语义块直存 | 递归 `500/50` | 单层 Top5 | `ingest_semantic_recursive_general_v1.py` |

### 3.2 旧“全部内容合并后再分块”实验

下列旧父子实验把一个商品的营销描述、所有 FAQ、所有评价先合成较长文档，再统一进行父子切分；通用知识也使用同一父子路径。它们会破坏商品 FAQ/评价的原始语义边界。

这类实验回答的是“整篇商品文档的父子切块是否有效”，不是“仅替换通用知识切分器是否有效”。不能和第 3.1 节的混合策略当作同一变量的对照。

| 策略 | Collection | 商品与通用知识组织 | 父块 / 子块 | 结论定位 |
|---|---|---|---|---|
| v2.3 recursive parent-child | `knowledge_parent_child_v1` | 商品内容先合并；通用知识也进入父子递归 | 递归 `1200/160` / `320/48` | 历史探索，数据范围和评测口径不同 |
| fixed_parent_child_v1 | `knowledge_fixed_parent_child_v1` | 商品内容先合并；通用知识也进入父子固定 | 固定 `800/100` / `400/60` | 历史探索，商品语义被稀释 |

## 4. 当前 32 条知识问答结果

下表来自当前可用报告。RAGAS 各列的括号为该指标有效样本数，检索指标固定在 16 条有标注 case 上计算。

| 策略 | AR | CP | CR | Faithfulness | Recall@5 | MRR@5 | NDCG@5 | Contract | 报告 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| v2.1 固定单层 | 0.7741 (25) | 0.7358 (20) | 0.6842 (20) | 0.7187 (25) | 0.8646 | 0.8646 | 0.8381 | 93.75% | `agent-v2.1-resumed-20260725.json` |
| semantic_v1 | 0.7822 (26) | 0.7365 (20) | 0.6800 (20) | 0.7111 (26) | 0.8021 | 0.8125 | 0.7838 | 87.50% | `agent-semantic-v1.json` |
| mixed fixed parent-child | 0.7843 (26) | 0.8540 (21) | 0.7341 (21) | 0.7036 (26) | 0.8646 | 0.8750 | 0.8463 | 90.62% | `agent-mixed-fixed-parent-child-v1.json` |
| semantic + recursive general | 0.7363 (27) | 0.7633 (20) | 0.6300 (20) | 0.6967 (27) | 0.8646 | 0.8750 | 0.8463 | 90.62% | `agent-semantic-recursive-general-v1.json` |

### 4.1 相对 v2.1 的配对 RAGAS 差异

Delta 为“候选策略 - v2.1”，仅在两个报告对该指标均成功评分的同一 case ID 上计算。正数表示候选更高。

| 策略 | AR Delta | CP Delta | CR Delta | Faithfulness Delta | 解读 |
|---|---:|---:|---:|---:|---|
| semantic_v1 | +0.0178 (n=24) | +0.0534 (n=19) | +0.0132 (n=19) | -0.0089 (n=24) | 数值改善幅度小，但检索三项下降；没有形成可靠优势 |
| mixed fixed parent-child | +0.0068 (n=25) | +0.1108 (n=20) | +0.0367 (n=20) | -0.0050 (n=25) | 当前最有希望的候选：上下文相关性和覆盖均改善，忠实度基本持平 |
| semantic + recursive general | -0.0218 (n=25) | +0.0275 (n=20) | -0.0542 (n=20) | -0.0160 (n=25) | 片段更聚焦但覆盖和答案质量下降，应淘汰 |

### 4.2 当前结论

1. `my_rag_collection` 的 v2.1 是可用、稳定的固定单层基线。
2. `knowledge_mixed_fixed_parent_child_v1` 是当前最强候选：商品语义块不被合并，父子结构只用于通用知识。它比 v2.1 的 CP 和 CR 更高，且检索指标不低。
3. `knowledge_semantic_v1` 不能证明主题单层优于 v2.1：虽然部分配对 RAGAS 略高，但 3 个检索指标均下降。
4. `knowledge_semantic_recursive_general_v1` 不适合作为最终方案：递归单层仅带来 CP 小幅提升，AR、CR、Faithfulness 均下降。32 条中有 23 条 Top5 完全不变，说明当前短通用文档的递归边界改动有限。

以上结果仍属于候选筛选，不是最终统计结论。v2.1 报告的提交为 `d7e245b`，后三个报告为 `e0ac6ed`；虽使用相同数据集、模型和检索参数，最终定版前应在同一提交、同一运行环境下重跑 v2.1 与 mixed fixed parent-child，并进行配对比较。

## 5. 历史实验与参考结果

这些报告保留设计演进信息，但存在不同提交、不同 Prompt、不同 case 范围或旧评测上下文拆分问题，不能直接同第 4 节做数值相减。

| 实验 | 日期 / Collection | 关键策略 | AR / CP / CR / F | R@5 / MRR / NDCG | 可比性与收获 |
|---|---|---|---|---|---|
| v2.1 历史基线 | 07-17, `my_rag_collection` | 商品语义块 + 通用固定 `500/50` | 0.8107 / 0.4040 / 0.5561 / 0.6672 | 0.8646 / 0.8958 / 0.8489 | Prompt 为 `f49c...`，仅作历史参考 |
| recursive_v1 商品 only | 07-22, `knowledge_recursive_v1` | 商品语义内容递归 `500/50`，未导入通用知识 | 0.7921 / 0.3947 / 0.4717 / 0.6325 | 0.7292 / 0.8750 / 0.7603 | 证明缺少通用知识会显著损害覆盖，不能作为最终方案 |
| v2.3 递归父子 | 07-18, `knowledge_parent_child_v1` | 商品与通用知识均先合并后递归父子 | 0.7411 / 0.3304 / 0.6522 / 0.5804 | 0.4628 / 0.4505 / 0.4304 | 142 条全场景、仅 14 条检索标注；不能横比 32 条知识问答 |
| fixed_parent_child_v1 | 07-23, `knowledge_fixed_parent_child_v1` | 商品与通用知识均先合并后固定父子 `800/100`、`400/60` | 0.7701 / 0.3671 / 0.5682 / 0.6197 | 0.8646 / 0.9062 / 0.8623 | 商品语义边界被合并，且旧评测上下文存在拆分问题；仅作反例和设计参考 |
| recursive_v1 + general | 07-25, `knowledge_recursive_v1` | 商品语义内容递归 `500/50` + 通用递归 `500/50` | 0.7747 / 0.4428 / 0.5652 / 0.6531 | 0.7708 / 0.8750 / 0.7742 | 使用旧上下文解析结果，不能与第 4 节直接比较；递归版 CP 更高但 CR/F 更低的方向可作参考 |

对应报告：

- `agent-v2.1-ragas.local.json`
- `agent-recursive-v1-product-only.json`
- `agent-v2.3-full.json`
- `agent-fixed-parent-child-v1.json`
- `agent-recursive-v1-with-general.json`

`agent-v2.1-rerun-20260725.json` 是一次失败/中断的重跑，RAGAS 有效样本为 0，已由 `agent-v2.1-resumed-20260725.json` 替代，不参与任何结论。

## 6. 为什么旧父子策略表现不可靠

旧父子实验的问题不在于“父子分块一定无效”，而在数据组织：

1. 商品营销描述、所有 FAQ 和所有评价先被拼接，原本独立的问答和评价语义被打散。
2. 子块命中后回填较大的父块，会带入未命中的 FAQ、评价或营销语句，增加噪声。
3. 商品文档和通用文档被同一套父子策略处理，忽略了两类数据的天然结构差异。

混合 fixed parent-child 的设计正是针对这一点：商品语义块直接参与检索与回答；仅通用知识使用“子块检索/rerank -> 父窗口回填”。因此它是与旧父子实验不同的新方案。

## 7. 后续实验决策

| 候选 | 当前决策 | 原因 |
|---|---|---|
| 通用递归父子 | 先干跑比较父/子边界，再决定是否跑 RAGAS | 当前 8 篇通用文档较短，父 `1000/100` 往往接近整篇文档；若边界近似固定父子，完整 RAGAS 没有信息增益 |
| 通用主题父子 | 暂不跑 | 当前主题单层没有可靠优势，且文档标题层级少，父子内容容易重复 |
| mixed fixed parent-child | 保留为最终候选，后续做同提交复测 | 当前 RAGAS 和检索证据最强 |
| v2.1 固定单层 | 保留为对照基线和回退方案 | 结构简单、检索稳定，且商品语义边界得到保留 |

最终定版实验只需重跑两组：v2.1 固定单层与 mixed fixed parent-child。两组应固定同一 Git commit、相同 `.env` 的模型参数、相同 32 条数据集，并以配对 RAGAS 和 16 条检索指标共同决策。

## 8. 运行与恢复索引

| 目的 | 入口 |
|---|---|
| v2.1 商品语义 + 通用固定单层 | `scripts/ingest_knowledge_v2.py` |
| 商品语义 + 通用主题单层 | `scripts/ingest_semantic_v1.py` 与 `evals/semantic_v1_runbook.md` |
| 商品语义 + 通用固定父子 | `scripts/ingest_mixed_fixed_parent_child_v1.py` |
| 商品语义 + 通用递归单层 | `scripts/ingest_semantic_recursive_general_v1.py` |
| 历史递归单层 | `scripts/ingest_recursive_v1.py` |
| 历史全量固定父子 | `scripts/ingest_fixed_parent_child_v1.py` |

每次实验前，必须在 `ai-service/.env` 显式设置 `MILVUS_COLLECTION`、`RAG_PARENT_CHILD_ENABLED`、`RAG_PARENT_CHILD_CHUNKING`、`RAG_PARENT_CHILD_GENERAL_ONLY`、`CHUNK_SIZE` 和 `CHUNK_OVERLAP`，并将结果写入新的报告文件，避免覆盖历史证据。
