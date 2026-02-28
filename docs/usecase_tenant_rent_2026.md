Tenant rent reminder schedule (2026)

Assumptions: US federal holidays treated as non-workdays (observed dates), weekends are non-workdays.
Each reminder is scheduled for 09:00 local time on the computed remind_on date; message includes the pay-by date.

Holidays used:
- 2026-01-01
- 2026-01-19
- 2026-02-16
- 2026-05-25
- 2026-06-19
- 2026-07-03
- 2026-09-07
- 2026-10-12
- 2026-11-11
- 2026-11-26
- 2026-12-25

Schedule:

Month | Pay by (first Monday) | Reminder send date (3 workdays before)
---|---|---
01 | 2026-01-05 | 2025-12-30
02 | 2026-02-02 | 2026-01-28
03 | 2026-03-02 | 2026-02-25
04 | 2026-04-06 | 2026-04-01
05 | 2026-05-04 | 2026-04-29
06 | 2026-06-01 | 2026-05-27
07 | 2026-07-06 | 2026-06-30
08 | 2026-08-03 | 2026-07-29
09 | 2026-09-07 | 2026-09-02
10 | 2026-10-05 | 2026-09-30
11 | 2026-11-02 | 2026-10-28
12 | 2026-12-07 | 2026-12-02

Suggested reminder text template:
Rent reminder: please pay rent by {PAY_BY_DATE} (first Monday).

Admin-mode CLI commands (set REMINDER_SCOPE_USER_ID to tenant user_id; REMINDER_BEARER_TOKEN=admin token):
python3 -m cli.reminderctl admin-create "Rent reminder: please pay rent by 2026-01-05 (first Monday)." --due-at 2025-12-30
python3 -m cli.reminderctl admin-create "Rent reminder: please pay rent by 2026-02-02 (first Monday)." --due-at 2026-01-28
python3 -m cli.reminderctl admin-create "Rent reminder: please pay rent by 2026-03-02 (first Monday)." --due-at 2026-02-25
python3 -m cli.reminderctl admin-create "Rent reminder: please pay rent by 2026-04-06 (first Monday)." --due-at 2026-04-01
python3 -m cli.reminderctl admin-create "Rent reminder: please pay rent by 2026-05-04 (first Monday)." --due-at 2026-04-29
python3 -m cli.reminderctl admin-create "Rent reminder: please pay rent by 2026-06-01 (first Monday)." --due-at 2026-05-27
python3 -m cli.reminderctl admin-create "Rent reminder: please pay rent by 2026-07-06 (first Monday)." --due-at 2026-06-30
python3 -m cli.reminderctl admin-create "Rent reminder: please pay rent by 2026-08-03 (first Monday)." --due-at 2026-07-29
python3 -m cli.reminderctl admin-create "Rent reminder: please pay rent by 2026-09-07 (first Monday)." --due-at 2026-09-02
python3 -m cli.reminderctl admin-create "Rent reminder: please pay rent by 2026-10-05 (first Monday)." --due-at 2026-09-30
python3 -m cli.reminderctl admin-create "Rent reminder: please pay rent by 2026-11-02 (first Monday)." --due-at 2026-10-28
python3 -m cli.reminderctl admin-create "Rent reminder: please pay rent by 2026-12-07 (first Monday)." --due-at 2026-12-02
