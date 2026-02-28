from __future__ import annotations

import logging
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


async def send_text(db: ReminderDB, user_id: int, text: str, app: Application) -> bool:
    chat_id = db.get_chat_id(user_id)
    if not chat_id:
        return False
    await app.bot.send_message(chat_id=chat_id, text=text)
    return True
