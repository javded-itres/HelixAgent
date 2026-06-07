"""Helpers for MAX API update payloads."""

from __future__ import annotations

from typing import Any


def update_type(update: dict[str, Any]) -> str:
    return str(update.get("update_type") or "")


def message_from_update(update: dict[str, Any]) -> dict[str, Any] | None:
    msg = update.get("message")
    return msg if isinstance(msg, dict) else None


def message_has_media(message: dict[str, Any]) -> bool:
    from integrations.max.file_handler import extract_media_attachments

    return bool(extract_media_attachments(message))


def message_text(message: dict[str, Any]) -> str:
    body = message.get("body")
    if not isinstance(body, dict):
        return ""
    text = body.get("text")
    return str(text).strip() if text is not None else ""


def sender_user_id(message: dict[str, Any]) -> int | None:
    sender = message.get("sender")
    if not isinstance(sender, dict):
        return None
    uid = sender.get("user_id")
    if isinstance(uid, int):
        return uid
    if isinstance(uid, str) and uid.isdigit():
        return int(uid)
    return None


def recipient_target(message: dict[str, Any]) -> tuple[int | None, int | None]:
    """Return (user_id, chat_id) for replying via POST /messages."""
    recipient = message.get("recipient")
    if not isinstance(recipient, dict):
        return None, None
    chat_id = recipient.get("chat_id")
    user_id = recipient.get("user_id")
    cid = int(chat_id) if isinstance(chat_id, int) else None
    uid = int(user_id) if isinstance(user_id, int) else None
    if cid is None and isinstance(chat_id, str) and chat_id.isdigit():
        cid = int(chat_id)
    if uid is None and isinstance(user_id, str) and user_id.isdigit():
        uid = int(user_id)
    return uid, cid


def message_id_from_response(payload: dict[str, Any]) -> str | None:
    if not isinstance(payload, dict):
        return None
    msg = payload.get("message")
    if not isinstance(msg, dict):
        return None
    for key in ("message_id", "id", "mid"):
        val = msg.get(key)
        if val is not None and str(val).strip():
            return str(val)
    body = msg.get("body")
    if isinstance(body, dict):
        for key in ("mid", "message_id", "id"):
            val = body.get(key)
            if val is not None and str(val).strip():
                return str(val)
    return None


def callback_from_update(update: dict[str, Any]) -> dict[str, Any] | None:
    cb = update.get("callback")
    return cb if isinstance(cb, dict) else None


def callback_id_from_update(update: dict[str, Any]) -> str | None:
    cb = callback_from_update(update)
    if cb is None:
        return None
    cid = cb.get("callback_id")
    return str(cid).strip() if cid is not None and str(cid).strip() else None


def callback_payload_from_update(update: dict[str, Any]) -> str:
    cb = callback_from_update(update)
    if cb is None:
        return ""
    payload = cb.get("payload")
    return str(payload).strip() if payload is not None else ""


def callback_reply_target(update: dict[str, Any]) -> tuple[int | None, int | None]:
    cb = callback_from_update(update)
    if cb is None:
        return None, None
    msg = cb.get("message")
    if isinstance(msg, dict):
        return recipient_target(msg)
    uid = user_id_from_update(update)
    return uid, update.get("chat_id") if isinstance(update.get("chat_id"), int) else None


def user_id_from_update(update: dict[str, Any]) -> int | None:
    if update_type(update) == "message_created":
        msg = message_from_update(update)
        if msg is not None:
            return sender_user_id(msg)
    if update_type(update) == "bot_started":
        user = update.get("user")
        if isinstance(user, dict):
            uid = user.get("user_id")
            if isinstance(uid, int):
                return uid
            if isinstance(uid, str) and uid.isdigit():
                return int(uid)
    if update_type(update) == "message_callback":
        callback = update.get("callback")
        if isinstance(callback, dict):
            user = callback.get("user")
            if isinstance(user, dict):
                uid = user.get("user_id")
                if isinstance(uid, int):
                    return uid
    return None