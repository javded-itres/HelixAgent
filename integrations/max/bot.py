"""MAX bot event dispatcher."""

from __future__ import annotations

import logging
from typing import Any

from integrations.max.agent_setup import create_agent
from integrations.max.client import MaxClient
from integrations.max.commands import help_message_markdown, register_bot_commands
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
from integrations.max.markdown import plain_to_max_html
from integrations.max.models import (
    callback_id_from_update,
    callback_payload_from_update,
    callback_reply_target,
    chat_type_from_message,
    chat_type_from_update,
    conversation_id_for_max,
    message_from_update,
    message_has_media,
    message_text,
    message_mid_from_message,
    reply_kwargs_for_session,
    reply_target_from_message,
    sender_user_id,
    update_type,
    user_id_from_update,
)
from integrations.telegram.file_handler import SavedTelegramFile
from integrations.max.session import MaxChatSession

logger = logging.getLogger(__name__)


def _session_key(user_id: int, chat_id: int | None) -> tuple[int, int]:
    return (chat_id or 0, user_id)


class HelixMaxBot:
    def __init__(self, settings: MaxSettings | None = None, *, profile: str = "default") -> None:
        self.settings = settings or load_max_settings(profile)
        self._sessions: dict[tuple[int, int], MaxChatSession] = {}
        self._agent = None

    async def warmup(self) -> None:
        """Eagerly initialize shared Helix agent (memory, tools, MCP) at bot startup."""
        if self._agent is not None:
            return
        logger.info("Initializing Helix agent (profile=%s)…", self.settings.profile)
        self._agent = await create_agent(self.settings.profile)
        model = getattr(self._agent, "model", None) or "—"
        logger.info("Helix agent ready (profile=%s, model=%s)", self.settings.profile, model)

    def _allowed(self, user_id: int) -> bool:
        return self.settings.is_user_allowed(user_id)

    async def _get_session(
        self,
        user_id: int,
        *,
        reply_user_id: int | None,
        reply_chat_id: int | None,
        chat_type: str | None = None,
    ) -> MaxChatSession:
        key = _session_key(user_id, reply_chat_id)
        if key not in self._sessions:
            conv = conversation_id_for_max(
                self.settings.profile,
                user_id,
                chat_id=reply_chat_id,
                chat_type=chat_type,
            )
            self._sessions[key] = MaxChatSession(
                user_id=user_id,
                profile=self.settings.profile,
                conversation_id=conv,
                reply_user_id=reply_user_id,
                reply_chat_id=reply_chat_id,
                chat_type=chat_type or "",
            )
        session = self._sessions[key]
        session.reply_user_id = reply_user_id
        session.reply_chat_id = reply_chat_id
        if chat_type:
            session.chat_type = chat_type
        if session.agent is None:
            if self._agent is None:
                self._agent = await create_agent(self.settings.profile)
            session.agent = self._agent
            self._restore_session_model(session)
        return session

    def _restore_session_model(self, session: MaxChatSession) -> None:
        from core.session_models import restore_session_model

        class _Host:
            def __init__(self, s: MaxChatSession) -> None:
                self._session = s

            @property
            def profile(self) -> str:
                return self._session.profile

            @property
            def conversation_id(self) -> str:
                return self._session.conversation_id

            @property
            def agent(self) -> Any:
                return self._session.agent

        restore_session_model(_Host(session))

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
        try:
            from core.i18n import LocaleStore

            locale = LocaleStore(self.settings.profile).get()
            await register_bot_commands(client, locale=locale)
        except Exception:
            logger.exception("Failed to sync MAX command menu on bot_started")
        await client.send_message(
            plain_to_max_html(
                help_message_markdown()
                + "\n\n**Команды:** введите `/` в поле ввода или отправьте `/menu` — панель управления."
            ),
            user_id=uid,
            fmt="html",
        )

    async def _handle_message_created(self, client: MaxClient, update: dict[str, Any]) -> None:
        msg = message_from_update(update)
        if msg is None:
            return
        uid = sender_user_id(msg)
        if uid is None:
            return
        if not self._allowed(uid):
            logger.warning(
                "MAX message from disallowed user %s (allowlist=%s)",
                uid,
                self.settings.allowed_user_ids or "(empty)",
            )
            return
        text = message_text(msg).strip()
        logger.info("MAX message from user %s: %r", uid, text[:120] if text else "(media)")
        reply_user_id, reply_chat_id = reply_target_from_message(msg)
        if reply_user_id is None and reply_chat_id is None:
            reply_user_id = uid
        incoming_mid = message_mid_from_message(msg)

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

        chat_type = chat_type_from_update(update)
        if text.lower() == "ping":
            await client.send_message(
                "pong",
                **reply_kwargs_for_session(
                    user_id=uid,
                    reply_user_id=reply_user_id,
                    reply_chat_id=reply_chat_id,
                    chat_type=chat_type,
                ),
            )
            return

        session = await self._get_session(
            uid,
            reply_user_id=reply_user_id,
            reply_chat_id=reply_chat_id,
            chat_type=chat_type,
        )
        session.incoming_message_id = incoming_mid
        host = MaxHost(client, session)
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

        chat_type = chat_type_from_message(message)
        reply = reply_kwargs_for_session(
            user_id=user_id,
            reply_user_id=reply_user_id,
            reply_chat_id=reply_chat_id,
            chat_type=chat_type,
        )
        if not settings.max_files_enabled:
            await client.send_message(
                "📎 Приём файлов отключён. Установите HELIX_MAX_FILES_ENABLED=true.",
                **reply,
            )
            return

        attachments = extract_media_attachments(message)
        if not attachments:
            return

        session = await self._get_session(
            user_id,
            reply_user_id=reply_user_id,
            reply_chat_id=reply_chat_id,
            chat_type=chat_type,
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
                plain_to_max_html(f"📎 **Файлы**\n\n❌ {'; '.join(errors)}"),
                fmt="html",
                **reply,
            )
            return

        preview = format_files_preview_markdown(saved, errors=errors)
        if caption:
            await client.send_message(
                plain_to_max_html(preview),
                fmt="html",
                **reply,
            )
            prompt = build_agent_prompt(caption, saved)
            await host.handle_user_text(prompt)
            return

        session.pending_files.extend(saved)
        count = len(saved)
        await client.send_message(
            plain_to_max_html(
                preview
                + f"\n\nСохранено файлов: {count}. Напишите задачу "
                "(можно добавить ещё файлы, затем одно сообщение с инструкцией)."
            ),
            fmt="html",
            **reply,
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
            chat_type=chat_type_from_update(update),
        )
        host = MaxHost(client, session)
        approvals = MaxApprovals(client, session)
        notification = ""

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