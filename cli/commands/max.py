"""helix max — setup and run Helix via MAX messenger bot."""

from __future__ import annotations

import asyncio

import typer

from cli.commands.max_setup import run_max_setup, show_max_status
from cli.utils.rich_console import print_error, print_info

max_app = typer.Typer(
    help="MAX messenger bot: interactive setup and run",
    invoke_without_command=True,
)


@max_app.callback()
def max_default(
    ctx: typer.Context,
    profile: str = typer.Option("default", "--profile", "-p", help="Helix profile"),
) -> None:
    """Start MAX bot (Long Polling — dev/test)."""
    if ctx.invoked_subcommand is not None:
        return
    max_run(profile=profile)


@max_app.command("run")
def max_run(
    profile: str = typer.Option("default", "--profile", "-p", help="Helix profile"),
) -> None:
    """Start MAX bot Long Polling (dev/test)."""
    try:
        from integrations.max.env_store import load_max_env_files
        from integrations.max.main import run_bot

        load_max_env_files()
    except ImportError as e:
        print_error(str(e))
        raise typer.Exit(1) from e

    print_info(f"Starting Helix MAX bot (profile={profile})…")
    try:
        asyncio.run(run_bot(profile))
    except RuntimeError as e:
        print_error(str(e))
        if "MAX_ACCESS_TOKEN" in str(e):
            print_info("Настройка: helix max setup")
        raise typer.Exit(1) from e


@max_app.command("setup")
def max_setup(
    profile: str | None = typer.Option(None, "--profile", "-p", help="Helix profile"),
    project_env: bool = typer.Option(
        False,
        "--project-env",
        help="Also write keys to ./.env in the current directory",
    ),
    no_start: bool = typer.Option(False, "--no-start", help="Do not offer to start the bot"),
) -> None:
    """Interactive wizard: token, allowlist, mode, save config."""
    asyncio.run(
        run_max_setup(
            profile=profile,
            also_project_env=project_env,
            skip_start=no_start,
        )
    )


@max_app.command("status")
def max_status() -> None:
    """Show saved MAX configuration (token masked)."""
    show_max_status()


def register_max_command(app: typer.Typer) -> None:
    app.add_typer(max_app, name="max")