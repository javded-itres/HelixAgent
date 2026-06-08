"""MAX bot help text and slash-command menu."""

from __future__ import annotations

from integrations.max.client import MaxClient
from integrations.telegram.commands import command_specs

MAX_COMMAND_LIMIT = 32
MAX_COMMAND_DESC_LEN = 256


def max_bot_commands(locale: str | None = None) -> list[dict[str, str]]:
    """Helix slash commands in MAX BotCommand format (name without /)."""
    return [
        {
            "name": spec.command,
            "description": spec.description[:MAX_COMMAND_DESC_LEN],
        }
        for spec in command_specs(locale)[:MAX_COMMAND_LIMIT]
    ]


async def register_bot_commands(
    client: MaxClient,
    *,
    locale: str | None = None,
) -> list[str]:
    """Register commands in MAX autocomplete menu (when user types /)."""
    commands = max_bot_commands(locale)
    await client.set_my_commands(commands)
    return [item["name"] for item in commands]


async def sync_bot_menu(profile: str = "default") -> list[str]:
    """Push command menu to MAX API without starting polling."""
    from core.i18n import LocaleStore
    from integrations.max.config import load_max_settings

    settings = load_max_settings(profile)
    token = settings.access_token.strip()
    if not token:
        raise RuntimeError("MAX_ACCESS_TOKEN is not set. Run: helix max setup")

    locale = LocaleStore(profile).get()
    async with MaxClient(token) as client:
        return await register_bot_commands(client, locale=locale)


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