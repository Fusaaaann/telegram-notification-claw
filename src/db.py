from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import Settings
from .storage import BlobStorage, StorageBackend


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
                    visibility TEXT NOT NULL DEFAULT 'user',
                    text TEXT NOT NULL,
                    due_at TEXT NULL,
                    done INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(reminders)").fetchall()}
            if "visibility" not in columns:
                conn.execute("ALTER TABLE reminders ADD COLUMN visibility TEXT NOT NULL DEFAULT 'user'")
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

    def list_chat_bindings(self) -> List[Dict[str, Any]]:
        with self._with_conn(write=False) as conn:
            rows = conn.execute(
                "SELECT user_id, chat_id, created_at FROM chat_bindings ORDER BY user_id ASC"
            ).fetchall()
            return [dict(r) for r in rows]

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
    def create_reminder(
        self,
        user_id: Optional[int],
        text: str,
        due_at: Optional[str],
        visibility: str = "global",
    ) -> Dict[str, Any]:
        now = _utcnow_iso()
        stored_user_id = 0 if visibility == "global" else int(user_id or 0)
        if visibility == "user" and stored_user_id <= 0:
            raise ValueError("user-specific reminders require a user_id")
        with self._with_conn(write=True) as conn:
            cur = conn.execute(
                """
                INSERT INTO reminders(user_id, visibility, text, due_at, done, created_at, updated_at)
                VALUES (?, ?, ?, ?, 0, ?, ?)
                """,
                (stored_user_id, visibility, text, due_at, now, now),
            )
            rid = int(cur.lastrowid)
            row = conn.execute(
                "SELECT * FROM reminders WHERE id=?",
                (rid,),
            ).fetchone()
            if not row:
                raise KeyError("reminder not found")
            return dict(row)

    def get_due_reminders(self) -> List[Dict[str, Any]]:
        """Return all undone reminders with due_at set, across all users. Caller filters by time."""
        with self._with_conn(write=False) as conn:
            rows = conn.execute(
                """
                SELECT * FROM reminders
                WHERE done = 0 AND due_at IS NOT NULL
                ORDER BY due_at ASC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def list_reminders_for_admin(
        self,
        scoped_user_id: Optional[int] = None,
        include_done: bool = True,
        visibility: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self._with_conn(write=False) as conn:
            clauses = []
            params: list[Any] = []
            if scoped_user_id is None:
                clauses.append("visibility='global'")
            else:
                clauses.append("(visibility='global' OR (visibility='user' AND user_id=?))")
                params.append(scoped_user_id)
            if not include_done:
                clauses.append("done=0")
            if visibility:
                clauses.append("visibility=?")
                params.append(visibility)
            query = "SELECT * FROM reminders"
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            query += " ORDER BY id DESC"
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    def list_reminders_for_user(self, user_id: int, include_done: bool = True) -> List[Dict[str, Any]]:
        with self._with_conn(write=False) as conn:
            clauses = ["(visibility='global' OR (visibility='user' AND user_id=?))"]
            params: list[Any] = [user_id]
            if not include_done:
                clauses.append("done=0")
            rows = conn.execute(
                f"SELECT * FROM reminders WHERE {' AND '.join(clauses)} ORDER BY id DESC",
                tuple(params),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_reminder(self, reminder_id: int) -> Dict[str, Any]:
        with self._with_conn(write=False) as conn:
            row = conn.execute(
                "SELECT * FROM reminders WHERE id=?",
                (reminder_id,),
            ).fetchone()
            if not row:
                raise KeyError("reminder not found")
            return dict(row)

    def get_user_visible_reminder(self, user_id: int, reminder_id: int) -> Dict[str, Any]:
        with self._with_conn(write=False) as conn:
            row = conn.execute(
                """
                SELECT * FROM reminders
                WHERE id=? AND (visibility='global' OR (visibility='user' AND user_id=?))
                """,
                (reminder_id, user_id),
            ).fetchone()
            if not row:
                raise KeyError("reminder not found")
            return dict(row)

    def update_admin_reminder(
        self,
        reminder_id: int,
        text: Optional[str] = None,
        due_at: Optional[str] = None,
        done: Optional[bool] = None,
        visibility: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        with self._with_conn(write=True) as conn:
            existing = conn.execute(
                "SELECT * FROM reminders WHERE id=?",
                (reminder_id,),
            ).fetchone()
            if not existing:
                raise KeyError("reminder not found")
            new_text = text if text is not None else existing["text"]
            new_due_at = due_at if due_at is not None else existing["due_at"]
            new_done = int(done) if done is not None else int(existing["done"])
            new_visibility = visibility if visibility is not None else existing["visibility"]
            if new_visibility == "global":
                new_user_id = 0
            else:
                current_user_id = int(existing["user_id"])
                new_user_id = int(user_id if user_id is not None else current_user_id)
                if new_user_id <= 0:
                    raise ValueError("user-specific reminders require a user_id")
            now = _utcnow_iso()
            conn.execute(
                """
                UPDATE reminders
                SET user_id=?, visibility=?, text=?, due_at=?, done=?, updated_at=?
                WHERE id=?
                """,
                (new_user_id, new_visibility, new_text, new_due_at, new_done, now, reminder_id),
            )
            row = conn.execute(
                "SELECT * FROM reminders WHERE id=?",
                (reminder_id,),
            ).fetchone()
            if not row:
                raise KeyError("reminder not found")
            return dict(row)

    def update_user_reminder(
        self,
        user_id: int,
        reminder_id: int,
        text: Optional[str] = None,
        due_at: Optional[str] = None,
        done: Optional[bool] = None,
    ) -> Dict[str, Any]:
        with self._with_conn(write=True) as conn:
            existing = conn.execute(
                "SELECT * FROM reminders WHERE id=? AND visibility='user' AND user_id=?",
                (reminder_id, user_id),
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
                WHERE id=? AND user_id=? AND visibility='user'
                """,
                (new_text, new_due_at, new_done, now, reminder_id, user_id),
            )
            row = conn.execute(
                "SELECT * FROM reminders WHERE id=?",
                (reminder_id,),
            ).fetchone()
            if not row:
                raise KeyError("reminder not found")
            return dict(row)

    def delete_admin_reminder(self, reminder_id: int) -> None:
        with self._with_conn(write=True) as conn:
            row = conn.execute(
                "SELECT id FROM reminders WHERE id=?",
                (reminder_id,),
            ).fetchone()
            if not row:
                raise KeyError("reminder not found")
            conn.execute(
                "DELETE FROM reminders WHERE id=?",
                (reminder_id,),
            )

    def delete_user_reminder(self, user_id: int, reminder_id: int) -> None:
        with self._with_conn(write=True) as conn:
            row = conn.execute(
                "SELECT id FROM reminders WHERE id=? AND user_id=? AND visibility='user'",
                (reminder_id, user_id),
            ).fetchone()
            if not row:
                raise KeyError("reminder not found")
            conn.execute(
                "DELETE FROM reminders WHERE id=? AND user_id=? AND visibility='user'",
                (reminder_id, user_id),
            )
