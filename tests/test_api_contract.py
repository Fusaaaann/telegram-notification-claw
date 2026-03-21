from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient

    import src.api as api_module
    import src.auth as auth_module
    from src.db import ReminderDB
    from src.storage import LocalStorage
    import src.telegram_bot as telegram_bot_module

    HAS_FASTAPI = True
except Exception:
    HAS_FASTAPI = False


@unittest.skipUnless(HAS_FASTAPI, "fastapi test dependencies are not installed")
class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db = ReminderDB(LocalStorage(local_path=f"{self.tmpdir.name}/reminders.sqlite3"))
        self.db.upsert_user_token(user_id=42, token="user-token")
        settings = SimpleNamespace(
            admin_token="admin-token",
            telegram_bot_token="",
            reminder_timezone="UTC",
            zoneinfo=lambda: None,
        )
        self.api_patch = patch.object(api_module, "settings", settings)
        self.auth_patch = patch.object(auth_module, "settings", settings)
        self.telegram_patch = patch.object(telegram_bot_module, "settings", settings)
        self.api_patch.start()
        self.auth_patch.start()
        self.telegram_patch.start()
        self.client = TestClient(api_module.create_api(self.db))

    def tearDown(self) -> None:
        self.api_patch.stop()
        self.auth_patch.stop()
        self.telegram_patch.stop()
        self.tmpdir.cleanup()

    def test_admin_get_user_visible_requires_matching_scope(self) -> None:
        reminder = self.db.create_reminder(user_id=42, text="pay rent", due_at=None, visibility="user")

        response = self.client.get(
            f"/v1/admin/reminders/{reminder['id']}",
            headers={"Authorization": "Bearer admin-token"},
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.get(
            f"/v1/admin/reminders/{reminder['id']}",
            headers={
                "Authorization": "Bearer admin-token",
                "X-Reminder-User-Id": "42",
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_user_list_includes_global_and_own_user_reminders(self) -> None:
        self.db.create_reminder(user_id=None, text="system maintenance", due_at=None, visibility="global")
        self.db.create_reminder(user_id=42, text="pay rent", due_at=None, visibility="user")

        response = self.client.get(
            "/v1/user/reminders",
            headers={"Authorization": "Bearer user-token"},
        )
        self.assertEqual(response.status_code, 200)
        texts = [row["text"] for row in response.json()]
        self.assertIn("system maintenance", texts)
        self.assertIn("pay rent", texts)


if __name__ == "__main__":
    unittest.main()
