# Agent 评测续跑说明

更新时间：2026-07-25

## 目的

这份说明记录如何对已有评测报告做定向续跑，避免每次把整套 Agent 评测重新跑一遍。

适用两种场景：

1. 只重跑失败、超时、报错的 case。
2. 只补跑已经有回答和检索上下文，但 RAGAS 没成功的 case。

脚本位置：

- [scripts/resume_agent_eval.py](../scripts/resume_agent_eval.py)

## 什么时候用

### 失败续跑

当旧报告里出现以下情况时，用 `--mode failed`：

- `contract.passed == false`
- `response.error == true`
- `response.error_code` 存在

这个模式会重新执行主流程，适合修复路由、超时、工具调用、回答为空等问题后的回归检查。

### 只补 RAGAS

当旧报告里已经有完整回答和 `retrieved_contexts`，但 RAGAS 没跑成功时，用 `--mode ragas`。

这个模式不会重新跑 Agent 主流程，不会重新打 Milvus，也不会重新请求大模型主回答，只补评测。

选择规则：

- `response.task_type == knowledge`
- `response.error != true`
- `retrieved_contexts` 非空
- `ragas.enabled != true` 或 `ragas.error` 存在

## 命令

### 失败续跑

```powershell
python scripts/resume_agent_eval.py `
  --report evals/reports/agent-v2.1-rerun-20260725.json `
  --mode failed `
  --dataset evals/datasets/agent_golden_cases.jsonl `
  --timeout-seconds 90 `
  --ragas `
  --output evals/reports/agent-v2.1-resumed.json `
  --markdown-output evals/reports/agent-v2.1-resumed.md
```

### 只补 RAGAS

```powershell
python scripts/resume_agent_eval.py `
  --report evals/reports/agent-v2.1-smoke-90s.json `
  --mode ragas `
  --dataset evals/datasets/agent_golden_cases.jsonl `
  --output evals/reports/agent-v2.1-ragas-resumed.json `
  --markdown-output evals/reports/agent-v2.1-ragas-resumed.md
```

### 手动指定 case

可重复传 `--case-id`，只重跑你点名的 case。

```powershell
python scripts/resume_agent_eval.py `
  --report evals/reports/agent-v2.1-rerun-20260725.json `
  --mode failed `
  --case-id rag-001 `
  --case-id rag-014 `
  --output evals/reports/agent-v2.1-manual-resume.json
```

## 合并方式

脚本的行为不是生成一个局部报告，而是生成一份完整的新报告。

流程是：

1. 读取旧报告。
2. 按模式挑选需要重跑的 case。
3. 只执行这些 case。
4. 按 `case_id` 替换旧报告里的对应行。
5. 重新计算整份报告的汇总指标。

输出内容：

- JSON 报告
- Markdown 报告

报告 metadata 里会额外写入：

- `metadata.resume.source_report`
- `metadata.resume.mode`
- `metadata.resume.rerun_case_ids`
- `metadata.resume.rerun_case_count`

## 边界

1. 这个脚本只恢复已经落盘的报告。
2. 如果之前进程被强杀，某些 case 从来没写进报告，那部分无法从报告里补回来。
3. `--mode ragas` 依赖旧报告里已经保存了 `retrieved_contexts`。
4. 当前环境如果没有可用 Python 解释器，脚本先保留，等评测环境再执行。

## 当前建议

你的常用路径应该是：

1. 先用 `--mode failed` 补主流程失败项。
2. 再按需要对同一份报告跑 `--mode ragas`，只补评测。

这样比整份 `python -m evals.run_agent_eval` 重跑快很多，尤其是 RAGAS 部分。

## 当前报告现状

我看过 `evals/reports/agent-v2.1-rerun-20260725.json`：

- 总 case 数：32
- 失败 case：30
- 已通过 case：2

这份报告里目前没有可单独补跑 RAGAS 的 case。

`evals/reports/agent-v2.1-smoke-90s.json` 也是同样情况，只有 1 条 case，RAGAS 已经不是续跑重点。
