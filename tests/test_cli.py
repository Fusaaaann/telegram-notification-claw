from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from cli import reminderctl


class ReminderCtlTests(unittest.TestCase):
    def test_admin_create_defaults_to_global_visibility(self) -> None:
        captured: dict[str, object] = {}

        def fake_request(method: str, url: str, bearer: str, headers=None, body=None):
            captured.update(
                {
                    "method": method,
                    "url": url,
                    "bearer": bearer,
                    "headers": headers or {},
                    "body": body or {},
                }
            )
            return {"ok": True}

        with patch.dict(
            os.environ,
            {
                "REMINDER_API_BASE_URL": "http://127.0.0.1:8088",
                "REMINDER_BEARER_TOKEN": "admin-token",
            },
            clear=False,
        ):
            with patch("cli.reminderctl._request", side_effect=fake_request):
                rc = reminderctl.main(["admin-create", "system maintenance"])

        self.assertEqual(rc, 0)
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["body"]["visibility"], "global")

    def test_admin_user_visibility_requires_scope(self) -> None:
        with patch.dict(
            os.environ,
            {
                "REMINDER_API_BASE_URL": "http://127.0.0.1:8088",
                "REMINDER_BEARER_TOKEN": "admin-token",
            },
            clear=False,
        ):
            with self.assertRaises(SystemExit) as ctx:
                reminderctl.main(["admin-create", "tenant rent", "--visibility", "user"])

        self.assertIn("REMINDER_SCOPE_USER_ID is required", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
