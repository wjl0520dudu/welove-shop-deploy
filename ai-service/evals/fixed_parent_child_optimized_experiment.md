# 固定父子分块优化实验（fixed_parent_child_v1）

## 1. 实验目的

验证固定长度的父子分块，结合更小的父块和更完整的子块，是否能同时：

- 保留父子检索的上下文覆盖能力；
- 降低 v2.3 递归父子分块中由大父块回填带来的无关上下文；
- 在 RAGAS 的 Context Precision、Faithfulness 上优于 v2.3，并尽量接近或超过 v2.1。

这是一组**面向可上线效果的优化实验**，不是只隔离切分器差异的因果实验：切分方式和分块大小均有调整。

## 2. 已有结论与参数依据

| 版本 | 策略 | 参数 | 已观察到的现象 |
|---|---|---|---|
| v2.1 | 单层固定分块 | `500 / 50` | 当前综合基线，检索 Recall 和 RAGAS 整体最均衡。 |
| v2.3 | 递归父子分块 | 父 `1200 / 160`；子 `320 / 48` | Context Recall 较高，但 Context Precision、Faithfulness、Answer Relevancy 下降。 |
| recursive-v1 | 单层递归分块 | `500 / 50` | 相比 v2.3 回升，但仍未超过 v2.1，尤其召回不足。 |

本实验采用以下推断：

1. v2.3 的父块 1200 字符偏大，命中子块后回填的父块包含更多无关内容，可能损害 Precision 与 Faithfulness。
2. v2.3 的子块 320 字符较小；结合 recursive-v1 的 Recall 下滑，可能使证据更容易被切散。
3. v2.1 的固定分块 500/50 是经过历史结果验证的可用尺度。因此固定父子方案应向该尺度靠近，但仍保留“子检索、父回填”的结构优势。

## 3. 实验配置（冻结）

### 3.1 唯一实验变量

| 层级 | 切分器 | chunk_size | chunk_overlap | 设计理由 |
|---|---|---:|---:|---|
| 父块 | `CharacterTextSplitter` | 800 | 100 | 比 v2.3 父块小 33%，减少父块回填噪声；仍能容纳相邻说明、FAQ 或注意事项。 |
| 子块 | `CharacterTextSplitter` | 400 | 60 | 比 v2.3 子块更完整，接近 v2.1 的有效尺度，减少证据被切散的风险。 |

固定分块的分隔符与 v2.1 保持一致：`"\\n\\n"`。父块按固定切分生成后，每个父块独立再按固定切分生成子块。

### 3.2 必须保持不变的条件

| 项目 | 固定值 |
|---|---|
| 父子检索链路 | 子块召回 → 子块 rerank → 父块聚合 → 父块回填 |
| Embedding | `text-embedding-v4` |
| Rerank | `qwen3-rerank`，对子块执行 |
| 初始召回数 | `RAG_INITIAL_TOP_K=20` |
| 最终检索数 | 保持当前服务配置，不得为实验单独修改 |
| 回填上限 | 保持现有 `build_local_parent_windows()` 的配置，不得为实验单独修改 |
| 生成模型 | `qwen-plus` |
| RAGAS LLM | `qwen-plus` |
| RAGAS embedding | `text-embedding-v4` |
| 数据集 | `evals/datasets/agent_golden_cases.jsonl`，指纹 `d7c852af8570e81f` |
| 评测范围 | 仅 `knowledge` 的 32 条 case；所有对照组必须使用完全相同 case ID |

## 4. 实现边界

1. **禁止修改**既有固定单层分块、v2.3 递归父子分块、recursive-v1 的逻辑与参数。
2. 新增独立函数接口，例如 `build_fixed_parent_child_records(...)`；函数返回父记录和子记录，接口形态与现有 `build_parent_child_records(...)` 对齐，供上游入库逻辑调用。
3. 新增独立索引：`knowledge_fixed_parent_child_v1`。不得复用、清空或写入 `my_rag_collection`、`knowledge_parent_child_v1`、`knowledge_recursive_v1`。
4. 运行时仍使用 `RAG_PARENT_CHILD_ENABLED=true`，以复用现有子检索、rerank、父块聚合和父块回填链路；只让入库阶段调用新增的固定父子构建函数。
5. 新增独立的 ingest、smoke test、experiment runner。不得为了本实验改写已有脚本的默认行为。
6. `.env` 仅可在实验进程内临时覆盖，并在结束后按原始文本完整恢复；不得提交密钥，也不得输出任何 API Key。

## 5. 推荐文件与产物

| 类型 | 建议路径 |
|---|---|
| 固定父子构建函数 | `app/infrastructure/retrieval/fixed_parent_child.py` |
| 入库脚本 | `scripts/ingest_fixed_parent_child_v1.py` |
| Smoke test | `scripts/smoke_test_fixed_parent_child_v1.py` |
| 索引准备脚本 | `scripts/prepare_fixed_parent_child_v1_index.py` |
| RAGAS 运行器 | `scripts/run_fixed_parent_child_v1_ragas.py` |
| 冻结 case 文件 | `evals/datasets/fixed_parent_child_v1_frozen_cases.json` |
| JSON 报告 | `evals/reports/agent-fixed-parent-child-v1.json` |
| Markdown 报告 | `evals/reports/agent-fixed-parent-child-v1.md` |
| 对比摘要 | `evals/reports/agent-fixed-parent-child-v1-comparison.json` |

冻结 case 文件应写入全部 32 个 knowledge case ID（`rag-001` 至 `rag-032`）。若历史报告中某个 case 的 RAGAS 评分失败，不得从输入集删除；应在报告中单独记录失败原因，并仅在最终“配对样本”聚合时同时剔除该 case。

## 6. 执行流程

### 6.1 实现自检

在连接 Milvus 前运行单元/导入检查：

1. 对一段超过 1600 字符的中英文混合文本构建父子记录。
2. 断言父块最大长度不超过 800（允许分隔符实现产生的极小边界差）。
3. 断言子块最大长度不超过 400。
4. 断言每条子记录都有有效的 `parent_id`，且 `parent_id` 能在父记录中找到。
5. 断言同一 parent 下 `child_index` 从 0 连续递增。
6. 断言调用新增函数不影响现有 `build_parent_child_records()` 的输出。

### 6.2 创建和灌入独立索引

1. 设置实验进程变量：

   ```text
   MILVUS_COLLECTION=knowledge_fixed_parent_child_v1
   RAG_PARENT_CHILD_ENABLED=true
   ```

2. 使用与 v2.1 / v2.3 相同的数据源灌入商品 `rag_knowledge` 和静态知识文档。
3. 入库前只允许删除目标 collection；删除前打印并确认目标名称严格等于 `knowledge_fixed_parent_child_v1`。
4. 记录：源文档数、父块数、子块数、平均/中位/P95 父块与子块长度、空块数、孤儿子块数。

### 6.3 检索 Smoke Test

至少检查以下 case：`rag-001`、`rag-007`、`rag-008`、`rag-013`、`rag-015`。

每个 case 输出并人工检查：

1. 原始 Top20 子块候选（`doc_id`、`parent_id`、`child_index`、分数、内容摘要）；
2. rerank 后 Top5 子块；
3. 父块聚合结果和最终回填的父块内容长度；
4. 命中 child 的证据是否在回填父块中；
5. 是否触发 fallback；若触发，记录原因但不要把结果混入纯 Milvus 分块结论。

### 6.4 正式评测

对**相同冻结的 32 条 knowledge case**运行 Contract、检索指标和 RAGAS。DeepEval 不属于本次分块实验的主指标，为控制预算不执行。运行命令以新 runner 实现为准，等价逻辑为：

```bash
cd ai-service
# 第一步：只创建并灌入新的实验向量库（会删除的也仅是该实验 collection）
python scripts/prepare_fixed_parent_child_v1_index.py

# 第二步：只对已准备好的实验向量库运行 RAGAS / Contract / 检索评测
python scripts/run_fixed_parent_child_v1_ragas.py
```

运行器必须：

1. 在加载 `.env` 后再读取 `RAGAS_EVAL_*`；
2. 使用 DashScope 的 OpenAI 兼容配置，禁止使用已废弃的 Anthropic 代理地址；
3. 无论成功或异常，均恢复 `.env` 原文；
4. 生成有效 UTF-8 JSON；用 `python -m json.tool <报告路径>` 校验；
5. 不使用旧评分缓存来冒充本次 RAGAS 结果。

## 7. 评估与配对比较规则

### 7.1 指标

| 类别 | 指标 | 解释 |
|---|---|---|
| RAGAS | Answer Relevancy | 最终回答是否回应问题 |
| RAGAS | Context Precision | 提供给模型的上下文是否相关、排序是否干净 |
| RAGAS | Context Recall | 金标准所需信息是否被上下文覆盖 |
| RAGAS | Faithfulness | 回答是否可由检索上下文支持 |
| 检索 | Recall@5 | 标注相关文档是否被召回 |
| 检索 | MRR@5 / NDCG@5 | 相关结果的排序质量 |
| 服务 | Contract Pass Rate / Task Success | 路由、回答、错误、输出结构等确定性检查 |
| 性能 | P50/P95 Latency | 端到端时延；仅作观察，不单独归因给分块 |

### 7.2 严格比较口径

1. 主比较以 v2.1、v2.3、本实验三者**均成功获得对应 RAGAS 指标**的相同 case ID 交集为准。
2. 除配对均值外，报告每个指标的样本数和被排除 case ID / 原因。
3. 32 条原始输入 case 的 Contract、延迟、失败情况必须完整报告，不因 RAGAS 失败而删除。
4. 历史报告若 prompt、代码提交、模型或环境不一致，必须标注为混杂因素；不得把它们写成纯粹由分块导致的因果结论。

## 8. 验收标准

本组的优先目标是取得更均衡的效果，而不是单一指标最高。

| 指标 | 成功判定 |
|---|---|
| Context Precision | 高于 v2.3，且尽量接近 v2.1（差距不超过 0.03 为可接受） |
| Faithfulness | 高于 v2.3，且尽量接近 v2.1（差距不超过 0.03 为可接受） |
| Context Recall | 不低于 v2.1 超过 0.03；若高于 v2.1 则更优 |
| Recall@5 | 不低于 v2.1 超过 0.05 |
| Answer Relevancy | 不低于 v2.1 超过 0.03 |
| P95 Latency | 不超过 v2.1 的 1.15 倍，且无新增系统性超时 |

推荐规则：若固定父子优化版同时满足 Precision、Faithfulness、Recall@5 三项，并且 Answer Relevancy 没有明显下降，可进入候选方案；若仍显著落后 v2.1，则 v2.1 固定单层分块继续作为默认方案。

## 9. 最终报告要求

Markdown 与 JSON 报告均必须包含：

1. 实际 git commit、dirty 状态、prompt 指纹、数据集指纹、模型与检索配置；
2. 父/子块统计和索引名称；
3. 32 条 case 的执行汇总；
4. 配对后的四项 RAGAS 对比表：v2.1、v2.3、fixed_parent_child_v1；
5. Recall@5、MRR@5、NDCG@5 对比；
6. Contract、Task Success、P50/P95 延迟；
7. 每个 RAGAS 指标的成功样本数、排除项与错误信息；
8. 一个提升案例、一个退化案例、一个边界/失败案例：附问题、Top5 子块、父块回填摘要、回答摘要及分析；
9. 清晰结论：推荐 v2.1、v2.3、recursive-v1 或 fixed_parent_child_v1 中的哪一个，以及证据和已知限制。

## 10. 交给测试 Agent 的执行提示词

```text
请执行 fixed_parent_child_v1 RAG 分块实验，严格遵循
ai-service/evals/fixed_parent_child_optimized_experiment.md。

目标：新增“固定父子分块优化版”实验能力，父块 CharacterTextSplitter 800/100，子块 CharacterTextSplitter 400/60；子检索、子 rerank、父块聚合、父块回填链路保持不变。

边界：不得修改或替换既有 v2.1 固定单层、v2.3 递归父子、recursive-v1 单层递归逻辑；新增独立函数接口、独立 ingest/smoke/runner 和独立 Milvus collection knowledge_fixed_parent_child_v1。不得新增 HTTP 路由。不得泄露或写入密钥。

测试：使用同一份 agent_golden_cases.jsonl 的全部 32 条 knowledge case；完成入库统计、5 个 smoke case、Contract、检索指标、RAGAS，并产出有效 JSON 与 Markdown 报告。RAGAS 必须使用两边均成功评分的相同 case ID 做配对均值；同时报告原始 32 条执行情况和所有评分失败原因。

完成后说明：修改文件清单、运行命令、索引统计、报告路径、对 v2.1/v2.3 的配对指标对比、最终推荐结论及任何无法验证的外部依赖。
```
