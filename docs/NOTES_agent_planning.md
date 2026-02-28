Agent-side planning note

For recurrence rules (e.g., first Monday of each month) and workday offsets with holiday skipping:

- Agent computes concrete due-at dates.
- Agent writes reminders via reminderctl with absolute ISO dates/datetimes.
- Holiday lists can be acquired via web search and encoded as a set of dates during planning.

This repo includes a worked example schedule in docs/usecase_tenant_rent_2026.md.
