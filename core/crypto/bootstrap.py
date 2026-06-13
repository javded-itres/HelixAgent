"""Enable profile encryption and migrate existing workspace files."""

from __future__ import annotations

from pathlib import Path

from core.crypto.encrypted_fs import encrypt_bytes, is_encrypted_file
from core.crypto.profile_crypto import (
    ProfileCryptoError,
    create_profile_crypto,
    is_profile_encryption_enabled,
    unlock_profile_dek,
)
from core.crypto.unlock_context import set_profile_session_unlock
from core.workspace.limits import ensure_profile_limits
from core.workspace.quota import QUOTA_DIRNAME, reconcile_workspace_usage


def encrypt_workspace_tree(workspace_root: Path, dek: bytes) -> int:
    """Encrypt plaintext files under workspace; return count of files encrypted."""
    root = workspace_root.resolve()
    if not root.is_dir():
        return 0

    count = 0
    for item in root.rglob("*"):
        if not item.is_file():
            continue
        try:
            rel = item.relative_to(root)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] == QUOTA_DIRNAME:
            continue
        if is_encrypted_file(item):
            continue
        plaintext = item.read_bytes()
        item.write_bytes(encrypt_bytes(dek, plaintext))
        count += 1
    return count


def enable_profile_encryption(
    manager,
    profile: str,
    user_encryption_key: str,
    *,
    encrypt_existing: bool = True,
) -> Path:
    """Enable workspace encryption for a profile (workspace jail + crypto.json)."""
    from cli.core import enable_profile_workspace_isolation

    if is_profile_encryption_enabled(profile):
        raise ProfileCryptoError(f"Profile '{profile}' already has encryption enabled")

    workspace = enable_profile_workspace_isolation(manager, profile)
    ensure_profile_limits(profile)
    create_profile_crypto(profile, user_encryption_key)
    dek = unlock_profile_dek(profile, user_encryption_key)

    if encrypt_existing:
        encrypt_workspace_tree(workspace, dek)
    reconcile_workspace_usage(workspace)

    config = manager.load_profile(profile)
    config.encryption_enabled = True
    manager.save_profile(profile, config)
    set_profile_session_unlock(profile, dek)
    return workspace