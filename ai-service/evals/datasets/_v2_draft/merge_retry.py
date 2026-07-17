"""合并 retry 结果到主 contract 报告：产出 agent-v2.1-merged.local.json。

流程:
  1. 读主报告 (142 case)
  2. 读 retry 报告 (4 case)
  3. 按 case_id 匹配替换
  4. 重新调用 calculate_agent_metrics 算 metrics（含 latency 分位）
  5. 重新调用 summarize_retrieval_rows 算检索层指标
  6. 写 merged 报告
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # _v2_draft -> datasets -> evals -> ai-service
sys.path.insert(0, str(ROOT))

from evals.agent_metrics import calculate_agent_metrics
from evals.retrieval_metrics import summarize_retrieval_rows

REPORTS = ROOT / "evals" / "reports"
MAIN = REPORTS / "agent-v2.1-contract.local.json"
RETRY = REPORTS / "agent-v2.1-retry.local.json"
MERGED = REPORTS / "agent-v2.1-merged.local.json"


def main():
    main_report = json.loads(MAIN.read_text(encoding="utf-8"))
    retry_report = json.loads(RETRY.read_text(encoding="utf-8"))

    # 按 id 建索引
    retry_by_id = {c["id"]: c for c in retry_report["cases"]}
    print(f"主报告: {len(main_report['cases'])} case")
    print(f"retry: {len(retry_by_id)} case")

    # 替换
    merged_cases = []
    replaced = []
    for c in main_report["cases"]:
        if c["id"] in retry_by_id:
            new_case = retry_by_id[c["id"]]
            replaced.append(c["id"])
            merged_cases.append(new_case)
        else:
            merged_cases.append(c)

    print(f"\n已替换 {len(replaced)} case: {replaced}")

    # 重新算指标
    new_metrics = calculate_agent_metrics(merged_cases)
    new_retrieval = summarize_retrieval_rows(
        [c["retrieval"] for c in merged_cases], k=5,
    )
    new_failures = [
        c for c in merged_cases
        if not c["contract"]["passed"] or c["judge"].get("passed") is False
    ]

    merged_report = {
        **main_report,
        "cases": merged_cases,
        "metrics": new_metrics,
        "retrieval_summary": new_retrieval,
        "failures": new_failures,
        "merged_from": {
            "main": str(MAIN.name),
            "retry": str(RETRY.name),
            "replaced_case_ids": replaced,
        },
    }

    MERGED.write_text(
        json.dumps(merged_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n合并报告已写入: {MERGED}")

    # 对比
    print()
    print(f"{'指标':<32} {'原始':>10} {'合并后':>10}")
    print("-" * 55)
    old_m = main_report["metrics"]
    new_m = new_metrics
    print(f"{'Contract Pass Rate':<32} {old_m['contract_pass_rate']:>10.2%} {new_m['contract_pass_rate']:>10.2%}")
    print(f"{'Task Success Rate':<32} {old_m['task_success_rate']:>10.2%} {new_m['task_success_rate']:>10.2%}")
    print(f"{'P50 Latency (ms)':<32} {old_m['latency_ms']['p50']:>10.0f} {new_m['latency_ms']['p50']:>10.0f}")
    print(f"{'P95 Latency (ms)':<32} {old_m['latency_ms']['p95']:>10.0f} {new_m['latency_ms']['p95']:>10.0f}")
    print(f"{'Mean Latency (ms)':<32} {old_m['latency_ms']['mean']:>10.0f} {new_m['latency_ms']['mean']:>10.0f}")
    print(f"{'Retrieval Recall@5':<32} {main_report['retrieval_summary']['metrics']['recall@5']:>10.4f} {new_retrieval['metrics']['recall@5']:>10.4f}")
    print(f"{'Retrieval MRR@5':<32} {main_report['retrieval_summary']['metrics']['mrr@5']:>10.4f} {new_retrieval['metrics']['mrr@5']:>10.4f}")
    print(f"{'Retrieval NDCG@5':<32} {main_report['retrieval_summary']['metrics']['ndcg@5']:>10.4f} {new_retrieval['metrics']['ndcg@5']:>10.4f}")

    # 场景拆分
    print()
    print(f"{'Scenario':<25} {'Case':>6} {'原始':>10} {'合并后':>10}")
    print("-" * 55)
    for s in sorted(new_m["scenario_breakdown"].keys()):
        old_pass = old_m["scenario_breakdown"][s]["contract_pass_rate"]
        new_pass = new_m["scenario_breakdown"][s]["contract_pass_rate"]
        n = new_m["scenario_breakdown"][s]["case_count"]
        arrow = " ↑" if new_pass > old_pass else (" ↓" if new_pass < old_pass else "")
        print(f"  {s:<23} {n:>6} {old_pass:>10.2%} {new_pass:>10.2%}{arrow}")


if __name__ == "__main__":
    main()
