Reproduce steps (experiment)

Scope: this document is a human/operator checklist to reproduce the experiment end-to-end on a Unix machine.

Important: do not run the install/deploy scripts in this repo unless you intentionally choose to; they are templates.

1) Prepare environment

- Create a Python venv (or use system Python).
- Install Python dependencies from requirements.txt.

2) Configure server-side .env

Create a .env file in the repo root with at least:

- TELEGRAM_BOT_TOKEN
- REMINDER_ADMIN_TOKEN
- REMINDER_DB_PATH (optional; defaults to ./data/reminders.sqlite3)
- REMINDER_API_HOST, REMINDER_API_PORT (optional)

3) Start the service (single-process experiment mode)

- Run the bot + API together using src/app.py.
- Confirm health endpoint returns ok.

4) Bind a target user (Telegram)

- The target user must send /start to the bot once.
- This stores (telegram user_id -> chat_id) in SQLite so outbound reminders can be delivered.

5) Admin CRUD reminders on behalf of the target user

- Set client-side env values for the local CLI:
  - REMINDER_API_BASE_URL
  - REMINDER_BEARER_TOKEN (admin token)
  - REMINDER_SCOPE_USER_ID (target telegram user_id)

- Use the CLI to create/list/update/delete reminders.

6) Optional: issue a per-user bearer token

- Admin issues a token for a specific user_id.
- The user can then call the user endpoints with Authorization: Bearer <user token>.

7) Use-case reproduction: rent reminder schedule

- See docs/usecase_tenant_rent_2026.md for a worked schedule and the corresponding CLI admin-create commands.

8) Missing piece (intentional)

This experiment currently persists reminders and can send messages manually, but it does NOT yet include a background scheduler/worker that:

- periodically scans for due reminders
- sends Telegram messages at due_at
- marks them done

To make reminders actually fire automatically, add a simple worker (cron/systemd timer or a loop) that:

- queries DB for due reminders
- sends via Telegram bot
- updates done status

