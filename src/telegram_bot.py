from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .config import settings
from .db import ReminderDB

logger = logging.getLogger(__name__)


def build_bot_app(db: ReminderDB) -> Application:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty")

    app = Application.builder().token(settings.telegram_bot_token).build()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not update.effective_chat:
            return
        user_id = int(update.effective_user.id)
        chat_id = int(update.effective_chat.id)
        db.upsert_chat_binding(user_id=user_id, chat_id=chat_id)
        await update.message.reply_text("ok, bound; you can now receive reminder messages.")

    async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("pong")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    return app


async def run_scheduler(db: ReminderDB, app: Application, interval: int = 60) -> None:
    from cli.datecalc import parse_iso_datetime_loose

    async def _dispatch(row: dict) -> None:
        user_id = int(row["user_id"])
        reminder_id = int(row["id"])
        sent = await send_text(db, user_id, row["text"], app)
        if sent:
            db.update_reminder(user_id=user_id, reminder_id=reminder_id, done=True)
        else:
            logger.warning("No chat_id for user_id=%s, skipping reminder id=%s", user_id, reminder_id)

    while True:
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return

        now = datetime.now().replace(microsecond=0, tzinfo=None)
        due = []
        for r in db.get_due_reminders():
            try:
                dt = parse_iso_datetime_loose(r["due_at"]).replace(tzinfo=None)
                if dt <= now:
                    due.append(r)
            except Exception:
                logger.warning("Could not parse due_at=%r for reminder id=%s", r["due_at"], r["id"])

        for row in due:
            dispatch_task = asyncio.get_event_loop().create_task(_dispatch(row))
            try:
                await asyncio.shield(dispatch_task)
            except asyncio.CancelledError:
                await dispatch_task
                return
            except Exception:
                logger.exception("Failed to dispatch reminder id=%s", row["id"])


async def send_text(db: ReminderDB, user_id: int, text: str, app: Application) -> bool:
    chat_id = db.get_chat_id(user_id)
    if not chat_id:
        return False
    await app.bot.send_message(chat_id=chat_id, text=text)
    return True
