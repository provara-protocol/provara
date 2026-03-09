from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _load_saas_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **env: str):
    keys = {
        "PROVARA_ENV",
        "PROVARA_API_KEY",
        "PROVARA_ALLOWED_ORIGINS",
        "PROVARA_ALLOWED_HOSTS",
        "PROVARA_VAULT_ROOT",
    }
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("PROVARA_VAULT_ROOT", str(tmp_path / "vaults"))

    module_name = "provara.saas.main"
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


def test_production_requires_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="PROVARA_API_KEY must be set"):
        _load_saas_main(monkeypatch, tmp_path, PROVARA_ENV="production")


def test_production_rejects_wildcard_cors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="Wildcard CORS"):
        _load_saas_main(
            monkeypatch,
            tmp_path,
            PROVARA_ENV="production",
            PROVARA_API_KEY="test-key",
            PROVARA_ALLOWED_ORIGINS="*",
            PROVARA_ALLOWED_HOSTS="api.provara.test",
        )


def test_managed_create_append_verify_flow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    saas_main = _load_saas_main(
        monkeypatch,
        tmp_path,
        PROVARA_ENV="development",
        PROVARA_API_KEY="test-key",
        PROVARA_ALLOWED_ORIGINS="http://localhost:5173",
        PROVARA_ALLOWED_HOSTS="testserver",
    )
    client = TestClient(saas_main.app)
    headers = {"x-api-key": "test-key"}

    create_resp = client.post(
        "/api/v1/vaults/create",
        headers=headers,
        json={"name": "integration_tester", "description": "test"},
    )
    assert create_resp.status_code == 201
    vault_id = create_resp.json()["vault_id"]

    append_resp = client.post(
        f"/api/v1/vaults/{vault_id}/events",
        headers=headers,
        json={
            "type": "OBSERVATION",
            "subject": "system",
            "predicate": "status",
            "value": {"ok": True},
            "confidence": 0.9,
            "namespace": "managed",
        },
    )
    assert append_resp.status_code == 200
    append_data = append_resp.json()
    assert append_data["success"] is True
    assert str(append_data["event_id"]).startswith("evt_")

    verify_resp = client.get(f"/api/v1/vaults/{vault_id}/verify", headers=headers)
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["success"] is True
    assert verify_data["status"] == "valid"
    assert verify_data["event_count"] >= 3
