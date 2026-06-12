"""Bridge from Holix agent to Link Relay RPC."""

from __future__ import annotations

import base64

from core.gateway.links_store import LinkRecord, LinksStore

from integrations.link.protocol import RpcCall, RpcOp, RpcResult, new_request_id


class LinkBridgeError(RuntimeError):
    """Raised when a remote link operation cannot be performed."""


def _links_store() -> LinksStore:
    return LinksStore()


def _get_relay():
    try:
        from api import state

        return state.link_relay
    except Exception:
        return None


def profile_has_links(profile: str) -> bool:
    return bool(_links_store().list_links(profile=profile, status="active"))


def list_profile_links(profile: str) -> list[LinkRecord]:
    return _links_store().list_links(profile=profile, status="active")


def resolve_link_id(profile: str, link_id: str | None = None) -> str:
    links = list_profile_links(profile)
    if not links:
        raise LinkBridgeError(f"No active Holix Link connections for profile '{profile}'")

    if link_id:
        wanted = link_id.strip()
        if any(item.link_id == wanted for item in links):
            return wanted
        raise LinkBridgeError(f"Link '{wanted}' not found for profile '{profile}'")

    if len(links) == 1:
        return links[0].link_id

    ids = ", ".join(item.link_id for item in links)
    raise LinkBridgeError(
        f"Profile '{profile}' has multiple links; specify link_id. Available: {ids}"
    )


async def call_link_rpc(
    profile: str,
    op: RpcOp,
    *,
    path: str = "",
    link_id: str | None = None,
    limit: int = 200,
    content_b64: str | None = None,
    timeout: float = 30.0,
) -> RpcResult:
    relay = _get_relay()
    if relay is None:
        raise LinkBridgeError(
            "Link relay is not available. Start the Holix gateway on this server."
        )

    resolved = resolve_link_id(profile, link_id)
    if not relay.is_online(resolved):
        raise LinkBridgeError(f"Holix Link '{resolved}' is offline")

    call = RpcCall(
        id=new_request_id(),
        op=op,
        path=path,
        limit=limit,
        content_b64=content_b64,
    )
    try:
        return await relay.call_rpc(resolved, call, timeout=timeout)
    except TimeoutError as exc:
        raise LinkBridgeError(str(exc)) from exc


def format_rpc_error(result: RpcResult) -> str:
    return result.error or "Remote link operation failed"


def format_list_dir(result: RpcResult, *, link_id: str) -> str:
    if not result.ok or result.payload is None or not result.payload.entries:
        return format_rpc_error(result) if not result.ok else f"Link {link_id}: (empty directory)"
    lines = [f"Remote folder via {link_id}:"]
    for entry in result.payload.entries:
        suffix = "/" if entry.is_dir else ""
        size = f" ({entry.size} bytes)" if entry.size is not None else ""
        lines.append(f"  {entry.path}{suffix}{size}")
    return "\n".join(lines)


def format_read_file(result: RpcResult, *, path: str, link_id: str) -> str:
    if not result.ok or result.payload is None:
        return f"Error: {format_rpc_error(result)}"
    payload = result.payload
    if payload.content is not None:
        return f"Remote file {path} (via {link_id}):\n{payload.content}"
    if payload.content_b64:
        try:
            raw = base64.b64decode(payload.content_b64)
            text = raw.decode("utf-8")
            return f"Remote file {path} (via {link_id}, binary as utf-8):\n{text}"
        except Exception:
            return (
                f"Remote file {path} (via {link_id}): "
                f"<binary {len(payload.content_b64)} base64 chars>"
            )
    return f"Error: empty read result for {path}"


def format_stat(result: RpcResult, *, link_id: str) -> str:
    if not result.ok or result.payload is None or result.payload.stat is None:
        return f"Error: {format_rpc_error(result)}"
    stat = result.payload.stat
    kind = "directory" if stat.is_dir else "file"
    mtime = f", mtime={stat.mtime}" if stat.mtime is not None else ""
    return f"Link {link_id} stat {stat.path}: {kind}, {stat.size} bytes{mtime}"


def encode_write_content(content: str) -> str:
    return base64.b64encode(content.encode("utf-8")).decode("ascii")