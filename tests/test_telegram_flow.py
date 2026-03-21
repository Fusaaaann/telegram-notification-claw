from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone

from src.db import ReminderDB
from src.storage import LocalStorage
from src.telegram_bot import bind_chat_for_start, dispatch_due_reminders, handle_webhook_update, parse_start_token


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))


class TelegramFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db = ReminderDB(LocalStorage(local_path=f"{self.tmpdir.name}/reminders.sqlite3"))

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    async def test_start_token_binds_chat_and_due_dispatch_marks_done(self) -> None:
        self.db.upsert_user_token(user_id=42, token="user-token")
        reminder = self.db.create_reminder(
            user_id=42,
            text="pay rent",
            due_at="2026-03-22T00:00:00Z",
            visibility="user",
        )
        bot = FakeBot()

        webhook_result = await handle_webhook_update(
            self.db,
            {
                "message": {
                    "text": "/start user-token",
                    "chat": {"id": 9001},
                    "from": {"id": 1111},
                }
            },
            bot=bot,
        )

        self.assertEqual(webhook_result["user_id"], 42)
        self.assertEqual(self.db.get_chat_id(42), 9001)
        self.assertIn((9001, "ok, token linked; this chat will receive reminders."), bot.messages)

        dispatch_result = await dispatch_due_reminders(
            self.db,
            bot,
            now=datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(dispatch_result["sent"], 1)
        self.assertEqual(dispatch_result["skipped_unbound"], 0)
        stored = self.db.get_reminder(reminder_id=int(reminder["id"]))
        self.assertEqual(int(stored["done"]), 1)
        self.assertIn((9001, "pay rent"), bot.messages)

    async def test_start_command_accepts_bot_name_suffix(self) -> None:
        self.assertEqual(parse_start_token("/start@ReminderBot user-token"), "user-token")

        self.db.upsert_user_token(user_id=55, token="user-token")
        webhook_result = await handle_webhook_update(
            self.db,
            {
                "message": {
                    "text": "/start@ReminderBot user-token",
                    "chat": {"id": 9055},
                }
            },
            bot=FakeBot(),
        )

        self.assertEqual(webhook_result["user_id"], 55)
        self.assertEqual(self.db.get_chat_id(55), 9055)

    async def test_start_without_token_is_rejected(self) -> None:
        bot = FakeBot()

        webhook_result = await handle_webhook_update(
            self.db,
            {
                "message": {
                    "text": "/start",
                    "chat": {"id": 9002},
                }
            },
            bot=bot,
        )

        self.assertIsNone(webhook_result["user_id"])
        self.assertEqual(self.db.list_chat_bindings(), [])
        self.assertIn((9002, "Missing start token. Use /start <user-token>."), bot.messages)

    async def test_due_dispatch_respects_offset_aware_due_at(self) -> None:
        self.db.upsert_chat_binding(user_id=7, chat_id=7007)
        self.db.create_reminder(
            user_id=7,
            text="offset-aware reminder",
            due_at="2026-03-22T08:00:00+08:00",
            visibility="user",
        )
        bot = FakeBot()

        before_due = await dispatch_due_reminders(
            self.db,
            bot,
            now=datetime(2026, 3, 21, 23, 59, 59, tzinfo=timezone.utc),
        )
        self.assertEqual(before_due["sent"], 0)

        at_due = await dispatch_due_reminders(
            self.db,
            bot,
            now=datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(at_due["sent"], 1)
        self.assertIn((7007, "offset-aware reminder"), bot.messages)

    async def test_global_reminders_broadcast_to_all_bound_chats(self) -> None:
        self.db.upsert_chat_binding(user_id=1, chat_id=1001)
        self.db.upsert_chat_binding(user_id=2, chat_id=2002)
        reminder = self.db.create_reminder(
            user_id=None,
            text="system maintenance",
            due_at="2026-03-22T00:00:00Z",
        )
        bot = FakeBot()

        result = await dispatch_due_reminders(
            self.db,
            bot,
            now=datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result["sent"], 1)
        self.assertIn((1001, "system maintenance"), bot.messages)
        self.assertIn((2002, "system maintenance"), bot.messages)
        stored = self.db.get_reminder(reminder_id=int(reminder["id"]))
        self.assertEqual(int(stored["done"]), 1)


if __name__ == "__main__":
    unittest.main()
