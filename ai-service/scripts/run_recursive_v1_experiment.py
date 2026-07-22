"""Main experiment runner for recursive_v1 RAG chunking evaluation.

Orchestrates the full pipeline:
  1. Drop + recreate knowledge_recursive_v1 collection
  2. Ingest all product knowledge docs with recursive chunking
  3. Run smoke tests
  4. Execute RAGAS evaluation on frozen case set
  5. Generate JSON + Markdown reports
  6. Print cross-version comparison table

用法:
    cd ai-service
    python scripts/run_recursive_v1_experiment.py

环境变量（实验控制）:
    RAGAS_EVAL_API_KEY=...                     # RAGAS 评测 LLM API key
    RAGAS_EVAL_MODEL=qwen-plus                 # 评测模型
    RAGAS_EVAL_EMBEDDING_MODEL=text-embedding-v4
    (MILVUS_COLLECTION 和 RAG_PARENT_CHILD_ENABLED 通过 .env 实验临时文件注入)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

# ── project root ──────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = AI_SERVICE_ROOT / ".env"
sys.path.insert(0, str(AI_SERVICE_ROOT))
load_dotenv(ENV_FILE, override=True)

# Experiment-fixed parameters
COLLECTION = "knowledge_recursive_v1"
FROZEN_CASES_FILE = AI_SERVICE_ROOT / "evals" / "datasets" / "recursive_v1_frozen_cases.json"
REPORT_JSON = AI_SERVICE_ROOT / "evals" / "reports" / "agent-recursive-v1.json"
REPORT_MD = AI_SERVICE_ROOT / "evals" / "reports" / "agent-recursive-v1.md"
EVAL_SCRIPT = AI_SERVICE_ROOT / "evals" / "run_agent_eval.py"
DATASET = AI_SERVICE_ROOT / "evals" / "datasets" / "agent_golden_cases.jsonl"

# Experiment env vars (these are NOT in .env — they control the experiment process)
RAGAS_API_KEY = os.getenv("RAGAS_EVAL_API_KEY") or os.getenv("LLM_API_KEY", "")
RAGAS_MODEL = os.getenv("RAGAS_EVAL_MODEL") or os.getenv("LLM_MODEL", "qwen-plus")
RAGAS_EMBEDDING = os.getenv("RAGAS_EVAL_EMBEDDING_MODEL") or os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
RAGAS_BASE_URL = os.getenv("RAGAS_EVAL_BASE_URL") or os.getenv("LLM_BASE_URL", "")


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def git_dirty() -> bool:
    try:
        return bool(subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=str(REPO_ROOT),
            text=True,
        ).strip())
    except Exception:
        return False


def load_frozen_case_ids() -> list[str]:
    with open(FROZEN_CASES_FILE, encoding="utf-8") as f:
        return json.load(f)


def _read_env() -> dict[str, str]:
    """Read resolved .env values while preserving the original file separately."""
    return {
        key: value
        for key, value in dotenv_values(ENV_FILE).items()
        if value is not None
    }


def _write_env(env: dict[str, str]) -> None:
    """Write dict to .env."""
    lines = [f"{k}={v}" for k, v in env.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def with_experiment_env(fn, *args, **kwargs):
    """Context manager: swap .env to experiment config, run fn, restore.

    load_dotenv(ENV_FILE, override=True) runs at config.py import time,
    so we must patch the actual .env file before the subprocess imports config.
    """
    # Keep the original bytes, including comments and section layout.  The
    # experiment needs a temporary flat env file because config.py loads it
    # with override=True, but the user's maintained .env must be restored
    # exactly after every run.
    original_env_text = ENV_FILE.read_text(encoding="utf-8")
    backup = _read_env()

    # Build experiment .env (start from current env, override experiment fields)
    experiment_env = dict(backup)
    experiment_env["MILVUS_COLLECTION"] = COLLECTION
    experiment_env["RAG_PARENT_CHILD_ENABLED"] = "false"
    experiment_env["RAGAS_EVAL_API_KEY"] = RAGAS_API_KEY
    experiment_env["RAGAS_EVAL_MODEL"] = RAGAS_MODEL
    experiment_env["RAGAS_EVAL_EMBEDDING_MODEL"] = RAGAS_EMBEDDING
    if RAGAS_BASE_URL:
        experiment_env["RAGAS_EVAL_BASE_URL"] = RAGAS_BASE_URL

    try:
        _write_env(experiment_env)
        return fn(*args, **kwargs)
    finally:
        ENV_FILE.write_text(original_env_text, encoding="utf-8")


def step_drop_collection():
    """Step 1: Drop the experiment collection if it exists."""
    print("\n" + "=" * 60)
    print("Step 1 — 清理实验 collection")
    print("=" * 60)
    drop_script = AI_SERVICE_ROOT / "scripts" / "drop_milvus_collection.py"
    result = subprocess.run(
        [sys.executable, str(drop_script), "--collection", COLLECTION, "--yes"],
        cwd=str(AI_SERVICE_ROOT),
    )
    if result.returncode == 0:
        print(f"[OK] Collection '{COLLECTION}' 已清理（或不存在）")
    else:
        print(f"[WARN] drop 返回码 {result.returncode}，继续（collection 可能不存在）")


def _run_subprocess(cmd: list, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess with experiment .env injected."""
    env = dict(os.environ)
    # These are set by with_experiment_env already, but pass through explicitly
    env["MILVUS_COLLECTION"] = COLLECTION
    env["RAG_PARENT_CHILD_ENABLED"] = "false"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(cmd, cwd=str(AI_SERVICE_ROOT), env=env)


def step_ingest():
    """Step 2: Ingest knowledge docs with recursive chunking."""
    print("\n" + "=" * 60)
    print("Step 2 — 灌入知识文档（递归分块）")
    print("=" * 60)
    ingest_script = AI_SERVICE_ROOT / "scripts" / "ingest_recursive_v1.py"
    # Ingest script uses MilvusVectorStore(collection_name=...) directly — no .env needed
    result = _run_subprocess(
        [sys.executable, str(ingest_script), "--collection", COLLECTION],
    )
    if result.returncode != 0:
        print(f"[ERROR] 灌入失败，返回码 {result.returncode}")
        print(result.stderr.decode("utf-8", errors="replace") if result.stderr else "")
        sys.exit(1)
    print("[OK] 灌入完成")


def step_smoke_test():
    """Step 3: Run smoke tests on the collection."""
    print("\n" + "=" * 60)
    print("Step 3 — 冒烟测试")
    print("=" * 60)
    smoke_script = AI_SERVICE_ROOT / "scripts" / "smoke_test_recursive_v1.py"
    result = _run_subprocess([sys.executable, str(smoke_script)])
    if result.returncode != 0:
        print("[WARN] 冒烟测试未完全通过，但继续执行（可能需要人工确认）")
    else:
        print("[OK] 冒烟测试通过")


def step_run_eval() -> dict:
    """Step 4: Run RAGAS evaluation via run_agent_eval.py."""
    print("\n" + "=" * 60)
    print("Step 4 — 执行 RAGAS 评测（direct + RAGAS）")
    print("=" * 60)

    frozen_ids = load_frozen_case_ids()
    case_id_args = []
    for cid in frozen_ids:
        case_id_args.extend(["--case-id", cid])

    cmd = [
        sys.executable, str(EVAL_SCRIPT),
        "--direct",
        "--deepeval",
        "--ragas",
        "--output", str(REPORT_JSON),
        "--markdown-output", str(REPORT_MD),
        "--dataset", str(DATASET),
    ] + case_id_args

    # Pass RAGAS credentials through env
    env_extra = {}
    for k in ["RAGAS_EVAL_API_KEY", "RAGAS_EVAL_MODEL", "RAGAS_EVAL_EMBEDDING_MODEL",
              "RAGAS_EVAL_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL",
              "DASH_SCOPE_API_KEY", "DASHSCOPE_MAAS_BASE_URL"]:
        if k in os.environ:
            env_extra[k] = os.environ[k]

    print(f"Running: python run_agent_eval --direct --deepeval --ragas ... ({len(frozen_ids)} cases)")
    started = time.time()
    result = _run_subprocess(cmd, env_extra=env_extra)
    elapsed = time.time() - started

    print(f"\n[eval] 评测进程返回码: {result.returncode}, 耗时: {elapsed:.0f}s")

    if result.stderr:
        stderr = result.stderr.decode("utf-8", errors="replace")
        print(f"[eval] stderr 前 800 字符:\n{stderr[:800]}")

    if result.returncode != 0:
        print("[ERROR] 评测进程异常")
        sys.exit(1)

    # Load the generated report
    if REPORT_JSON.exists():
        with open(REPORT_JSON, encoding="utf-8") as f:
            report = json.load(f)
        print(f"[OK] 报告已生成: {REPORT_JSON}")
    else:
        print("[ERROR] 报告文件未生成")
        sys.exit(1)

    return report


def build_comparison_table(recursive_report: dict) -> dict:
    """Step 5: Build cross-version comparison against v2.1 and v2.3."""
    print("\n" + "=" * 60)
    print("Step 5 — 横向指标对比")
    print("=" * 60)

    # Load v2.1 and v2.3 reports
    v21_path = AI_SERVICE_ROOT / "evals" / "reports" / "agent-v2.1-ragas.local.json"
    v23_path = AI_SERVICE_ROOT / "evals" / "reports" / "agent-v2.3-full.json"

    def load_report(path: Path) -> dict:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    v21 = load_report(v21_path)
    v23 = load_report(v23_path)

    def agg_ragas(report: dict) -> dict:
        """Aggregate RAGAS scores across knowledge cases in a report."""
        cases = report.get("cases", [])
        knowledge_cases = [c for c in cases if c.get("scenario") == "knowledge"]
        # Only cases with RAGAS scores
        ragas_cases = [
            c for c in knowledge_cases
            if c.get("ragas", {}).get("enabled") and c.get("ragas", {}).get("scores")
        ]
        if not ragas_cases:
            return {}
        metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
        result = {}
        for m in metrics:
            vals = [c["ragas"]["scores"].get(m) for c in ragas_cases if c["ragas"]["scores"].get(m) is not None]
            if vals:
                result[m] = {
                    "mean": round(sum(vals) / len(vals), 4),
                    "count": len(vals),
                    "min": round(min(vals), 4),
                    "max": round(max(vals), 4),
                }
        result["_n_ragas_cases"] = len(ragas_cases)
        result["_n_knowledge_cases"] = len(knowledge_cases)
        return result

    v21_ragas = agg_ragas(v21)
    v23_ragas = agg_ragas(v23)
    rv1_ragas = agg_ragas(recursive_report)

    # Latency
    def latency_summary(report: dict) -> dict:
        m = report.get("metrics", {}).get("latency_ms", {})
        return {"p50": m.get("p50"), "p95": m.get("p95"), "mean": m.get("mean"), "count": m.get("sample_count")}

    # Contract pass rate
    def contract_pass(report: dict, scenario: str = "knowledge") -> float | None:
        sb = report.get("metrics", {}).get("scenario_breakdown", {})
        if scenario in sb:
            return sb[scenario].get("contract_pass_rate")
        return None

    frozen_ids = set(load_frozen_case_ids())

    comparison = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "git_dirty": git_dirty(),
        "v2.1": {
            "milvus_collection": v21.get("metadata", {}).get("rag", {}).get("milvus_collection", "my_rag_collection"),
            "chunking": "fixed (CharacterTextSplitter, chunk_size=500, overlap=50)",
            "ragas": v21_ragas,
            "latency": latency_summary(v21),
            "contract_pass_rate_knowledge": contract_pass(v21, "knowledge"),
            "case_count": v21.get("metrics", {}).get("case_count"),
        },
        "v2.3": {
            "milvus_collection": v23.get("metadata", {}).get("rag", {}).get("milvus_collection", "knowledge_parent_child_v1"),
            "chunking": "parent-child (parent=1200/160, child=320/48, RAG_PARENT_CHILD_ENABLED=true)",
            "ragas": v23_ragas,
            "latency": latency_summary(v23),
            "contract_pass_rate_knowledge": contract_pass(v23, "knowledge"),
            "case_count": v23.get("metrics", {}).get("case_count"),
        },
        "recursive_v1": {
            "milvus_collection": COLLECTION,
            "chunking": "recursive (RecursiveCharacterTextSplitter, chunk_size=500, overlap=50)",
            "ragas": rv1_ragas,
            "latency": latency_summary(recursive_report),
            "contract_pass_rate_knowledge": contract_pass(recursive_report, "knowledge"),
            "case_count": recursive_report.get("metrics", {}).get("case_count"),
        },
        "frozen_case_ids": list(frozen_ids),
        "frozen_case_count": len(frozen_ids),
    }

    return comparison


def print_comparison_table(comparison: dict):
    """Pretty-print the cross-version comparison."""
    print()
    print("=" * 80)
    print("RAGAS 横向对比 (knowledge cases only)")
    print("=" * 80)

    metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    metric_labels = {
        "faithfulness": "Faithfulness",
        "answer_relevancy": "Answer Relevancy",
        "context_precision": "Context Precision",
        "context_recall": "Context Recall",
    }

    def fmt_ragas(entry: dict, m: str) -> str:
        if m not in entry:
            return "N/A"
        v = entry[m]
        if not v:
            return "N/A"
        return f"{v['mean']:.4f} (n={v['count']})"

    header = f"  {'Metric':<22} {'v2.1 (fixed)':<28} {'v2.3 (parent-child)':<28} {'recursive_v1':<28}"
    print(header)
    print("  " + "-" * 100)
    for m in metrics:
        v21 = fmt_ragas(comparison["v2.1"].get("ragas") or {}, m)
        v23 = fmt_ragas(comparison["v2.3"].get("ragas") or {}, m)
        rv1 = fmt_ragas(comparison["recursive_v1"].get("ragas") or {}, m)
        print(f"  {metric_labels[m]:<22} {v21:<28} {v23:<28} {rv1:<28}")

    print()
    print("=" * 80)
    print("其他指标")
    print("=" * 80)
    for label, version_key in [
        ("Contract Pass Rate (知识类)", "contract_pass_rate_knowledge"),
        ("Latency P50 (ms)", "latency"),
        ("Latency P95 (ms)", "latency"),
        ("Case Count", "case_count"),
    ]:
        v21_v = comparison["v2.1"].get(version_key, "N/A")
        v23_v = comparison["v2.3"].get(version_key, "N/A")
        rv1_v = comparison["recursive_v1"].get(version_key, "N/A")
        if isinstance(v21_v, dict):
            v21_v = v21_v.get("p50") or v21_v.get("mean") or "N/A"
        if isinstance(v23_v, dict):
            v23_v = v23_v.get("p50") or v23_v.get("mean") or "N/A"
        if isinstance(rv1_v, dict):
            rv1_v = rv1_v.get("p50") or rv1_v.get("mean") or "N/A"
        print(f"  {label:<35} v2.1={v21_v}  v2.3={v23_v}  recursive_v1={rv1_v}")

    print()
    print(f"Frozen case count: {comparison['frozen_case_count']}")
    print(f"Git commit: {comparison['git_commit']}")


def main():
    print("=" * 60)
    print("recursive_v1 RAG 分块实验")
    print(f"Collection : {COLLECTION}")
    print(f"Git commit : {git_commit()}")
    print(f"Git dirty  : {git_dirty()}")
    print("=" * 60)

    # Steps 1-4 need the experiment .env (MILVUS_COLLECTION=knowledge_recursive_v1, RAG_PARENT_CHILD_ENABLED=false)
    def run_experiment_steps():
        step_drop_collection()
        step_ingest()
        step_smoke_test()
        return step_run_eval()

    recursive_report = with_experiment_env(run_experiment_steps)

    # Step 5: comparison
    comparison = build_comparison_table(recursive_report)
    print_comparison_table(comparison)

    # Save comparison as sidecar
    cmp_path = REPORT_JSON.with_name("agent-recursive-v1-comparison.json")
    with open(cmp_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 对比数据已保存: {cmp_path}")

    print("\n✅ recursive_v1 实验完成")
    print(f"   报告: {REPORT_JSON}")
    print(f"   MD  : {REPORT_MD}")


if __name__ == "__main__":
    main()
