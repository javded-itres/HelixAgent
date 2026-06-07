"""MAX bot configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass
class MaxSettings:
    access_token: str
    allowed_user_ids: str = ""
    profile: str = "default"
    mode: str = "polling"
    webhook_url: str = ""
    webhook_secret: str = ""
    allow_all: bool = False

    def allowed_ids(self) -> set[int]:
        out: set[int] = set()
        for part in self.allowed_user_ids.replace(" ", "").split(","):
            if part.isdigit():
                out.add(int(part))
        return out

    def is_user_allowed(self, user_id: int) -> bool:
        if self.allow_all:
            return True
        allowed = self.allowed_ids()
        return bool(allowed) and user_id in allowed

    @property
    def is_webhook_mode(self) -> bool:
        return self.mode.strip().lower() == "webhook"


def max_files_extra_available() -> bool:
    """True when optional PDF extraction (pypdf) from the `max` extra is installed."""
    try:
        import pypdf  # noqa: F401

        return True
    except ImportError:
        return False


def load_max_settings(profile: str = "default") -> MaxSettings:
    from integrations.max.env_store import load_max_env_files

    load_max_env_files()
    mode = os.getenv("HELIX_MAX_MODE", "polling").strip().lower()
    if os.getenv("HELIX_ENV", "").strip().lower() == "production" and mode not in {"webhook"}:
        mode = "webhook"
    return MaxSettings(
        access_token=os.getenv("MAX_ACCESS_TOKEN", os.getenv("HELIX_MAX_ACCESS_TOKEN", "")),
        allowed_user_ids=os.getenv("HELIX_MAX_ALLOWED_USERS", ""),
        profile=os.getenv("HELIX_MAX_PROFILE", profile),
        mode=mode,
        webhook_url=os.getenv("HELIX_MAX_WEBHOOK_URL", ""),
        webhook_secret=os.getenv("HELIX_MAX_WEBHOOK_SECRET", ""),
        allow_all=_env_bool("HELIX_MAX_ALLOW_ALL"),
    )