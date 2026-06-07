"""Text chunking for MAX messages (max 4000 chars)."""

from __future__ import annotations

MAX_MESSAGE_LEN = 4000
SAFE_CHUNK_LEN = 3900


def truncate_max_text(text: str, *, limit: int = SAFE_CHUNK_LEN) -> str:
    raw = (text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 1] + "…"


def split_max_text(text: str, *, limit: int = SAFE_CHUNK_LEN) -> list[str]:
    raw = text or ""
    if not raw.strip():
        return []
    if len(raw) <= limit:
        return [raw]
    chunks: list[str] = []
    start = 0
    while start < len(raw):
        end = min(start + limit, len(raw))
        if end < len(raw):
            break_at = raw.rfind("\n\n", start, end)
            if break_at <= start:
                break_at = raw.rfind("\n", start, end)
            if break_at > start:
                end = break_at
        piece = raw[start:end].strip()
        if piece:
            chunks.append(piece)
        start = end if end > start else start + limit
    return chunks or [truncate_max_text(raw)]