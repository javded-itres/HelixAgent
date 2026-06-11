"""Tests for /api/helix/profiles/{id}/skills routes."""

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


def test_skills_list_and_assignments(
    helix_home: Path,
    gateway_client: TestClient,
    gateway_auth_headers: dict,
) -> None:
    from cli.core import ProfileManager

    ProfileManager().create_profile("skills-test")

    listed = gateway_client.get(
        "/api/helix/profiles/skills-test/skills",
        headers=gateway_auth_headers,
    )
    assert listed.status_code == 200
    assert "skills" in listed.json()

    seeded = gateway_client.post(
        "/api/helix/profiles/skills-test/skills/seed-bundled",
        headers=gateway_auth_headers,
    )
    assert seeded.status_code == 200

    patched = gateway_client.patch(
        "/api/helix/profiles/skills-test/skills/assignments",
        headers=gateway_auth_headers,
        json={"assignments": {"main": ["helix-cron"]}},
    )
    assert patched.status_code == 200
    assert patched.json()["reload_required"] is True

    assignments = gateway_client.get(
        "/api/helix/profiles/skills-test/skills/assignments",
        headers=gateway_auth_headers,
    )
    assert assignments.status_code == 200
    assert assignments.json()["assignments"]["main"] == ["helix-cron"]