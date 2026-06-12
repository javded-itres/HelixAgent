"""Holix Link agent tools and bridge."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from core.gateway.links_store import LinksStore
from core.tools.link_fs import LinkReadFileTool, register_link_tools
from core.tools.registry import ToolRegistry
from integrations.link.bridge import resolve_link_id
from integrations.link.protocol import LinkPermissions, RpcResult, RpcResultPayload


@pytest.fixture
def holix_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOLIX_HOME", str(tmp_path))
    monkeypatch.setenv("HOLIX_ENV", "development")
    return tmp_path


def test_resolve_link_id_single(holix_home) -> None:
    store = LinksStore()
    link = store.create_link(
        profile="support",
        folder_portable="~/work",
        device_public_key_b64="a",
        permissions=LinkPermissions(),
    )
    assert resolve_link_id("support") == link.link_id


def test_register_link_tools_only_with_links(holix_home) -> None:
    registry = ToolRegistry()
    assert register_link_tools(registry, "empty") == 0

    LinksStore().create_link(
        profile="support",
        folder_portable="~/work",
        device_public_key_b64="a",
        permissions=LinkPermissions(),
    )
    registry = ToolRegistry()
    count = register_link_tools(registry, "support")
    assert count == 6
    assert "link_read_file" in registry.tools


@pytest.mark.asyncio
async def test_link_read_file_tool(monkeypatch, holix_home) -> None:
    store = LinksStore()
    link = store.create_link(
        profile="default",
        folder_portable="~/work",
        device_public_key_b64="a",
        permissions=LinkPermissions(),
    )

    relay = MagicMock()
    relay.is_online = MagicMock(return_value=True)
    relay.call_rpc = AsyncMock(
        return_value=RpcResult(
            id="1",
            ok=True,
            payload=RpcResultPayload(content="remote text"),
        )
    )

    import api.state

    monkeypatch.setattr(api.state, "link_relay", relay)
    monkeypatch.setattr("core.tools.link_fs._resolve_profile_name", lambda: "default")

    tool = LinkReadFileTool()
    result = await tool.execute(path="readme.md", link_id=link.link_id)
    assert "remote text" in result
    relay.call_rpc.assert_awaited_once()