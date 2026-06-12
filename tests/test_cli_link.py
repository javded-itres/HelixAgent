"""Holix Link CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from cli.core import ProfileManager
from cli.main import app
from core.gateway.links_store import LinksStore
from typer.testing import CliRunner


@pytest.fixture
def holix_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOLIX_HOME", str(tmp_path))
    monkeypatch.setenv("HOLIX_ENV", "development")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_link_create_and_list(holix_home: Path) -> None:
    ProfileManager().create_profile("support")
    runner = CliRunner()
    created = runner.invoke(app, ["link", "create", "--profile", "support", "--ttl", "10m"])
    assert created.exit_code == 0
    assert "LINK-" in created.stdout

    listed = runner.invoke(app, ["link", "list", "--profile", "support"])
    assert listed.exit_code == 0
    assert "No Holix Link connections" in listed.stdout


def test_link_revoke(holix_home: Path) -> None:
    ProfileManager().create_profile("support")
    store = LinksStore()
    pair = store.create_pair_code(profile="support", ttl_seconds=600)
    link = store.create_link(
        profile="support",
        folder_portable="/tmp/work",
        device_public_key_b64="cHVibGlj",
        permissions=__import__(
            "integrations.link.protocol", fromlist=["LinkPermissions"]
        ).LinkPermissions(),
    )
    store.mark_pair_code_used(pair.code)

    runner = CliRunner()
    result = runner.invoke(app, ["link", "revoke", link.link_id])
    assert result.exit_code == 0
    assert store.get_link(link.link_id).status == "revoked"