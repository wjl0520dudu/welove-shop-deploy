# Phase 4：Agent 评测闭环测试指南

## 1. 范围与执行顺序

本阶段建立离线评测闭环，不把额外 Judge 放进用户线上请求。执行顺序固定：

```text
Golden Dataset
  -> Contract Test（零模型成本）
  -> DeepEval GEval（可选，最终回答质量）
  -> RAGAS（可选，仅 Knowledge RAG）
  -> JSON / Markdown 报告、基线差异与失败样本
```

`Contract Test` 是提交门禁；DeepEval 和 RAGAS 是低频回归工具。它们的离线结果不能表述为线上 CTR、转化率或 SLA。

## 2. 已实现内容

- Golden Dataset：`ai-service/evals/datasets/agent_golden_cases.jsonl`，32 条 Case，按 10 个文本商品、10 个 Knowledge RAG、6 个图文商品、6 个 DAG 多任务分层；
- 硬 Contract：route、task type、工具、商品 ID/品类、最终答案、子任务覆盖、错误状态、延迟、SSE `final/done`；
- 汇总指标：Contract Pass Rate、Task Success Rate/Pass@1、TTFT、P50/P95、场景拆分、失败原因；
- DeepEval：一个 `AgentAnswerQuality` GEval rubric，在 Contract 通过后检查多问题覆盖、知识来源依据、商品卡字段一致性和幻觉；
- RAGAS：只评 Knowledge 行的 Faithfulness、Answer Relevancy、Context Precision、Context Recall；
- 版本信息：报告记录当前 Git Commit、LLM、路由阈值、Embedding/Rerank 配置，支持与基线 JSON 比较。

KnowledgeAgent 新增仅供进程内评测使用的 `retrieved_contexts`。API response adapter 不序列化它，所以 H5/Java 仍保持原有 `AIResponse` 体积和契约。

## 3. 环境准备

在 `ai-service` 下执行。

```powershell
# Contract、数据集与指标逻辑，无外部依赖
python -m pytest tests/test_agent_evaluation.py -q

# 只在评测机器安装；不加入生产 requirements.txt
pip install -r requirements-eval.txt
```

DeepEval 读取其默认支持的 Judge 配置，模型名可用 `DEEPEVAL_MODEL` 指定。RAGAS 使用 OpenAI-compatible client，优先读取：

```text
RAGAS_EVAL_API_KEY
RAGAS_EVAL_BASE_URL
RAGAS_EVAL_MODEL
RAGAS_EVAL_EMBEDDING_MODEL
```

未配置时 RAGAS 回退读取 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`LLM_MODEL`。任何真实 Key 只能放在本地 `.env`。

## 4. 已录制结果的零成本回归

录制文件是 JSONL，每行至少包含 `id`、`response`，可选 `latency_ms`、`ttft_ms`、`sse_events`：

```json
{"id":"shop-01","latency_ms":820,"ttft_ms":210,"sse_events":["start","route","final","done"],"response":{"route":"shopping","task_type":"shopping","answer":"...","product_cards":[]}}
```

运行：

```powershell
python -m evals.run_agent_eval `
  --recorded-results evals/reports/agent-recording.local.jsonl `
  --output evals/reports/agent-contract.local.json `
  --markdown-output evals/reports/agent-contract.local.md
```

缺失 Case 会被标为 `EVAL_RESULT_MISSING`，不会静默跳过。`evals/reports/` 已被 `.gitignore` 忽略，不提交真实报告和 Judge cache。

## 5. 运行中 API 的集成评测

1. 启动 ai-service、模型、Milvus 与所需业务服务；
2. 将 Dataset 中 `replace-with-local-oss-image` 改成可 HEAD 访问的测试图片。推荐复制出 `.local.jsonl` 再替换，不改提交的数据集；
3. 运行：

```powershell
python -m evals.run_agent_eval `
  --base-url http://127.0.0.1:8000/api/assistant `
  --timeout-seconds 30 `
  --output evals/reports/agent-v1.local.json `
  --markdown-output evals/reports/agent-v1.local.md
```

有 `require_sse=true` 的 Case 会额外调用 `/stream`（图文为 `/multimodal/stream`），断言同时得到 `final`、`done` 并记录 TTFT。图文 Case 默认选择 `/multimodal/run`。

可通过 `--scenario knowledge`、`--tag dag`、`--case-id dag-01` 或 `--limit 10` 缩小本次评测范围；这些参数可组合，适合先跑低成本核心 Case 再做全量回归。

## 6. 启用 DeepEval / RAGAS

先通过 Contract，再低频运行 DeepEval：

```powershell
python -m evals.run_agent_eval `
  --base-url http://127.0.0.1:8000/api/assistant `
  --deepeval --judge-threshold 0.6 `
  --output evals/reports/agent-judge-v1.local.json
```

RAGAS 绝不能用只有标题的 `sources` 代替检索片段。HTTP 响应默认不含原始 chunks，因此 RAGAS 会明确标记 `retrieved_contexts_missing` 并跳过。需评 RAGAS 时，优先使用进程内执行模式，它会保留 KnowledgeAgent 的原始 `retrieved_contexts`：

```powershell
python -m evals.run_agent_eval `
  --direct `
  --scenario knowledge `
  --ragas --output evals/reports/agent-ragas-v1.local.json
```

也可以传入保存了 `retrieved_contexts` 的 `--recorded-results`。HTTP 模式的跳过不是通过也不是失败，而是数据采集不完整；补齐 context 后再报告 RAGAS 分数。

`Context Precision` 和 `Context Recall` 还要求 `expected.ragas_reference` 是与当前项目知识库一致的事实型标准答案。普通的“应说明某某内容”验收描述不能冒充标准答案；缺少该字段时只计算 Faithfulness 和 Answer Relevancy，并显式跳过两个 Context 指标。

## 7. 指标解释与验收

| 指标 | 定义 | 用途 |
|---|---|---|
| Contract Pass Rate | 硬约束全部通过的比例 | 最优先、稳定、低成本 |
| Task Success Rate / Pass@1 | Contract 通过；启用 Judge 时 Judge 同时通过 | 当前无重试时等于 Pass@1 |
| TTFT | 第一个 token/final/error SSE 事件耗时 | 流式体验 |
| P50/P95 Latency | API 端到端耗时分位数 | DAG、模型或检索改动对比 |
| Recall@5 / MRR@5 / NDCG@5 | 相关结果覆盖、首个命中位置和整体排序质量 | 仅对配置了 `retrieval_grades` 的检索 Case 计算 |
| RAGAS Faithfulness | 回答声明被上下文支持的比例 | Knowledge 幻觉专项 |
| RAGAS Context Precision/Recall | 相关块是否靠前、能否覆盖参考答案 | 分块/检索专项 |

提交前检查：

1. `new_failures` 为空；
2. `contract_pass_rate` 和 `task_success_rate` 不下降；
3. `failure_reason_counts` 归因到 route、tool、product_cards、SSE 或 judge；
4. RAG 改动只比较 Knowledge 场景的 RAGAS；不要用 RAGAS 评商品排序或 DAG。

基线对比示例：

```powershell
python -m evals.run_agent_eval `
  --recorded-results evals/reports/agent-current.local.jsonl `
  --baseline evals/reports/agent-v1.local.json `
  --output evals/reports/agent-v2.local.json
```
