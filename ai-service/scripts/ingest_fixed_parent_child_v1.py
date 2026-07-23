"""Ingest the fixed-size parent-child experiment into an isolated collection.

Run this script only with:
  MILVUS_COLLECTION=knowledge_fixed_parent_child_v1
  RAG_PARENT_CHILD_ENABLED=true
  RAG_PARENT_CHILD_CHUNKING=fixed_v1
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.infrastructure.config import config  # noqa: E402


def main() -> None:
    if not config.RAG_PARENT_CHILD_ENABLED:
        raise SystemExit("RAG_PARENT_CHILD_ENABLED must be true for fixed_parent_child_v1")
    if config.RAG_PARENT_CHILD_CHUNKING != "fixed_v1":
        raise SystemExit("RAG_PARENT_CHILD_CHUNKING must be fixed_v1 for this script")
    if config.MILVUS_COLLECTION != "knowledge_fixed_parent_child_v1":
        raise SystemExit(
            "refusing to ingest fixed_parent_child_v1 into a non-isolated collection: "
            f"{config.MILVUS_COLLECTION}"
        )

    # The source iteration and upsert behavior are intentionally shared with
    # the existing v2.3 reindex script.  The pipeline dispatches to the new,
    # versioned fixed parent-child builder through the experiment flag above.
    from scripts.reindex_knowledge_parent_child import main as reindex_main
    reindex_main()


if __name__ == "__main__":
    main()
