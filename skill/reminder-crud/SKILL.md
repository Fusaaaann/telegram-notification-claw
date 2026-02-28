# reminder-crud (local experiment skill)

Use the local CLI (reminderctl) to call the Reminder CRUD HTTP API (v1 endpoints).

The CLI loads configuration from a .env file via python-dotenv.

Client-side .env variables:

- REMINDER_API_BASE_URL (example: http://127.0.0.1:8088)
- REMINDER_BEARER_TOKEN (Authorization: Bearer <token>)

Admin-on-behalf mode:

- REMINDER_SCOPE_USER_ID (Telegram user_id)

Due-at input (absolute/relative only):

- Absolute: YYYY-MM-DD or ISO datetime like 2026-02-24T10:00:00
- Relative: now, today, tomorrow, +3d, +2h, +30m, +1w

Endpoints (current):

- `GET /health`
- `POST /v1/admin/reminders`
- `GET /v1/admin/reminders`
- `GET /v1/admin/reminders/{reminder_id}`
- `PATCH /v1/admin/reminders/{reminder_id}`
- `DELETE /v1/admin/reminders/{reminder_id}`
- `POST /v1/admin/users/{user_id}/token`
- `POST /v1/user/reminders`
- `GET /v1/user/reminders`
- `PATCH /v1/user/reminders/{reminder_id}`
- `DELETE /v1/user/reminders/{reminder_id}`

Examples:

- python -m cli.reminderctl admin-create "buy milk" --due-at 2026-02-24T10:00:00
- python -m cli.reminderctl admin-create "standup" --due-at +2h
- python -m cli.reminderctl user-create "pay rent" --due-at tomorrow

Note: complex recurrence planning (first Monday, workday offsets, holiday skipping) should be handled by the agent, then passed in as concrete due-at values.
