from __future__ import annotations

import secrets
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from .auth import require_admin_bearer, require_scoped_user_id, require_user_id_from_bearer
from .db import ReminderDB
from .models import Reminder, ReminderCreate, ReminderUpdate


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
        user_id: int = Depends(require_scoped_user_id),
    ) -> Reminder:
        r = db.create_reminder(user_id=user_id, text=payload.text, due_at=_parse_dt(payload.due_at))
        return Reminder(**r)

    @app.get("/v1/admin/reminders", dependencies=[Depends(require_admin_bearer)])
    def admin_list_reminders(
        include_done: bool = Query(default=True),
        user_id: int = Depends(require_scoped_user_id),
    ) -> List[Reminder]:
        rows = db.list_reminders(user_id=user_id, include_done=include_done)
        return [Reminder(**r) for r in rows]

    @app.get("/v1/admin/reminders/{reminder_id}", dependencies=[Depends(require_admin_bearer)])
    def admin_get_reminder(
        reminder_id: int,
        user_id: int = Depends(require_scoped_user_id),
    ) -> Reminder:
        try:
            r = db.get_reminder(user_id=user_id, reminder_id=reminder_id)
            return Reminder(**r)
        except KeyError:
            raise HTTPException(status_code=404, detail="not found")

    @app.patch("/v1/admin/reminders/{reminder_id}", dependencies=[Depends(require_admin_bearer)])
    def admin_patch_reminder(
        reminder_id: int,
        payload: ReminderUpdate,
        user_id: int = Depends(require_scoped_user_id),
    ) -> Reminder:
        try:
            r = db.update_reminder(
                user_id=user_id,
                reminder_id=reminder_id,
                text=payload.text,
                due_at=_parse_dt(payload.due_at) if payload.due_at is not None else None,
                done=payload.done,
            )
            return Reminder(**r)
        except KeyError:
            raise HTTPException(status_code=404, detail="not found")

    @app.delete("/v1/admin/reminders/{reminder_id}", dependencies=[Depends(require_admin_bearer)])
    def admin_delete_reminder(
        reminder_id: int,
        user_id: int = Depends(require_scoped_user_id),
    ):
        try:
            db.delete_reminder(user_id=user_id, reminder_id=reminder_id)
            return {"ok": True}
        except KeyError:
            raise HTTPException(status_code=404, detail="not found")

    # --- Admin: provision per-user bearer token ---
    @app.post("/v1/admin/users/{user_id}/token", dependencies=[Depends(require_admin_bearer)])
    def admin_issue_user_token(user_id: int):
        token = secrets.token_urlsafe(32)
        db.upsert_user_token(user_id=user_id, token=token)
        return {"user_id": user_id, "token": token}

    # --- User CRUD (self-scoped via Authorization: Bearer <user token>) ---
    @app.post("/v1/user/reminders")
    def user_create_reminder(
        payload: ReminderCreate,
        user_id: int = Depends(_user_id_dep),
    ) -> Reminder:
        r = db.create_reminder(user_id=user_id, text=payload.text, due_at=_parse_dt(payload.due_at))
        return Reminder(**r)

    @app.get("/v1/user/reminders")
    def user_list_reminders(
        include_done: bool = Query(default=True),
        user_id: int = Depends(_user_id_dep),
    ) -> List[Reminder]:
        rows = db.list_reminders(user_id=user_id, include_done=include_done)
        return [Reminder(**r) for r in rows]

    @app.patch("/v1/user/reminders/{reminder_id}")
    def user_patch_reminder(
        reminder_id: int,
        payload: ReminderUpdate,
        user_id: int = Depends(_user_id_dep),
    ) -> Reminder:
        try:
            r = db.update_reminder(
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
            db.delete_reminder(user_id=user_id, reminder_id=reminder_id)
            return {"ok": True}
        except KeyError:
            raise HTTPException(status_code=404, detail="not found")

    return app
