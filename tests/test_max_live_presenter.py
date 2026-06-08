"""MAX live presenter delivery guarantees."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from integrations.max.live_presenter import MaxLivePresenter
from integrations.max.session import MaxChatSession


@pytest.mark.asyncio
async def test_deliver_final_answer_only_once() -> None:
    client = MagicMock()
    client.send_message = AsyncMock(return_value={"message": {"body": {"mid": "m1"}}})
    session = MaxChatSession(user_id=1, profile="default", conversation_id="max_default_1")
    presenter = MaxLivePresenter(client, session)

    await presenter.deliver_final_answer("**hello** world")
    await presenter.deliver_final_answer("**hello** world")

    assert client.send_message.await_count == 1
    assert client.send_message.await_args_list[0].kwargs.get("fmt") == "html"
    sent = client.send_message.await_args_list[0].args[0]
    assert "<b>hello</b>" in sent
    assert "**hello**" not in sent


@pytest.mark.asyncio
async def test_finish_delivers_full_content_not_preview_placeholder() -> None:
    client = MagicMock()
    client.edit_message = AsyncMock()
    client.send_message = AsyncMock(return_value={"message": {"body": {"mid": "m1"}}})
    session = MaxChatSession(user_id=1, profile="default", conversation_id="max_default_1")
    session.bump_live_buffer()
    session.live_message_id = "live-1"
    session.live_buffer.set_answer("✓ Done — full answer below.")
    session.live_buffer.mark_done()

    presenter = MaxLivePresenter(client, session, heartbeat_interval_s=60)
    presenter.note_final_content("This is the real final answer from the agent.")
    await presenter.finish()

    assert client.send_message.await_count == 1
    sent = client.send_message.await_args_list[0].args[0]
    assert "real final answer" in sent
    assert client.send_message.await_args_list[0].kwargs.get("fmt") == "html"


@pytest.mark.asyncio
async def test_deliver_final_answer_not_marked_when_all_sends_fail() -> None:
    client = MagicMock()
    client.send_message = AsyncMock(side_effect=Exception("api down"))
    session = MaxChatSession(user_id=1, profile="default", conversation_id="max_default_1")
    presenter = MaxLivePresenter(client, session)

    await presenter.deliver_final_answer("**hello** world")

    assert presenter.final_delivered is False


@pytest.mark.asyncio
async def test_finish_skips_placeholder_when_no_final_content() -> None:
    client = MagicMock()
    client.edit_message = AsyncMock()
    client.send_message = AsyncMock()
    session = MaxChatSession(user_id=1, profile="default", conversation_id="max_default_1")
    session.bump_live_buffer()
    session.live_message_id = "live-1"
    session.live_buffer.set_answer("✓ Done — full answer below.")
    session.live_buffer.mark_done()

    presenter = MaxLivePresenter(client, session, heartbeat_interval_s=60)
    await presenter.finish()

    client.send_message.assert_not_awaited()