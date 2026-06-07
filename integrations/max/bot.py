"""MAX bot event dispatcher."""

from __future__ import annotations

import logging
from typing import Any

from integrations.max.agent_setup import create_agent
from integrations.max.client import MaxClient
from integrations.max.commands import help_message_markdown
from integrations.max.config import MaxSettings, load_max_settings
from integrations.max.host import MaxHost
from integrations.max.approvals import MaxApprovals
from integrations.max.interactive import dispatch_callback
from integrations.max.file_handler import (
    PendingMaxAttachment,
    build_agent_prompt,
    extract_media_attachments,
    format_files_preview_markdown,
    save_max_attachment,
)
from integrations.max.models import (
    callback_id_from_update,
    callback_payload_from_update,
    callback_reply_target,
    message_from_update,
    message_has_media,
    message_text,
    recipient_target,
    sender_user_id,
    update_type,
    user_id_from_update,
)
from integrations.telegram.file_handler import SavedTelegramFile
from integrations.max.session import MaxChatSession

logger = logging.getLogger(__name__)


def _session_key(user_id: int, chat_id: int | None) -> tuple[int, int]:
    return (chat_id or 0, user_id)


def _conversation_id(profile: str, user_id: int, chat_id: int | None) -> str:
    if chat_id:
        return f"max_{profile}_chat_{chat_id}"
    return f"max_{profile}_{user_id}"


class HelixMaxBot:
    def __init__(self, settings: MaxSettings | None = None, *, profile: str = "default") -> None:
        self.settings = settings or load_max_settings(profile)
        self._sessions: dict[tuple[int, int], MaxChatSession] = {}
        self._agent = None

    def _allowed(self, user_id: int) -> bool:
        return self.settings.is_user_allowed(user_id)

    async def _get_session(
        self,
        user_id: int,
        *,
        reply_user_id: int | None,
        reply_chat_id: int | None,
    ) -> MaxChatSession:
        key = _session_key(user_id, reply_chat_id)
        if key not in self._sessions:
            conv = _conversation_id(self.settings.profile, user_id, reply_chat_id)
            self._sessions[key] = MaxChatSession(
                user_id=user_id,
                profile=self.settings.profile,
                conversation_id=conv,
                reply_user_id=reply_user_id,
                reply_chat_id=reply_chat_id,
            )
        session = self._sessions[key]
        session.reply_user_id = reply_user_id
        session.reply_chat_id = reply_chat_id
        if session.agent is None:
            if self._agent is None:
                self._agent = await create_agent(self.settings.profile)
            session.agent = self._agent
        return session

    async def handle_update(self, client: MaxClient, update: dict[str, Any]) -> None:
        kind = update_type(update)
        if kind == "bot_started":
            await self._handle_bot_started(client, update)
            return
        if kind == "message_created":
            await self._handle_message_created(client, update)
            return
        if kind == "message_callback":
            await self._handle_message_callback(client, update)
            return
        logger.debug("Ignored MAX update: %s", kind)

    async def _handle_bot_started(self, client: MaxClient, update: dict[str, Any]) -> None:
        uid = user_id_from_update(update)
        if uid is None:
            return
        if not self._allowed(uid):
            logger.info("MAX bot_started from disallowed user %s", uid)
            return
        await client.send_message(
            help_message_markdown(),
            user_id=uid,
            fmt="markdown",
        )

    async def _handle_message_created(self, client: MaxClient, update: dict[str, Any]) -> None:
        msg = message_from_update(update)
        if msg is None:
            return
        uid = sender_user_id(msg)
        if uid is None:
            return
        if not self._allowed(uid):
            logger.info("MAX message from disallowed user %s", uid)
            return
        text = message_text(msg).strip()
        reply_user_id, reply_chat_id = recipient_target(msg)
        if reply_user_id is None and reply_chat_id is None:
            reply_user_id = uid

        if message_has_media(msg):
            await self._handle_message_media(
                client,
                uid,
                reply_user_id=reply_user_id,
                reply_chat_id=reply_chat_id,
                caption=text,
                message=msg,
            )
            return

        if not text:
            return

        if text.lower() == "ping":
            await client.send_message("pong", user_id=reply_user_id, chat_id=reply_chat_id)
            return

        session = await self._get_session(
            uid,
            reply_user_id=reply_user_id,
            reply_chat_id=reply_chat_id,
        )
        host = MaxHost(client, session)
        async with session.run_lock:
            await host.handle_user_text(text)

    async def _handle_message_media(
        self,
        client: MaxClient,
        user_id: int,
        *,
        reply_user_id: int | None,
        reply_chat_id: int | None,
        caption: str,
        message: dict,
    ) -> None:
        from config import settings

        if not settings.max_files_enabled:
            await client.send_message(
                "📎 Приём файлов отключён. Установите HELIX_MAX_FILES_ENABLED=true.",
                user_id=reply_user_id,
                chat_id=reply_chat_id,
            )
            return

        attachments = extract_media_attachments(message)
        if not attachments:
            return

        session = await self._get_session(
            user_id,
            reply_user_id=reply_user_id,
            reply_chat_id=reply_chat_id,
        )
        host = MaxHost(client, session)
        saved, errors = await self._save_attachments(
            client,
            attachments,
            profile=self.settings.profile,
            storage_id=reply_chat_id or user_id,
        )

        if not saved and errors:
            await client.send_message(
                f"📎 **Файлы**\n\n❌ {'; '.join(errors)}",
                user_id=reply_user_id,
                chat_id=reply_chat_id,
                fmt="markdown",
            )
            return

        preview = format_files_preview_markdown(saved, errors=errors)
        if caption:
            await client.send_message(
                preview,
                user_id=reply_user_id,
                chat_id=reply_chat_id,
                fmt="markdown",
            )
            prompt = build_agent_prompt(caption, saved)
            async with session.run_lock:
                await host.handle_user_text(prompt)
            return

        session.pending_files.extend(saved)
        count = len(saved)
        await client.send_message(
            preview
            + f"\n\nСохранено файлов: {count}. Напишите задачу "
            "(можно добавить ещё файлы, затем одно сообщение с инструкцией).",
            user_id=reply_user_id,
            chat_id=reply_chat_id,
            fmt="markdown",
        )

    async def _save_attachments(
        self,
        client: MaxClient,
        items: list[PendingMaxAttachment],
        *,
        profile: str,
        storage_id: int,
    ) -> tuple[list[SavedTelegramFile], list[str]]:
        saved: list[SavedTelegramFile] = []
        errors: list[str] = []
        for item in items:
            try:
                saved.append(
                    await save_max_attachment(
                        client,
                        item,
                        profile=profile,
                        storage_id=storage_id,
                    )
                )
            except Exception as exc:
                errors.append(f"{item.file_name}: {exc}")
        return saved, errors

    async def _handle_message_callback(self, client: MaxClient, update: dict[str, Any]) -> None:
        uid = user_id_from_update(update)
        if uid is None:
            return
        if not self._allowed(uid):
            logger.info("MAX callback from disallowed user %s", uid)
            return

        callback_id = callback_id_from_update(update)
        payload = callback_payload_from_update(update)
        if not callback_id or not payload:
            return

        reply_user_id, reply_chat_id = callback_reply_target(update)
        if reply_user_id is None and reply_chat_id is None:
            reply_user_id = uid

        session = await self._get_session(
            uid,
            reply_user_id=reply_user_id,
            reply_chat_id=reply_chat_id,
        )
        host = MaxHost(client, session)
        approvals = MaxApprovals(client, session)
        notification = ""

        async with session.run_lock:
            if payload.startswith("cfm:"):
                parts = payload.split(":", 2)
                if len(parts) == 3 and approvals.resolve_confirmation_callback(parts[1], parts[2]):
                    await approvals.dismiss_confirmation_ui()
                    notification = "✓"
                else:
                    notification = "?"
            elif payload.startswith("plan:"):
                parts = payload.split(":", 2)
                if len(parts) == 3 and approvals.resolve_plan_callback(parts[1], parts[2]):
                    await approvals.dismiss_plan_review_ui()
                    notification = "✓"
                else:
                    notification = "?"
            else:
                notification = await dispatch_callback(host, payload) or "OK"

        try:
            await client.answer_callback(callback_id, notification=notification or None)
        except Exception:
            logger.exception("Failed to answer MAX callback %s", callback_id)