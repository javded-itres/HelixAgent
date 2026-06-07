"""Render LiveTranscriptBuffer for MAX markdown messages."""

from __future__ import annotations

from core.presenters.live_buffer import LiveTranscriptBuffer
from integrations.max.markdown import truncate_max_text


def buffer_to_max_text(buf: LiveTranscriptBuffer) -> str:
    answer = (buf.answer or "").strip()
    running = buf.status == "running"
    done = buf.status == "done"
    show_tools = bool(buf.tool_lines) and not done

    if done and answer and not show_tools and not buf.thinking and not buf.notes:
        footer = f"\n\n_🤖 {buf.profile} · {buf.mode} · ✓_"
        return truncate_max_text(f"{answer}{footer}")

    parts: list[str] = [
        f"**🤖 Helix** · {buf.profile} · {buf.mode} · {buf.session_label}",
    ]
    if buf.thinking:
        parts.append(f"_💭 {buf.thinking}_")
    if show_tools:
        parts.extend(buf.tool_lines[:12])
    if answer:
        parts.append(answer)
    for note in buf.notes[-3:]:
        if running or not done:
            parts.append(f"· {note}")
    if running and not answer and not buf.tool_lines:
        parts.append("_⏳ Working…_")
    elif done and answer:
        parts.append(f"_🤖 {buf.profile} · {buf.mode} · ✓_")
    elif buf.status == "error":
        parts.append("**✗ Error**")

    return truncate_max_text("\n\n".join(parts))