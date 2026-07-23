"""Create and ingest only the fixed_parent_child_v1 Milvus collection.

This script deliberately does not run any evaluation.  It is safe to run
before the separate RAGAS script because it can delete only the experiment
collection, never a legacy collection.
"""
from __future__ import annotations

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


@contextmanager
def experiment_env() -> Iterator[None]:
    """Temporarily make config.py select the new, isolated experiment index."""
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


def run(command: list[str]) -> None:
    env = os.environ.copy()
    env.update({
        "MILVUS_COLLECTION": COLLECTION,
        "RAG_PARENT_CHILD_ENABLED": "true",
        "RAG_PARENT_CHILD_CHUNKING": "fixed_v1",
    })
    completed = subprocess.run(command, cwd=AI_SERVICE_ROOT, env=env)
    if completed.returncode:
        raise SystemExit(f"command failed ({completed.returncode}): {' '.join(command)}")


def main() -> None:
    with experiment_env():
        run([sys.executable, "scripts/drop_milvus_collection.py", "--collection", COLLECTION, "--yes"])
        run([sys.executable, "scripts/ingest_fixed_parent_child_v1.py", "--source", "all", "--replace"])
        run([sys.executable, "scripts/smoke_test_fixed_parent_child_v1.py"])
    print(f"fixed_parent_child_v1 index is ready: {COLLECTION}")


if __name__ == "__main__":
    main()
