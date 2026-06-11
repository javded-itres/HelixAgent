"""Shared FastAPI dependencies for /api/helix management routes."""

from __future__ import annotations

from fastapi import Depends, Header

from api.deps import verify_api_key
from api.services.profile_access import ProfileAccessContext, verify_profile_management


def profile_access(
    profile_id: str,
    key_info: dict,
    x_helix_profile: str | None,
    x_helix_profile_key: str | None,
) -> ProfileAccessContext:
    return verify_profile_management(
        profile_id,
        api_key_info=key_info,
        x_helix_profile=x_helix_profile,
        x_helix_profile_key=x_helix_profile_key,
    )


async def require_profile_access(
    profile_id: str,
    key_info: dict = Depends(verify_api_key),
    x_helix_profile: str | None = Header(None),
    x_helix_profile_key: str | None = Header(None, alias="X-Helix-Profile-Key"),
) -> ProfileAccessContext:
    return profile_access(profile_id, key_info, x_helix_profile, x_helix_profile_key)