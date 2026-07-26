import pytest

from app.infrastructure.config import config
from scripts.ingest_mixed_fixed_parent_child_v1 import _validate_remote_target


def test_remote_target_requires_https_endpoint(monkeypatch):
    monkeypatch.setattr(config, "MILVUS_URL", "http://127.0.0.1:19530")
    monkeypatch.setattr(config, "MILVUS_TOKEN", "cloud-token")

    with pytest.raises(RuntimeError, match="Zilliz HTTPS endpoint"):
        _validate_remote_target(True)


def test_remote_target_requires_token(monkeypatch):
    monkeypatch.setattr(config, "MILVUS_URL", "https://example.api.gcp-us-west1.zillizcloud.com")
    monkeypatch.setattr(config, "MILVUS_TOKEN", "")

    with pytest.raises(RuntimeError, match="MILVUS_TOKEN"):
        _validate_remote_target(True)


def test_remote_target_accepts_https_endpoint_and_token(monkeypatch):
    monkeypatch.setattr(config, "MILVUS_URL", "https://example.api.gcp-us-west1.zillizcloud.com")
    monkeypatch.setattr(config, "MILVUS_TOKEN", "cloud-token")

    _validate_remote_target(True)
