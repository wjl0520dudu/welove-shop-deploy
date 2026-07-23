"""Structural smoke checks for the fixed-size parent-child experiment."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.infrastructure.retrieval.fixed_parent_child import (  # noqa: E402
    CHILD_CHUNK_OVERLAP,
    CHILD_CHUNK_SIZE,
    PARENT_CHUNK_OVERLAP,
    PARENT_CHUNK_SIZE,
    build_fixed_parent_child_records,
)


def main() -> int:
    paragraph = "成分说明：烟酰胺可帮助改善肤色不均并调节油脂。"
    text = "\n\n".join(f"第{i}段。{paragraph * 12}" for i in range(1, 12))
    parents, children = build_fixed_parent_child_records(42, text, {"source": "smoke", "title": "smoke"})

    parent_ids = {item["parent_id"] for item in parents}
    if not parents or not children:
        print("FAIL: expected both parent and child records")
        return 1
    if any(child["parent_id"] not in parent_ids for child in children):
        print("FAIL: orphan child record found")
        return 1
    for parent in parents:
        indices = [child["child_index"] for child in children if child["parent_id"] == parent["parent_id"]]
        if indices != list(range(len(indices))):
            print(f"FAIL: non-contiguous child indexes for {parent['parent_id']}")
            return 1

    print("PASS: fixed_parent_child_v1 structural smoke test")
    print(f"parent={len(parents)} size/overlap={PARENT_CHUNK_SIZE}/{PARENT_CHUNK_OVERLAP}")
    print(f"child={len(children)} size/overlap={CHILD_CHUNK_SIZE}/{CHILD_CHUNK_OVERLAP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
