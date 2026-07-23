"""Run RAGAS evaluation only against the prepared experiment collection.

It never drops a collection and never ingests documents.  Run
``prepare_fixed_parent_child_v1_index.py`` first.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from dotenv import dotenv_values


AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = AI_SERVICE_ROOT / ".env"
COLLECTION = "knowledge_fixed_parent_child_v1"
FROZEN_CASES = AI_SERVICE_ROOT / "evals" / "datasets" / "fixed_parent_child_v1_frozen_cases.json"
REPORT_JSON = AI_SERVICE_ROOT / "evals" / "reports" / "agent-fixed-parent-child-v1.json"
REPORT_MD = AI_SERVICE_ROOT / "evals" / "reports" / "agent-fixed-parent-child-v1.md"
DATASET = AI_SERVICE_ROOT / "evals" / "datasets" / "agent_golden_cases.jsonl"


@contextmanager
def experiment_env() -> Iterator[None]:
    original_text = ENV_FILE.read_text(encoding="utf-8")
    values = {key: value for key, value in dotenv_values(ENV_FILE).items() if value is not None}
    values.update({
        "MILVUS_COLLECTION": COLLECTION,
        "RAG_PARENT_CHILD_ENABLED": "true",
        "RAG_PARENT_CHILD_CHUNKING": "fixed_v1",
    })
    ENV_FILE.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")
    try:
        yield
    finally:
        ENV_FILE.write_text(original_text, encoding="utf-8")


def check_collection_exists() -> None:
    # Import after the temporary .env is in place because config.py loads it at
    # import time with override=True.
    sys.path.insert(0, str(AI_SERVICE_ROOT))
    from app.infrastructure.config import config
    from pymilvus import MilvusClient

    client = MilvusClient(uri=config.MILVUS_URL)
    if not client.has_collection(COLLECTION):
        raise SystemExit(
            f"experiment collection does not exist: {COLLECTION}. "
            "Run scripts/prepare_fixed_parent_child_v1_index.py first."
        )


def main() -> None:
    case_ids = json.loads(FROZEN_CASES.read_text(encoding="utf-8"))
    case_args = [item for case_id in case_ids for item in ("--case-id", case_id)]
    with experiment_env():
        check_collection_exists()
        env = os.environ.copy()
        env.update({
            "MILVUS_COLLECTION": COLLECTION,
            "RAG_PARENT_CHILD_ENABLED": "true",
            "RAG_PARENT_CHILD_CHUNKING": "fixed_v1",
        })
        completed = subprocess.run([
            sys.executable, "-m", "evals.run_agent_eval", "--direct", "--ragas",
            "--dataset", str(DATASET), "--output", str(REPORT_JSON), "--markdown-output", str(REPORT_MD),
            *case_args,
        ], cwd=AI_SERVICE_ROOT, env=env)
        if completed.returncode:
            raise SystemExit(f"RAGAS evaluation failed with exit code {completed.returncode}")
    # Fail early if the evaluator produced a truncated/invalid JSON artifact.
    json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    print(f"JSON report: {REPORT_JSON}")
    print(f"Markdown report: {REPORT_MD}")


if __name__ == "__main__":
    main()
