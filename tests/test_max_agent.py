"""MAX agent bridge helpers."""

from __future__ import annotations

from integrations.max.markdown import split_max_text, truncate_max_text
from integrations.max.models import message_id_from_response
from integrations.max.session import MaxChatSession


def test_split_max_text_chunks_long_message() -> None:
    text = "line\n" * 2000
    chunks = split_max_text(text, limit=500)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)


def test_truncate_max_text() -> None:
    assert truncate_max_text("abc", limit=10) == "abc"
    assert truncate_max_text("x" * 20, limit=10).endswith("…")


def test_message_id_from_response() -> None:
    assert message_id_from_response({"message": {"message_id": "mid-1"}}) == "mid-1"
    assert message_id_from_response({"message": {"body": {"mid": "42"}}}) == "42"
    assert message_id_from_response({}) is None


def test_max_session_conversation_id() -> None:
    sess = MaxChatSession(user_id=7, profile="default", conversation_id="max_default_7")
    assert sess.execution_mode == "react"
    buf = sess.bump_live_buffer()
    assert buf.profile == "default"