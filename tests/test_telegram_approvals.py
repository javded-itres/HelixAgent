"""Telegram confirmation / plan-review UI cleanup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.security.confirmation_events import ConfirmationRequestEvent
from integrations.telegram.approvals import TelegramApprovals, _format_confirmation_args
from integrations.telegram.session import ChatSession


@pytest.fixture
def session() -> ChatSession:
    return ChatSession(
        chat_id=100,
        user_id=1,
        profile="default",
        conversation_id="tg_default_100",
    )


@pytest.fixture
def approvals(session: ChatSession) -> TelegramApprovals:
    bot = AsyncMock()
    return TelegramApprovals(bot, session)


@pytest.mark.asyncio
async def test_dismiss_confirmation_deletes_stored_message(
    approvals: TelegramApprovals, session: ChatSession
) -> None:
    session.pending_confirmation_message_id = 42
    await approvals.dismiss_confirmation_ui()
    approvals._bot.delete_message.assert_awaited_once_with(100, 42)
    assert session.pending_confirmation_message_id is None


@pytest.mark.asyncio
async def test_dismiss_plan_review_deletes_all_stored_messages(
    approvals: TelegramApprovals, session: ChatSession
) -> None:
    session.pending_plan_message_ids = [10, 11]
    await approvals.dismiss_plan_review_ui()
    assert approvals._bot.delete_message.await_count == 2
    approvals._bot.delete_message.assert_any_await(100, 10)
    approvals._bot.delete_message.assert_any_await(100, 11)
    assert session.pending_plan_message_ids == []


@pytest.mark.asyncio
async def test_dismiss_confirmation_ignores_delete_errors(
    approvals: TelegramApprovals, session: ChatSession
) -> None:
    session.pending_confirmation_message_id = 99
    approvals._bot.delete_message.side_effect = Exception("already gone")
    await approvals.dismiss_confirmation_ui()
    assert session.pending_confirmation_message_id is None


def test_format_confirmation_args_terminal_shows_command() -> None:
    html = _format_confirmation_args(
        "run_terminal_command",
        {"command": "rm -rf /tmp/test"},
    )
    assert "Команда:" in html
    assert "rm -rf" in html


def test_format_confirmation_args_write_file_shows_path() -> None:
    html = _format_confirmation_args(
        "write_file",
        {"path": "/etc/hosts", "content": "hello"},
    )
    assert "/etc/hosts" in html


@pytest.mark.asyncio
async def test_on_confirmation_request_includes_command_and_keyboard(
    approvals: TelegramApprovals,
) -> None:
    event = ConfirmationRequestEvent(
        confirmation_id="abc",
        tool_name="run_terminal_command",
        arguments={"command": "ls -la"},
        risk_level="high",
        reason="Dangerous command",
    )
    sent = MagicMock()
    sent.message_id = 7
    approvals._bot.send_message = AsyncMock(return_value=sent)

    await approvals.on_confirmation_request(event)

    call = approvals._bot.send_message.await_args
    assert call is not None
    text = call.args[1] if len(call.args) > 1 else call.kwargs.get("text", "")
    assert "ls -la" in text
    assert call.kwargs.get("reply_markup") is not None
    assert approvals._session.pending_confirmation_message_id == 7