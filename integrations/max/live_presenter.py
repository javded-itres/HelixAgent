"""Single MAX message updated via PUT /messages."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from integrations.max.markdown import split_max_text
from integrations.max.models import message_id_from_response
from integrations.max.render import buffer_to_max_text

if TYPE_CHECKING:
    from integrations.max.client import MaxClient
    from integrations.max.session import MaxChatSession


class MaxLivePresenter:
    def __init__(
        self,
        client: MaxClient,
        session: MaxChatSession,
        *,
        edit_interval_ms: int = 700,
    ) -> None:
        self._client = client
        self.session = session
        self._edit_interval = edit_interval_ms / 1000.0
        self._last_edit = 0.0
        self._edit_task: asyncio.Task | None = None
        self._buffer = session.live_buffer

    @property
    def buffer(self):
        return self.session.live_buffer

    async def start(self) -> None:
        self.session.bump_live_buffer()
        self._buffer = self.session.live_buffer
        text = buffer_to_max_text(self._buffer)
        payload = await self._client.send_message(
            text,
            user_id=self.session.reply_user_id,
            chat_id=self.session.reply_chat_id,
            fmt="markdown",
        )
        self.session.live_message_id = message_id_from_response(payload)

    def schedule_edit(self, *, force: bool = False) -> None:
        if self._edit_task and not self._edit_task.done():
            if not force:
                return
            self._edit_task.cancel()
        self._edit_task = asyncio.create_task(self._throttled_edit(force=force))

    async def _throttled_edit(self, *, force: bool = False) -> None:
        now = time.monotonic()
        wait = 0.0 if force else max(0.0, self._edit_interval - (now - self._last_edit))
        if wait:
            await asyncio.sleep(wait)
        await self._do_edit()
        self._last_edit = time.monotonic()

    async def _do_edit(self) -> None:
        if self.session.live_message_id is None or self._buffer is None:
            return
        text = buffer_to_max_text(self._buffer)
        try:
            await self._client.edit_message(
                self.session.live_message_id,
                text,
                fmt="markdown",
            )
        except Exception:
            payload = await self._client.send_message(
                text,
                user_id=self.session.reply_user_id,
                chat_id=self.session.reply_chat_id,
                fmt="markdown",
            )
            mid = message_id_from_response(payload)
            if mid:
                self.session.live_message_id = mid

    async def send_notice(self, text: str) -> None:
        await self._client.send_message(
            text,
            user_id=self.session.reply_user_id,
            chat_id=self.session.reply_chat_id,
            fmt="markdown",
        )

    async def send_final_answer_split(self, content: str) -> None:
        if not content or not content.strip():
            return
        for chunk in split_max_text(content):
            await self._client.send_message(
                chunk,
                user_id=self.session.reply_user_id,
                chat_id=self.session.reply_chat_id,
                fmt="markdown",
            )
            await asyncio.sleep(0.08)