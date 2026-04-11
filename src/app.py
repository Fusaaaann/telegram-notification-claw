from __future__ import annotations

import asyncio
import logging

import uvicorn

from .api import create_api
from .config import settings
from .db import ReminderDB
from .telegram_bot import build_bot_app, run_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    db = ReminderDB.from_settings(settings)

    api = create_api(db)
    bot_app = build_bot_app(db)

    # Run bot + API concurrently in one process (simple experiment setup).
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()

    scheduler_task = asyncio.get_event_loop().create_task(run_scheduler(db, bot_app))

    config = uvicorn.Config(api, host=settings.host, port=settings.port, log_level="info")
    server = uvicorn.Server(config)

    try:
        await server.serve()
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
