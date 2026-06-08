"""MAX setup helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from integrations.max.env_store import (
    format_env_lines,
    mask_token,
    merge_project_env,
    save_max_env,
    token_looks_valid,
)
from integrations.max.config import load_max_settings
from integrations.max.models import user_id_from_update


def _block_max_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("integrations.max.env_store.load_max_env_files", lambda: None)


def test_token_looks_valid() -> None:
    assert token_looks_valid("a" * 20)
    assert not token_looks_valid("short")
    assert not token_looks_valid("has space inside token")


def test_mask_token() -> None:
    masked = mask_token("abcdefghijklmnop")
    assert "abcd" in masked
    assert "mnop" in masked
    assert "ghij" not in masked


def test_save_max_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("integrations.max.env_store.HELIX_HOME", tmp_path)
    monkeypatch.setattr("integrations.max.env_store.MAX_ENV_PATH", tmp_path / "max.env")

    path = save_max_env(
        {
            "MAX_ACCESS_TOKEN": "x" * 24,
            "HELIX_MAX_ALLOWED_USERS": "42",
            "HELIX_MAX_PROFILE": "default",
            "HELIX_MAX_MODE": "polling",
        }
    )
    text = path.read_text(encoding="utf-8")
    assert "MAX_ACCESS_TOKEN=" in text
    assert "HELIX_MAX_ALLOWED_USERS=42" in text


def test_merge_project_env(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("FOO=bar\nMAX_ACCESS_TOKEN=old\n", encoding="utf-8")
    merge_project_env(
        env,
        {
            "MAX_ACCESS_TOKEN": "newtoken1234567890",
            "HELIX_MAX_ALLOWED_USERS": "99",
        },
    )
    text = env.read_text(encoding="utf-8")
    assert "FOO=bar" in text
    assert "MAX_ACCESS_TOKEN=newtoken1234567890" in text
    assert "old" not in text


def test_user_id_from_bot_started() -> None:
    uid = user_id_from_update({"update_type": "bot_started", "user": {"user_id": 555}})
    assert uid == 555


def test_poll_timeout_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_max_env(monkeypatch)
    monkeypatch.delenv("HELIX_MAX_POLL_TIMEOUT", raising=False)
    assert load_max_settings().poll_timeout_s == 5


def test_poll_timeout_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_max_env(monkeypatch)
    monkeypatch.setenv("HELIX_MAX_POLL_TIMEOUT", "15")
    assert load_max_settings().poll_timeout_s == 15


def test_poll_timeout_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_max_env(monkeypatch)
    monkeypatch.setenv("HELIX_MAX_POLL_TIMEOUT", "120")
    assert load_max_settings().poll_timeout_s == 90
    monkeypatch.setenv("HELIX_MAX_POLL_TIMEOUT", "not-a-number")
    assert load_max_settings().poll_timeout_s == 5


def test_format_env_lines() -> None:
    body = format_env_lines({"MAX_ACCESS_TOKEN": "t" * 20, "HELIX_MAX_PROFILE": "work"})
    assert "helix max setup" in body.lower() or "Helix MAX" in body