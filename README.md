# reminder-crud-telegram-bot (experiment)

Goal: run a Vercel-hosted HTTP API for reminder CRUD, Telegram webhook onboarding, and due-reminder dispatch.

Auth is Bearer-style via the standard Authorization header.

## Surfaces

Admin surface (exclusive):

- Authorization: Bearer <REMINDER_ADMIN_TOKEN>
- Admin can CRUD reminders
- `visibility=global` reminders are broadcast to every bound Telegram chat
- `visibility=user` reminders are scoped to one user and require `X-Reminder-User-Id`
- Admin can provision per-user bearer tokens

User surface (self-service):

- Authorization: Bearer <user token>
- Token maps to exactly one Telegram user_id in SQLite
- User can CRUD only their own user-specific reminders
- User list also includes global reminders

## Files

- src/api.py: FastAPI app (admin + user CRUD + dispatch + Telegram webhook)
- src/telegram_bot.py: Telegram helpers for `/start` binding and due-reminder dispatch
- src/db.py: SQLite persistence (reminders, chat_bindings, user_tokens)
- scripts/install_deps.sh|ps1: dependency install scripts (NOT executed)
- cli/reminderctl.py: local CLI that calls the API using bearer token from .env
- skill/reminder-crud/SKILL.md: agent-facing usage notes

## Operational note

A user should send `/start <user-token>` to the bot once so the system links that token's user_id to the Telegram chat/channel used for reminder delivery.

If `/start` is sent without a token, the bot falls back to binding the Telegram sender's numeric Telegram user_id directly.

## Vercel deployment

This repo includes a Vercel entrypoint at `api/index.py` for the FastAPI surface. Telegram onboarding is handled
through the webhook endpoint, and due reminders can be dispatched by calling the admin dispatch endpoint from
Vercel Cron or another scheduler.

Vercel serverless is read-only except for `/tmp`, so persistence is moved to Vercel Blob.

Required env vars for Blob storage:

- `BLOB_READ_WRITE_TOKEN` (recommended to set via Vercel project env)
- `REMINDER_ADMIN_TOKEN`
- `TELEGRAM_BOT_TOKEN`

Optional:

- `REMINDER_BLOB_PATH` (blob pathname; default `reminders.sqlite3`)
- `REMINDER_BLOB_ACCESS` (`private` or `public`, default `private`)
- `REMINDER_BLOB_TOKEN` (explicit token override; otherwise uses `BLOB_READ_WRITE_TOKEN`)
- `REMINDER_DB_PATH` (local sqlite path; default `/tmp/reminders.sqlite3`)
- `REMINDER_TIMEZONE` (timezone name used for naive `due_at` values; default `UTC`)

Note: private Blob access requires the Vercel Python SDK version that supports private storage (`vercel>=0.5.0`).

## Key endpoints

- `POST /v1/admin/reminders`
- `GET /v1/admin/reminders`
- `GET /v1/admin/reminders/{reminder_id}`
- `PATCH /v1/admin/reminders/{reminder_id}`
- `DELETE /v1/admin/reminders/{reminder_id}`
- `POST /v1/admin/users/{user_id}/token`
- `POST /v1/admin/reminders/dispatch-due`
- `POST /v1/user/reminders`
- `GET /v1/user/reminders`
- `PATCH /v1/user/reminders/{reminder_id}`
- `DELETE /v1/user/reminders/{reminder_id}`
- `POST /v1/telegram/webhook`

## Reminder visibility

- `global` is the admin-create default and broadcasts to every bound Telegram chat when due
- `user` is scoped to one user and requires `X-Reminder-User-Id` on admin create/update
- User-token routes always create/update/delete `user` reminders only

## Time semantics

- Store and send `due_at` in ISO 8601
- Offset-aware datetimes are converted to UTC before dispatch checks
- Naive datetimes are interpreted in `REMINDER_TIMEZONE` before conversion to UTC
- `created_at` and `updated_at` are stored in UTC with `Z`

## One-click deploy (local machine)

- Bash: `./scripts/deploy_vercel.sh`
- PowerShell: `./scripts/deploy_vercel.ps1`
