"""Human-readable sub-agent tool output for MAX chat."""

from __future__ import annotations

import json


def format_list_subagents_result(raw: str) -> str:
    """Turn list_subagents JSON into a short MAX-friendly message."""
    text = (raw or "").strip()
    if not text:
        return "Субагенты: нет данных."

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text

    if not isinstance(data, dict):
        return text

    total = int(data.get("total") or 0)
    running = int(data.get("running") or 0)
    agents = data.get("agents") or []

    if total == 0:
        return (
            "**Субагенты:** сейчас нет запущенных задач.\n\n"
            "Запуск вручную: `/subagent-spawn researcher <задача>`\n"
            "Или напишите агенту: «делегируй researcher: …»"
        )

    lines = [f"**Субагенты:** {total} (в работе: {running})"]
    for item in agents[:12]:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or "?"
        status = item.get("status") or "?"
        preview = (item.get("task_preview") or item.get("agent_type") or "")[:80]
        line = f"• `{name}` — {status}"
        if preview:
            line += f" — {preview}"
        lines.append(line)
    return "\n".join(lines)