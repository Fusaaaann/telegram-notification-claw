from __future__ import annotations

import secrets
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from .auth import optional_scoped_user_id, require_admin_bearer, require_user_id_from_bearer
from .config import settings
from .db import ReminderDB
from .models import Reminder, ReminderCreate, ReminderUpdate
from .telegram_bot import dispatch_due_reminders, handle_webhook_update


def create_api(db: ReminderDB) -> FastAPI:
    app = FastAPI(title="Reminder CRUD API", version="0.3")

    def _parse_dt(dt: Optional[datetime]) -> Optional[str]:
        return dt.isoformat() if dt else None

    def _user_id_dep(authorization: str = Header(default="", alias="Authorization")) -> int:
        return require_user_id_from_bearer(db, authorization)

    @app.get("/health")
    def health():
        return {"ok": True}

    # --- Admin CRUD (acts on behalf of a user_id) ---
    @app.post("/v1/admin/reminders", dependencies=[Depends(require_admin_bearer)])
    def admin_create_reminder(
        payload: ReminderCreate,
        user_id: Optional[int] = Depends(optional_scoped_user_id),
    ) -> Reminder:
        if payload.visibility == "user" and user_id is None:
            raise HTTPException(status_code=400, detail="X-Reminder-User-Id is required for user visibility")
        r = db.create_reminder(
            user_id=user_id,
            text=payload.text,
            due_at=_parse_dt(payload.due_at),
            visibility=payload.visibility,
        )
        return Reminder(**r)

    @app.get("/v1/admin/reminders", dependencies=[Depends(require_admin_bearer)])
    def admin_list_reminders(
        include_done: bool = Query(default=True),
        visibility: Optional[str] = Query(default=None, pattern="^(global|user)$"),
        user_id: Optional[int] = Depends(optional_scoped_user_id),
    ) -> List[Reminder]:
        rows = db.list_reminders_for_admin(scoped_user_id=user_id, include_done=include_done, visibility=visibility)
        return [Reminder(**r) for r in rows]

    @app.get("/v1/admin/reminders/{reminder_id}", dependencies=[Depends(require_admin_bearer)])
    def admin_get_reminder(
        reminder_id: int,
    ) -> Reminder:
        try:
            r = db.get_reminder(reminder_id=reminder_id)
            return Reminder(**r)
        except KeyError:
            raise HTTPException(status_code=404, detail="not found")

    @app.patch("/v1/admin/reminders/{reminder_id}", dependencies=[Depends(require_admin_bearer)])
    def admin_patch_reminder(
        reminder_id: int,
        payload: ReminderUpdate,
        user_id: Optional[int] = Depends(optional_scoped_user_id),
    ) -> Reminder:
        try:
            if payload.visibility == "user" and user_id is None:
                raise HTTPException(status_code=400, detail="X-Reminder-User-Id is required for user visibility")
            r = db.update_admin_reminder(
                reminder_id=reminder_id,
                text=payload.text,
                due_at=_parse_dt(payload.due_at) if payload.due_at is not None else None,
                done=payload.done,
                visibility=payload.visibility,
                user_id=user_id,
            )
            return Reminder(**r)
        except KeyError:
            raise HTTPException(status_code=404, detail="not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.delete("/v1/admin/reminders/{reminder_id}", dependencies=[Depends(require_admin_bearer)])
    def admin_delete_reminder(
        reminder_id: int,
    ):
        try:
            db.delete_admin_reminder(reminder_id=reminder_id)
            return {"ok": True}
        except KeyError:
            raise HTTPException(status_code=404, detail="not found")

    # --- Admin: provision per-user bearer token ---
    @app.post("/v1/admin/users/{user_id}/token", dependencies=[Depends(require_admin_bearer)])
    def admin_issue_user_token(user_id: int):
        token = secrets.token_urlsafe(32)
        db.upsert_user_token(user_id=user_id, token=token)
        return {"user_id": user_id, "token": token}

    @app.post("/v1/admin/reminders/dispatch-due", dependencies=[Depends(require_admin_bearer)])
    async def admin_dispatch_due_reminders():
        if not settings.telegram_bot_token:
            raise HTTPException(status_code=500, detail="Server not configured: TELEGRAM_BOT_TOKEN empty")
        from telegram import Bot

        return await dispatch_due_reminders(db, Bot(token=settings.telegram_bot_token))

    # --- User CRUD (self-scoped via Authorization: Bearer <user token>) ---
    @app.post("/v1/user/reminders")
    def user_create_reminder(
        payload: ReminderCreate,
        user_id: int = Depends(_user_id_dep),
    ) -> Reminder:
        r = db.create_reminder(
            user_id=user_id,
            text=payload.text,
            due_at=_parse_dt(payload.due_at),
            visibility="user",
        )
        return Reminder(**r)

    @app.get("/v1/user/reminders")
    def user_list_reminders(
        include_done: bool = Query(default=True),
        user_id: int = Depends(_user_id_dep),
    ) -> List[Reminder]:
        rows = db.list_reminders_for_user(user_id=user_id, include_done=include_done)
        return [Reminder(**r) for r in rows]

    @app.patch("/v1/user/reminders/{reminder_id}")
    def user_patch_reminder(
        reminder_id: int,
        payload: ReminderUpdate,
        user_id: int = Depends(_user_id_dep),
    ) -> Reminder:
        try:
            r = db.update_user_reminder(
                user_id=user_id,
                reminder_id=reminder_id,
                text=payload.text,
                due_at=_parse_dt(payload.due_at) if payload.due_at is not None else None,
                done=payload.done,
            )
            return Reminder(**r)
        except KeyError:
            raise HTTPException(status_code=404, detail="not found")

    @app.delete("/v1/user/reminders/{reminder_id}")
    def user_delete_reminder(
        reminder_id: int,
        user_id: int = Depends(_user_id_dep),
    ):
        try:
            db.delete_user_reminder(user_id=user_id, reminder_id=reminder_id)
            return {"ok": True}
        except KeyError:
            raise HTTPException(status_code=404, detail="not found")

    @app.post("/v1/telegram/webhook")
    async def telegram_webhook(payload: dict):
        bot = None
        if settings.telegram_bot_token:
            from telegram import Bot

            bot = Bot(token=settings.telegram_bot_token)
        return await handle_webhook_update(db, payload, bot=bot)

    return app
