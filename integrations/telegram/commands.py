"""Telegram bot command menu and routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.i18n import DEFAULT_LOCALE, LocaleStore, t

# (command without /, description key in messages catalog)
_TELEGRAM_COMMAND_KEYS: list[tuple[str, str]] = [
    ("help", "tg.cmd.help"),
    ("status", "tg.cmd.status"),
    ("models", "tg.cmd.models"),
    ("menu", "tg.cmd.menu"),
    ("mode", "tg.cmd.mode"),
    ("profile", "tg.cmd.profile"),
    ("stream", "tg.cmd.stream"),
    ("sessions", "tg.cmd.sessions"),
    ("switch", "tg.cmd.switch"),
    ("clear", "tg.cmd.clear"),
    ("stop", "tg.cmd.stop"),
    ("mcp", "tg.cmd.mcp"),
    ("new", "tg.cmd.new"),
    ("memory", "tg.cmd.memory"),
    ("skills", "tg.cmd.skills"),
    ("subagents", "tg.cmd.subagents"),
    ("tools", "tg.cmd.tools"),
    ("last", "tg.cmd.last"),
    ("metrics", "tg.cmd.metrics"),
    ("compress", "tg.cmd.compress"),
    ("init", "tg.cmd.init"),
    ("cron", "tg.cmd.cron"),
    ("lang", "tg.cmd.lang"),
    ("yes", "tg.cmd.yes"),
    ("no", "tg.cmd.no"),
]


@dataclass(frozen=True, slots=True)
class TelegramCommandSpec:
    command: str
    description: str
    slash: str

    @classmethod
    def from_pair(cls, command: str, description: str) -> TelegramCommandSpec:
        return cls(command=command, description=description, slash=f"/{command}")


def telegram_menu_commands(locale: str | None = None) -> list[tuple[str, str]]:
    loc = locale or DEFAULT_LOCALE
    return [(cmd, t(key, loc)) for cmd, key in _TELEGRAM_COMMAND_KEYS]


def command_specs(locale: str | None = None) -> list[TelegramCommandSpec]:
    return [
        TelegramCommandSpec.from_pair(cmd, desc)
        for cmd, desc in telegram_menu_commands(locale)
    ]


async def register_bot_commands(bot: Any, *, locale: str | None = None) -> list[str]:
    """Register commands in Telegram menu (side button + autocomplete)."""
    try:
        from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonCommands
    except ImportError:
        return []

    specs = command_specs(locale)
    commands = [
        BotCommand(command=spec.command, description=spec.description[:256])
        for spec in specs
    ]
    scope = BotCommandScopeDefault()
    try:
        await bot.delete_my_commands(scope=scope)
    except Exception:
        pass
    await bot.set_my_commands(commands, scope=scope)
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except Exception:
        pass
    return [spec.command for spec in specs]


async def sync_bot_menu(profile: str = "default") -> list[str]:
    """Push command menu to Telegram API (no polling)."""
    from integrations.telegram.config import load_telegram_settings

    settings = load_telegram_settings(profile)
    if not settings.bot_token:
        raise RuntimeError("Telegram bot token not configured")

    try:
        from aiogram import Bot
    except ImportError as e:
        raise ImportError("uv sync --extra telegram") from e

    locale = LocaleStore(profile).get()
    bot = Bot(token=settings.bot_token)
    try:
        return await register_bot_commands(bot, locale=locale)
    finally:
        await bot.session.close()


def help_message_html(locale: str | None = None) -> str:
    """HTML help for /help and /start."""
    loc = locale or DEFAULT_LOCALE
    lines = [
        f"<b>{escape_html_simple(t('tg.help.title', loc))}</b>",
        "",
        f"<b>{escape_html_simple(t('tg.help.chat', loc))}</b>",
        escape_html_simple(t("tg.help.chat_body", loc)),
        "",
        f"<b>{escape_html_simple(t('tg.help.commands', loc))}</b>",
    ]
    for spec in command_specs(loc):
        lines.append(
            f"• <code>/{spec.command}</code> — {escape_html_simple(spec.description)}"
        )
    lines.extend(
        [
            "",
            f"<b>{escape_html_simple(t('tg.help.buttons', loc))}</b>",
            escape_html_simple(t("tg.help.buttons_body", loc)),
            "",
            f"<b>{escape_html_simple(t('tg.help.extra', loc))}</b>",
            escape_html_simple(t("tg.help.extra_body", loc)),
        ]
    )
    return "\n".join(lines)


def escape_html_simple(text: str) -> str:
    from integrations.telegram.markdown import escape_html

    return escape_html(text)