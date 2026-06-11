"""Tests for /api/helix/profiles/{id}/mcp routes."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def helix_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HELIX_HOME", str(tmp_path))
    monkeypatch.setenv("HELIX_ENV", "development")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_mcp_servers_crud(
    helix_home: Path,
    gateway_client: TestClient,
    gateway_auth_headers: dict,
) -> None:
    from cli.core import ProfileManager

    ProfileManager().create_profile("mcp-test")

    popular = gateway_client.get(
        "/api/helix/profiles/mcp-test/mcp/popular",
        headers=gateway_auth_headers,
    )
    assert popular.status_code == 200
    assert popular.json()["count"] > 0

    created = gateway_client.post(
        "/api/helix/profiles/mcp-test/mcp/servers",
        headers=gateway_auth_headers,
        json={
            "name": "demo",
            "transport": "stdio",
            "command": "echo",
            "args": ["hello"],
        },
    )
    assert created.status_code == 200
    assert created.json()["reload_required"] is True

    listed = gateway_client.get(
        "/api/helix/profiles/mcp-test/mcp/servers",
        headers=gateway_auth_headers,
    )
    assert listed.status_code == 200
    assert "demo" in listed.json()["servers"]

    patched = gateway_client.patch(
        "/api/helix/profiles/mcp-test/mcp/assignments",
        headers=gateway_auth_headers,
        json={"assignments": {"main": ["demo"]}},
    )
    assert patched.status_code == 200

    deleted = gateway_client.delete(
        "/api/helix/profiles/mcp-test/mcp/servers/demo",
        headers=gateway_auth_headers,
    )
    assert deleted.status_code == 200