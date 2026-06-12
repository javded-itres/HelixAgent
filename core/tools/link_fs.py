"""Agent tools for Holix Link remote folder access."""

from __future__ import annotations

from integrations.link.bridge import (
    LinkBridgeError,
    call_link_rpc,
    encode_write_content,
    format_list_dir,
    format_read_file,
    format_rpc_error,
    format_stat,
)
from integrations.link.protocol import RpcOp

from core.tools.base import BaseTool
from core.tools.profile_identity import _resolve_profile_name


def register_link_tools(registry, profile: str | None = None) -> int:
    """Register link_* tools when the profile has active connections."""
    from integrations.link.bridge import profile_has_links

    name = (profile or _resolve_profile_name()).strip() or "default"
    if not profile_has_links(name):
        return 0

    registry.register(LinkListDirTool())
    registry.register(LinkReadFileTool())
    registry.register(LinkWriteFileTool())
    registry.register(LinkStatTool())
    registry.register(LinkMkdirTool())
    registry.register(LinkDeleteTool())
    return 6


class _LinkToolMixin:
    async def _rpc(self, op: RpcOp, path: str = "", link_id: str | None = None, **kwargs):
        profile = _resolve_profile_name()
        return await call_link_rpc(profile, op, path=path, link_id=link_id, **kwargs)


class LinkListDirTool(_LinkToolMixin, BaseTool):
    def __init__(self) -> None:
        super().__init__()
        self.name = "link_list_dir"
        self.description = (
            "List entries in a Holix Link remote folder (user PC behind NAT). "
            "Use when files live on a linked client, not on the server."
        )
        self.risk_level = "no"
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path inside the linked folder (empty = root)",
                },
                "link_id": {
                    "type": "string",
                    "description": "Link id when the profile has multiple connections",
                },
                "limit": {"type": "integer", "description": "Max entries (default 200)"},
            },
            "required": [],
        }

    async def execute(self, path: str = "", link_id: str | None = None, limit: int = 200) -> str:
        try:
            result = await self._rpc(RpcOp.LIST_DIR, path=path, link_id=link_id, limit=limit)
            if not result.ok:
                return f"Error: {format_rpc_error(result)}"
            return format_list_dir(result, link_id=link_id or "link")
        except LinkBridgeError as exc:
            return f"Error: {exc}"


class LinkReadFileTool(_LinkToolMixin, BaseTool):
    def __init__(self) -> None:
        super().__init__()
        self.name = "link_read_file"
        self.description = "Read a file from a Holix Link remote folder"
        self.risk_level = "no"
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "link_id": {"type": "string", "description": "Optional link id"},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, link_id: str | None = None) -> str:
        try:
            result = await self._rpc(RpcOp.READ_FILE, path=path, link_id=link_id)
            return format_read_file(result, path=path, link_id=link_id or "link")
        except LinkBridgeError as exc:
            return f"Error: {exc}"


class LinkWriteFileTool(_LinkToolMixin, BaseTool):
    def __init__(self) -> None:
        super().__init__()
        self.name = "link_write_file"
        self.description = "Write a file to a Holix Link remote folder"
        self.risk_level = "medium"
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "content": {"type": "string", "description": "UTF-8 text content"},
                "link_id": {"type": "string", "description": "Optional link id"},
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str, content: str, link_id: str | None = None) -> str:
        try:
            result = await self._rpc(
                RpcOp.WRITE_FILE,
                path=path,
                link_id=link_id,
                content_b64=encode_write_content(content),
            )
            if not result.ok:
                return f"Error: {format_rpc_error(result)}"
            written = result.payload.bytes_written if result.payload else len(content.encode())
            return f"Wrote {written} bytes to remote {path}"
        except LinkBridgeError as exc:
            return f"Error: {exc}"


class LinkStatTool(_LinkToolMixin, BaseTool):
    def __init__(self) -> None:
        super().__init__()
        self.name = "link_stat"
        self.description = "Stat a path in a Holix Link remote folder"
        self.risk_level = "no"
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path"},
                "link_id": {"type": "string", "description": "Optional link id"},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, link_id: str | None = None) -> str:
        try:
            result = await self._rpc(RpcOp.STAT, path=path, link_id=link_id)
            return format_stat(result, link_id=link_id or "link")
        except LinkBridgeError as exc:
            return f"Error: {exc}"


class LinkMkdirTool(_LinkToolMixin, BaseTool):
    def __init__(self) -> None:
        super().__init__()
        self.name = "link_mkdir"
        self.description = "Create a directory in a Holix Link remote folder"
        self.risk_level = "medium"
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative directory path"},
                "link_id": {"type": "string", "description": "Optional link id"},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, link_id: str | None = None) -> str:
        try:
            result = await self._rpc(RpcOp.MKDIR, path=path, link_id=link_id)
            if not result.ok:
                return f"Error: {format_rpc_error(result)}"
            return f"Created remote directory {path}"
        except LinkBridgeError as exc:
            return f"Error: {exc}"


class LinkDeleteTool(_LinkToolMixin, BaseTool):
    def __init__(self) -> None:
        super().__init__()
        self.name = "link_delete"
        self.description = "Delete a file in a Holix Link remote folder (not directories)"
        self.risk_level = "high"
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "link_id": {"type": "string", "description": "Optional link id"},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, link_id: str | None = None) -> str:
        try:
            result = await self._rpc(RpcOp.DELETE, path=path, link_id=link_id)
            if not result.ok:
                return f"Error: {format_rpc_error(result)}"
            return f"Deleted remote file {path}"
        except LinkBridgeError as exc:
            return f"Error: {exc}"