from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

try:
    from telegram import Bot, Update
    from telegram.ext import Application, CommandHandler, ContextTypes
except ImportError:  # pragma: no cover - telegram runtime is optional in local tests
    Bot = Any
    Update = Any
    Application = Any
    CommandHandler = Any

    class ContextTypes:
        DEFAULT_TYPE = Any

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
        chat_id = int(update.effective_chat.id)
        token = context.args[0].strip() if context.args else ""
        user_id, reply_text = bind_chat_for_start(
            db,
            chat_id=chat_id,
            token=token,
            fallback_user_id=int(update.effective_user.id),
        )
        logger.info("Bound chat_id=%s to user_id=%s via /start", chat_id, user_id)
        if update.message:
            await update.message.reply_text(reply_text)

    async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("pong")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    return app


def parse_start_token(text: str) -> str:
    parts = text.strip().split(None, 1)
    if not parts or parts[0] != "/start":
        return ""
    return parts[1].strip() if len(parts) == 2 else ""


def bind_chat_for_start(
    db: ReminderDB,
    *,
    chat_id: int,
    token: str = "",
    fallback_user_id: int | None = None,
) -> tuple[int, str]:
    if token:
        user_id = db.get_user_id_by_token(token)
        if not user_id:
            raise ValueError("Invalid start token")
        db.upsert_chat_binding(user_id=user_id, chat_id=chat_id)
        return user_id, "ok, token linked; this chat will receive reminders."

    if fallback_user_id is None:
        raise ValueError("Missing user identity for /start")

    db.upsert_chat_binding(user_id=fallback_user_id, chat_id=chat_id)
    return fallback_user_id, "ok, bound; you can now receive reminder messages."


def _due_at_to_utc(s: str, *, timezone_name: str | None = None) -> datetime:
    from cli.datecalc import parse_iso_datetime_loose

    dt = parse_iso_datetime_loose(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=settings.zoneinfo() if timezone_name is None else ZoneInfo(timezone_name))
    return dt.astimezone(timezone.utc)


async def handle_webhook_update(
    db: ReminderDB,
    payload: dict[str, Any],
    bot: Bot | None = None,
) -> dict[str, Any]:
    message = payload.get("message") or payload.get("edited_message") or {}
    text = str(message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    from_user = message.get("from") or {}
    fallback_user_id = from_user.get("id")

    if not text.startswith("/start") or chat_id is None:
        return {"ok": True, "handled": False}

    try:
        user_id, reply_text = bind_chat_for_start(
            db,
            chat_id=int(chat_id),
            token=parse_start_token(text),
            fallback_user_id=int(fallback_user_id) if fallback_user_id is not None else None,
        )
    except ValueError as exc:
        reply_text = str(exc)
        user_id = None

    if bot is not None:
        await bot.send_message(chat_id=int(chat_id), text=reply_text)

    return {"ok": True, "handled": True, "user_id": user_id}


async def dispatch_due_reminders(
    db: ReminderDB,
    bot_or_app: Bot | Application,
    *,
    now: datetime | None = None,
    timezone_name: str | None = None,
) -> dict[str, Any]:
    bot = bot_or_app.bot if hasattr(bot_or_app, "bot") else bot_or_app
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current_utc = current.astimezone(timezone.utc)

    scanned = db.get_due_reminders()
    due: list[dict[str, Any]] = []
    invalid_due_at: list[int] = []

    for row in scanned:
        try:
            due_at = _due_at_to_utc(str(row["due_at"]), timezone_name=timezone_name)
        except Exception:
            invalid_due_at.append(int(row["id"]))
            logger.warning("Could not parse due_at=%r for reminder id=%s", row["due_at"], row["id"])
            continue
        if due_at <= current_utc:
            due.append(row)

    sent = 0
    skipped_unbound = 0
    failed: list[int] = []

    for row in due:
        user_id = int(row["user_id"])
        reminder_id = int(row["id"])
        try:
            if row.get("visibility") == "global":
                delivered = await send_global_text(db, str(row["text"]), bot)
            else:
                delivered = await send_text(db, user_id, str(row["text"]), bot)
        except Exception:
            failed.append(reminder_id)
            logger.exception("Failed to dispatch reminder id=%s", reminder_id)
            continue

        if delivered:
            db.update_admin_reminder(reminder_id=reminder_id, done=True)
            sent += 1
        else:
            skipped_unbound += 1
            logger.warning("No delivery route for reminder id=%s", reminder_id)

    return {
        "ok": True,
        "scanned": len(scanned),
        "due": len(due),
        "sent": sent,
        "skipped_unbound": skipped_unbound,
        "invalid_due_at": invalid_due_at,
        "failed": failed,
    }


async def run_scheduler(db: ReminderDB, app: Application, interval: int = 60) -> None:
    tz_name = settings.reminder_timezone

    while True:
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return

        dispatch_task = asyncio.get_event_loop().create_task(
            dispatch_due_reminders(db, app, timezone_name=tz_name)
        )
        try:
            await asyncio.shield(dispatch_task)
        except asyncio.CancelledError:
            await dispatch_task
            return


async def send_text(db: ReminderDB, user_id: int, text: str, bot: Bot | Any) -> bool:
    chat_id = db.get_chat_id(user_id)
    if not chat_id:
        return False
    await bot.send_message(chat_id=chat_id, text=text)
    return True


async def send_global_text(db: ReminderDB, text: str, bot: Bot | Any) -> bool:
    bindings = db.list_chat_bindings()
    if not bindings:
        return False
    delivered = False
    seen_chat_ids: set[int] = set()
    for binding in bindings:
        chat_id = int(binding["chat_id"])
        if chat_id in seen_chat_ids:
            continue
        await bot.send_message(chat_id=chat_id, text=text)
        seen_chat_ids.add(chat_id)
        delivered = True
    return delivered
