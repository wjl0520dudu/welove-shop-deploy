"""Read-only Milvus / Zilliz Cloud connectivity check.

Examples:
    # Local Milvus: MILVUS_URL=http://127.0.0.1:19530 and MILVUS_TOKEN=
    python scripts/check_milvus_connection.py

    # Zilliz Cloud: put the HTTPS endpoint and API token in .env first
    python scripts/check_milvus_connection.py --remote

The script never creates, changes, loads, or drops a collection.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymilvus import MilvusClient  # noqa: E402

from app.infrastructure.config import config  # noqa: E402


def client_from_config() -> MilvusClient:
    """Pass token only when it is configured, preserving local Milvus access."""
    kwargs: dict[str, str] = {"uri": config.MILVUS_URL}
    if config.MILVUS_TOKEN:
        kwargs["token"] = config.MILVUS_TOKEN
    return MilvusClient(**kwargs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Milvus / Zilliz Cloud connection check")
    parser.add_argument(
        "--remote",
        action="store_true",
        help="require an HTTPS endpoint and non-empty MILVUS_TOKEN before connecting",
    )
    args = parser.parse_args()

    if args.remote and not config.MILVUS_URL.startswith("https://"):
        raise SystemExit("[error] --remote requires MILVUS_URL to start with https://")
    if args.remote and not config.MILVUS_TOKEN:
        raise SystemExit("[error] --remote requires MILVUS_TOKEN in ai-service/.env")

    configured_collections = {
        "knowledge": config.MILVUS_COLLECTION,
        "product": config.MILVUS_PRODUCT_COLLECTION,
        "product_v2": config.MILVUS_PRODUCT_V2_COLLECTION,
    }
    print(f"[config] URI: {config.MILVUS_URL}")
    print(f"[config] token: {'configured' if config.MILVUS_TOKEN else 'empty'}")

    try:
        client = client_from_config()
        collections = sorted(client.list_collections())
    except Exception as exc:
        raise SystemExit(f"[error] Cannot connect or list collections: {exc}") from exc

    print(f"[ok] Connected. Found {len(collections)} collection(s):")
    for collection in collections:
        print(f"  - {collection}")

    print("[configured collections]")
    existing = set(collections)
    for role, collection in configured_collections.items():
        state = "exists" if collection in existing else "not found"
        print(f"  - {role}: {collection} ({state})")


if __name__ == "__main__":
    main()
