from __future__ import annotations

from fastapi import Header, HTTPException

from .config import settings
from .db import ReminderDB


def _parse_bearer(authorization: str) -> str:
    if not authorization:
        return ""
    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        return ""
    scheme, token = parts[0].strip(), parts[1].strip()
    if scheme.lower() != "bearer":
        return ""
    return token


def require_admin_bearer(
    authorization: str = Header(default="", alias="Authorization"),
) -> None:
    token = _parse_bearer(authorization)
    if not settings.admin_token:
        raise HTTPException(status_code=500, detail="Server not configured: REMINDER_ADMIN_TOKEN empty")
    if token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


def require_scoped_user_id(
    x_reminder_user_id: str = Header(default="", alias="X-Reminder-User-Id"),
) -> int:
    user_id = optional_scoped_user_id(x_reminder_user_id)
    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid X-Reminder-User-Id")
    return user_id


def optional_scoped_user_id(
    x_reminder_user_id: str = Header(default="", alias="X-Reminder-User-Id"),
) -> int | None:
    if not x_reminder_user_id.strip():
        return None
    try:
        user_id = int(x_reminder_user_id)
        if user_id <= 0:
            raise ValueError
        return user_id
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid X-Reminder-User-Id")


def require_user_id_from_bearer(
    db: ReminderDB,
    authorization: str = Header(default="", alias="Authorization"),
) -> int:
    token = _parse_bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    user_id = db.get_user_id_by_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    return user_id
