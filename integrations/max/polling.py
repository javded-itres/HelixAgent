"""Long Polling worker for MAX (dev/test only)."""

from __future__ import annotations

import asyncio
import logging

from integrations.max.bot import HelixMaxBot
from integrations.max.client import MaxApiError, MaxClient
from integrations.max.config import MaxSettings, load_max_settings

logger = logging.getLogger(__name__)

POLL_TYPES = [
    "bot_started",
    "message_created",
    "message_callback",
]


async def run_polling(settings: MaxSettings | None = None, *, profile: str = "default") -> None:
    settings = settings or load_max_settings(profile)
    token = settings.access_token.strip()
    if not token:
        raise RuntimeError("MAX_ACCESS_TOKEN is not set. Run: helix max setup")

    bot = HelixMaxBot(settings, profile=profile)
    marker: int | None = None
    logger.info("MAX Long Polling started (profile=%s)", settings.profile)

    async with MaxClient(token) as client:
        while True:
            try:
                payload = await client.get_updates(
                    marker=marker,
                    limit=100,
                    timeout=30,
                    types=POLL_TYPES,
                )
            except MaxApiError as exc:
                logger.warning("MAX polling error: %s", exc)
                await asyncio.sleep(2.0)
                continue

            next_marker = payload.get("marker")
            if isinstance(next_marker, int):
                marker = next_marker

            updates = payload.get("updates")
            if not isinstance(updates, list):
                continue
            for update in updates:
                if isinstance(update, dict):
                    try:
                        await bot.handle_update(client, update)
                    except Exception:
                        logger.exception("Failed to handle MAX update")