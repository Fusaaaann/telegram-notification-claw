from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import Settings
from .storage import BlobStorage, StorageBackend


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class ReminderDB:
    def __init__(self, storage: StorageBackend):
        self.storage = storage
        os.makedirs(os.path.dirname(self.storage.local_path) or ".", exist_ok=True)
        self._init()

    @classmethod
    def from_settings(cls, settings: Settings) -> "ReminderDB":
        local_path = settings.db_path or "/tmp/reminders.sqlite3"
        blob_path = settings.blob_path or "reminders.sqlite3"
        access = settings.blob_access or "private"
        blob_storage = BlobStorage(
            local_path=local_path,
            blob_path=blob_path,
            access=access,
            token=settings.blob_token or None,
        )
        return cls(storage=blob_storage)

    @contextmanager
    def _with_conn(self, write: bool):
        self.storage.sync_from_remote()
        conn = sqlite3.connect(self.storage.local_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            if write:
                conn.commit()
        finally:
            conn.close()
            if write:
                self.storage.sync_to_remote()

    def _init(self) -> None:
        with self._with_conn(write=True) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    due_at TEXT NULL,
                    done INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_bindings (
                    user_id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_tokens (
                    user_id INTEGER PRIMARY KEY,
                    token TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    # --- chat binding ---
    def upsert_chat_binding(self, user_id: int, chat_id: int) -> None:
        with self._with_conn(write=True) as conn:
            conn.execute(
                """
                INSERT INTO chat_bindings(user_id, chat_id, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    chat_id=excluded.chat_id
                """,
                (user_id, chat_id, _utcnow_iso()),
            )

    def get_chat_id(self, user_id: int) -> Optional[int]:
        with self._with_conn(write=False) as conn:
            row = conn.execute(
                "SELECT chat_id FROM chat_bindings WHERE user_id=?",
                (user_id,),
            ).fetchone()
            return int(row["chat_id"]) if row else None

    # --- user tokens ---
    def upsert_user_token(self, user_id: int, token: str) -> None:
        with self._with_conn(write=True) as conn:
            conn.execute(
                """
                INSERT INTO user_tokens(user_id, token, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    token=excluded.token
                """,
                (user_id, token, _utcnow_iso()),
            )

    def get_user_id_by_token(self, token: str) -> Optional[int]:
        with self._with_conn(write=False) as conn:
            row = conn.execute(
                "SELECT user_id FROM user_tokens WHERE token=?",
                (token,),
            ).fetchone()
            return int(row["user_id"]) if row else None

    # --- reminders CRUD ---
    def create_reminder(self, user_id: int, text: str, due_at: Optional[str]) -> Dict[str, Any]:
        now = _utcnow_iso()
        with self._with_conn(write=True) as conn:
            cur = conn.execute(
                """
                INSERT INTO reminders(user_id, text, due_at, done, created_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?)
                """,
                (user_id, text, due_at, now, now),
            )
            rid = int(cur.lastrowid)
            row = conn.execute(
                "SELECT * FROM reminders WHERE user_id=? AND id=?",
                (user_id, rid),
            ).fetchone()
            if not row:
                raise KeyError("reminder not found")
            return dict(row)

    def list_reminders(self, user_id: int, include_done: bool = True) -> List[Dict[str, Any]]:
        with self._with_conn(write=False) as conn:
            if include_done:
                rows = conn.execute(
                    "SELECT * FROM reminders WHERE user_id=? ORDER BY id DESC",
                    (user_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reminders WHERE user_id=? AND done=0 ORDER BY id DESC",
                    (user_id,),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_reminder(self, user_id: int, reminder_id: int) -> Dict[str, Any]:
        with self._with_conn(write=False) as conn:
            row = conn.execute(
                "SELECT * FROM reminders WHERE user_id=? AND id=?",
                (user_id, reminder_id),
            ).fetchone()
            if not row:
                raise KeyError("reminder not found")
            return dict(row)

    def update_reminder(
        self,
        user_id: int,
        reminder_id: int,
        text: Optional[str] = None,
        due_at: Optional[str] = None,
        done: Optional[bool] = None,
    ) -> Dict[str, Any]:
        with self._with_conn(write=True) as conn:
            existing = conn.execute(
                "SELECT * FROM reminders WHERE user_id=? AND id=?",
                (user_id, reminder_id),
            ).fetchone()
            if not existing:
                raise KeyError("reminder not found")
            new_text = text if text is not None else existing["text"]
            new_due_at = due_at if due_at is not None else existing["due_at"]
            new_done = int(done) if done is not None else int(existing["done"])
            now = _utcnow_iso()
            conn.execute(
                """
                UPDATE reminders
                SET text=?, due_at=?, done=?, updated_at=?
                WHERE user_id=? AND id=?
                """,
                (new_text, new_due_at, new_done, now, user_id, reminder_id),
            )
            row = conn.execute(
                "SELECT * FROM reminders WHERE user_id=? AND id=?",
                (user_id, reminder_id),
            ).fetchone()
            if not row:
                raise KeyError("reminder not found")
            return dict(row)

    def delete_reminder(self, user_id: int, reminder_id: int) -> None:
        with self._with_conn(write=True) as conn:
            row = conn.execute(
                "SELECT id FROM reminders WHERE user_id=? AND id=?",
                (user_id, reminder_id),
            ).fetchone()
            if not row:
                raise KeyError("reminder not found")
            conn.execute(
                "DELETE FROM reminders WHERE user_id=? AND id=?",
                (user_id, reminder_id),
            )
