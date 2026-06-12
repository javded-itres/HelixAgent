"""Holix Link management — pairing codes and connected clients."""

from __future__ import annotations

import re

import typer
from core.gateway.links_store import LinksStore, link_connected_iso, pair_code_expires_iso

from cli.core import ProfileManager
from cli.utils.rich_console import print_error, print_info, print_success, print_warning

app = typer.Typer(
    help="Manage Holix Link remote folder connections",
    no_args_is_help=True,
)

_TTL_RE = re.compile(r"^(?P<num>\d+)(?P<unit>[smh])?$", re.IGNORECASE)


def _profile(ctx: typer.Context, explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    return ctx.obj["profile"]


def _parse_ttl(raw: str) -> int:
    text = raw.strip().lower()
    match = _TTL_RE.match(text)
    if not match:
        raise typer.BadParameter("TTL format: 600, 10m, 1h")
    num = int(match.group("num"))
    unit = (match.group("unit") or "s").lower()
    if unit == "m":
        return num * 60
    if unit == "h":
        return num * 3600
    return num


def _relay_online(link_id: str) -> bool | None:
    try:
        from api import state

        relay = state.link_relay
        if relay is None:
            return None
        return relay.is_online(link_id)
    except Exception:
        return None


@app.command("create")
def link_create(
    ctx: typer.Context,
    profile: str = typer.Option(None, "--profile", "-p", help="Server profile for the link"),
    ttl: str = typer.Option("10m", "--ttl", help="Pair code lifetime (e.g. 10m, 1h, 600)"),
) -> None:
    """Create a one-time pairing code for a Holix Link client."""
    target = _profile(ctx, profile)
    manager = ProfileManager()
    if not manager.profile_exists(target):
        print_error(f"Profile '{target}' does not exist")
        raise typer.Exit(1)

    ttl_seconds = _parse_ttl(ttl)
    if ttl_seconds < 60 or ttl_seconds > 3600:
        print_error("TTL must be between 60 seconds and 1 hour")
        raise typer.Exit(1)

    store = LinksStore()
    store.purge_expired_pair_codes()
    record = store.create_pair_code(profile=target, ttl_seconds=ttl_seconds, created_by="cli")
    print_success("Pairing code created")
    print_info(f"  Profile:  {target}")
    print_info(f"  Code:     [bold]{record.code}[/bold]")
    print_info(f"  Expires:  {pair_code_expires_iso(record)}")
    print_info("")
    print_info("On the client PC:")
    print_info(f"  holix-link pair {record.code} --folder ~/your-folder --server <gateway-url>")


@app.command("list")
def link_list(
    ctx: typer.Context,
    profile: str = typer.Option(None, "--profile", "-p", help="Filter by profile"),
    all_profiles: bool = typer.Option(False, "--all", help="List links for every profile"),
) -> None:
    """List Holix Link connections."""
    store = LinksStore()
    if all_profiles:
        records = store.list_links(status=None)
    else:
        target = _profile(ctx, profile)
        records = store.list_links(profile=target, status=None)

    if not records:
        print_info("No Holix Link connections.")
        raise typer.Exit(0)

    for rec in records:
        online = _relay_online(rec.link_id)
        online_text = "online" if online else "offline" if online is False else "unknown"
        print_info(f"{rec.link_id}  profile={rec.profile}  status={rec.status}  {online_text}")
        print_info(f"  folder: {rec.folder_portable}")
        connected = link_connected_iso(rec)
        if connected:
            print_info(f"  last connected: {connected}")


@app.command("revoke")
def link_revoke(
    link_id: str = typer.Argument(..., help="Link id to revoke"),
) -> None:
    """Revoke a Holix Link connection."""
    store = LinksStore()
    record = store.get_link(link_id)
    if record is None:
        print_error(f"Link '{link_id}' not found")
        raise typer.Exit(1)
    if record.status != "active":
        print_warning(f"Link '{link_id}' is already {record.status}")
        raise typer.Exit(0)

    if not store.revoke_link(link_id):
        print_error(f"Failed to revoke '{link_id}'")
        raise typer.Exit(1)

    try:
        from api import state

        relay = state.link_relay
        if relay is not None:
            websocket = relay._connections.get(link_id)  # noqa: SLF001
            if websocket is not None:
                import asyncio

                async def _close() -> None:
                    await websocket.close(code=1008, reason="revoked")
                    await relay.unregister(link_id, websocket)

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(_close())
                    else:
                        loop.run_until_complete(_close())
                except RuntimeError:
                    asyncio.run(_close())
    except Exception:
        pass

    print_success(f"Revoked link {link_id} (profile {record.profile})")