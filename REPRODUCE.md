Reproduce steps (Vercel-first experiment)

Scope: this document is a human/operator checklist to reproduce the Vercel-hosted reminder flow end-to-end.

Important: do not run the install/deploy scripts in this repo unless you intentionally choose to; they are templates.

1) Prepare environment

- Create a Python venv (or use system Python).
- Install Python dependencies from requirements.txt.

2) Configure server-side env

Configure Vercel project env vars with at least:

- TELEGRAM_BOT_TOKEN
- REMINDER_ADMIN_TOKEN
- BLOB_READ_WRITE_TOKEN
- REMINDER_DB_PATH (optional; defaults to /tmp/reminders.sqlite3)
- REMINDER_TIMEZONE (optional; defaults to UTC for naive due_at values)

3) Deploy the API

- Deploy to Vercel using `api/index.py`.
- Confirm `/health` returns `{"ok": true}`.

4) Issue a user token

- Call `POST /v1/admin/users/{user_id}/token` with the admin bearer token.
- Deliver that token to the target Telegram user.

5) Bind the Telegram chat/channel

- The target user sends `/start <user-token>` to the bot.
- This stores `(user_id -> chat_id)` so reminder delivery has a route.

6) Admin CRUD reminders

- Use `visibility=global` for broadcast reminders.
- Use `visibility=user` plus `X-Reminder-User-Id` for one-user reminders.
- The local CLI supports `--visibility` on admin create/update/list.

7) Trigger due reminders

- Call `POST /v1/admin/reminders/dispatch-due` with the admin bearer token.
- In production, wire this endpoint to Vercel Cron or another scheduler.

8) User self-service flow

- The same user token can call the `/v1/user/reminders` endpoints.
- User routes create/update/delete only user-specific reminders, but list output also includes global reminders.

9) Use-case reproduction: rent reminder schedule

- See docs/usecase_tenant_rent_2026.md for a worked schedule and the corresponding CLI admin-create commands.
