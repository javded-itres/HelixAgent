"""MAX HTTP client tests."""

from __future__ import annotations

import json

import aiohttp
import pytest
from aiohttp import web

from integrations.max.client import MaxApiError, MaxClient
from integrations.max.models import message_text, sender_user_id, update_type, user_id_from_update


async def _start_mock_server(handler):
    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    return runner, base


@pytest.mark.asyncio
async def test_get_me_and_send_message() -> None:
    calls: list[tuple[str, str]] = []

    async def handler(request: web.Request) -> web.Response:
        calls.append((request.method, request.path))
        auth = request.headers.get("Authorization", "")
        assert auth == "test-token"
        if request.path == "/me":
            return web.json_response({"user_id": 1, "username": "helix_bot", "is_bot": True})
        if request.path == "/messages":
            assert request.rel_url.query.get("user_id") == "42"
            body = await request.json()
            assert body["text"] == "pong"
            return web.json_response({"message": {"body": {"text": "pong"}}})
        return web.json_response({"error": "not found"}, status=404)

    runner, base = await _start_mock_server(handler)
    try:
        async with MaxClient("test-token", base_url=base) as client:
            me = await client.get_me()
            assert me["username"] == "helix_bot"
            await client.send_message("pong", user_id=42)
        assert ("GET", "/me") in calls
        assert ("POST", "/messages") in calls
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_get_updates_passes_marker() -> None:
    seen: list[str] = []

    async def handler(request: web.Request) -> web.Response:
        seen.append(request.rel_url.query_string)
        return web.json_response({"updates": [], "marker": 7})

    runner, base = await _start_mock_server(handler)
    try:
        async with MaxClient("tok", base_url=base) as client:
            payload = await client.get_updates(marker=5, types=["message_created"])
            assert payload["marker"] == 7
        assert "marker=5" in seen[0]
        assert "types=message_created" in seen[0]
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_api_error_on_401() -> None:
    async def handler(request: web.Request) -> web.Response:
        return web.json_response({"message": "unauthorized"}, status=401)

    runner, base = await _start_mock_server(handler)
    try:
        async with MaxClient("bad", base_url=base) as client:
            with pytest.raises(MaxApiError) as exc:
                await client.get_me()
            assert exc.value.status == 401
    finally:
        await runner.cleanup()


def test_update_helpers() -> None:
    update = {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": 99},
            "body": {"text": " ping "},
            "recipient": {"user_id": 99},
        },
    }
    assert update_type(update) == "message_created"
    assert user_id_from_update(update) == 99
    assert message_text(update["message"]) == "ping"
    assert sender_user_id(update["message"]) == 99