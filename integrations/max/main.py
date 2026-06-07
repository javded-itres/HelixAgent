"""Entry point: helix max."""

from __future__ import annotations

import asyncio
import logging

from integrations.max.config import load_max_settings
from integrations.max.polling import run_polling

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def run_bot(profile: str = "default") -> None:
    settings = load_max_settings(profile)
    if settings.is_webhook_mode:
        raise RuntimeError(
            "HELIX_MAX_MODE=webhook — используйте `helix gateway start` (Long Polling только для dev/test)."
        )
    await run_polling(settings, profile=profile)


def main(profile: str = "default") -> None:
    asyncio.run(run_bot(profile))


if __name__ == "__main__":
    from core.platform_compat import ensure_multiprocessing_support

    ensure_multiprocessing_support()
    main()