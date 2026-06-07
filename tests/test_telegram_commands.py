"""Telegram bot command menu."""

from integrations.telegram.commands import command_specs, help_message_html, telegram_menu_commands


def test_menu_has_help_and_status() -> None:
    names = {c for c, _ in telegram_menu_commands("en")}
    assert "help" in names
    assert "status" in names
    assert "models" in names
    assert "compress" in names
    assert "lang" in names
    assert len(command_specs("en")) == len(telegram_menu_commands("en"))


def test_help_html_lists_commands_en() -> None:
    html = help_message_html("en")
    assert "Helix" in html
    assert "<code>/help</code>" in html
    assert "<code>/memory</code>" in html
    assert "<code>/compress</code>" in html
    assert "<code>/lang</code>" in html


def test_help_html_lists_commands_ru() -> None:
    html = help_message_html("ru")
    assert "команд" in html.lower()
    assert "<code>/lang</code>" in html