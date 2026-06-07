"""MAX bot help text."""

from __future__ import annotations

from integrations.telegram.commands import command_specs


def help_message_markdown(locale: str | None = None) -> str:
    lines = [
        "**Helix в MAX**",
        "",
        "Пишите задачи обычным текстом — агент использует инструменты, память и навыки.",
        "",
        "**Слэш-команды:**",
    ]
    for spec in command_specs(locale):
        lines.append(f"• `{spec.slash}` — {spec.description}")
    lines.extend(
        [
            "",
            "`ping` — проверка связи",
            "`/stop` — остановить текущий запуск",
        ]
    )
    return "\n".join(lines)