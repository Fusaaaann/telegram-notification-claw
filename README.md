# reminder-crud-telegram-bot (experiment)

Goal: deploy a Telegram bot to a remote Unix machine and expose an HTTP API that supports reminder CRUD.

Auth is Bearer-style via the standard Authorization header.

## Surfaces

Admin surface (exclusive):

- Authorization: Bearer <REMINDER_ADMIN_TOKEN>
- Admin can CRUD reminders on behalf of a user by also passing X-Reminder-User-Id
- Admin can provision per-user bearer tokens

User surface (self-service):

- Authorization: Bearer <user token>
- Token maps to exactly one Telegram user_id in SQLite
- User can CRUD only their own reminders

## Files

- src/api.py: FastAPI app (admin + user CRUD)
- src/telegram_bot.py: bot polling loop (stores chat_id on /start)
- src/db.py: SQLite persistence (reminders, chat_bindings, user_tokens)
- scripts/install_deps.sh|ps1: dependency install scripts (NOT executed)
- scripts/deploy_ssh.sh|ps1: mock SSH deployment scripts (NOT executed)
- cli/reminderctl.py: local CLI that calls the API using bearer token from .env
- skill/reminder-crud/SKILL.md: agent-facing usage notes

## Operational note

A user must send /start to the bot at least once so the system records (user_id -> chat_id) before outbound messages can be delivered.

## Vercel deployment (API-only)

This repo includes a Vercel entrypoint at `api/index.py` for the FastAPI surface only. The Telegram bot
polling loop is not suitable for Vercel serverless and should be hosted elsewhere or switched to webhooks.
Vercel serverless is read-only except for `/tmp`, so persistence is moved to Vercel Blob.

Required env vars for Blob storage:

- `BLOB_READ_WRITE_TOKEN` (recommended to set via Vercel project env)

Optional:

- `REMINDER_BLOB_PATH` (blob pathname; default `reminders.sqlite3`)
- `REMINDER_BLOB_ACCESS` (`private` or `public`, default `private`)
- `REMINDER_BLOB_TOKEN` (explicit token override; otherwise uses `BLOB_READ_WRITE_TOKEN`)
- `REMINDER_DB_PATH` (local sqlite path; defaults to `/tmp/reminders.sqlite3` when `REMINDER_STORAGE=blob`)

Note: private Blob access requires the Vercel Python SDK version that supports private storage (`vercel>=0.5.0`).

## One-click deploy (local machine)

- Bash: `./scripts/deploy_vercel.sh`
- PowerShell: `./scripts/deploy_vercel.ps1`
