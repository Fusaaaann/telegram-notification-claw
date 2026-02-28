from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlencode

from dotenv import load_dotenv

from .datecalc import parse_due_at, to_iso


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _request(method: str, url: str, bearer: str, headers: dict[str, str] | None = None, body: dict | None = None):
    hdrs = {"Accept": "application/json"}
    if bearer:
        hdrs["Authorization"] = f"Bearer {bearer}"
    if headers:
        hdrs.update(headers)

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return None
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if hasattr(e, "read") else ""
        msg = raw or str(e)
        raise SystemExit(f"HTTP {e.code}: {msg}")


def _due_at_or_none(s: str | None) -> str | None:
    if s is None:
        return None
    try:
        return to_iso(parse_due_at(s))
    except Exception:
        raise SystemExit("Invalid --due-at; use ISO (YYYY-MM-DD or 2026-02-24T10:00:00) or relative (now/today/tomorrow/+3d/+2h/+30m/+1w)")


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    base = _env("REMINDER_API_BASE_URL", "http://127.0.0.1:8088").rstrip("/")
    bearer = _env("REMINDER_BEARER_TOKEN", "")
    scope_user_id = _env("REMINDER_SCOPE_USER_ID", "")

    p = argparse.ArgumentParser(prog="reminderctl")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("health")

    # Admin commands (require REMINDER_SCOPE_USER_ID)
    c = sub.add_parser("admin-create")
    c.add_argument("text")
    c.add_argument("--due-at", default=None)

    l = sub.add_parser("admin-list")
    l.add_argument("--include-done", default="true")

    u = sub.add_parser("admin-update")
    u.add_argument("reminder_id", type=int)
    u.add_argument("--text", default=None)
    u.add_argument("--due-at", default=None)
    u.add_argument("--done", default=None)

    d = sub.add_parser("admin-delete")
    d.add_argument("reminder_id", type=int)

    t = sub.add_parser("admin-issue-user-token")
    t.add_argument("user_id", type=int)

    # User commands (bearer is user token)
    uc = sub.add_parser("user-create")
    uc.add_argument("text")
    uc.add_argument("--due-at", default=None)

    ul = sub.add_parser("user-list")
    ul.add_argument("--include-done", default="true")

    uu = sub.add_parser("user-update")
    uu.add_argument("reminder_id", type=int)
    uu.add_argument("--text", default=None)
    uu.add_argument("--due-at", default=None)
    uu.add_argument("--done", default=None)

    ud = sub.add_parser("user-delete")
    ud.add_argument("reminder_id", type=int)

    args = p.parse_args(argv)

    if args.cmd == "health":
        out = _request("GET", f"{base}/health", bearer)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.cmd.startswith("admin-"):
        if not scope_user_id and args.cmd != "admin-issue-user-token":
            raise SystemExit("REMINDER_SCOPE_USER_ID is required for admin CRUD")

        hdrs = {}
        if scope_user_id:
            hdrs["X-Reminder-User-Id"] = scope_user_id

        if args.cmd == "admin-create":
            out = _request(
                "POST",
                f"{base}/v1/admin/reminders",
                bearer,
                headers=hdrs,
                body={"text": args.text, "due_at": _due_at_or_none(args.due_at)},
            )
        elif args.cmd == "admin-list":
            q = urlencode({"include_done": args.include_done.lower() == "true"})
            out = _request("GET", f"{base}/v1/admin/reminders?{q}", bearer, headers=hdrs)
        elif args.cmd == "admin-update":
            body = {"text": args.text, "due_at": _due_at_or_none(args.due_at) if args.due_at is not None else None}
            if args.done is not None:
                body["done"] = args.done.lower() == "true"
            out = _request("PATCH", f"{base}/v1/admin/reminders/{args.reminder_id}", bearer, headers=hdrs, body=body)
        elif args.cmd == "admin-delete":
            out = _request("DELETE", f"{base}/v1/admin/reminders/{args.reminder_id}", bearer, headers=hdrs)
        elif args.cmd == "admin-issue-user-token":
            out = _request("POST", f"{base}/v1/admin/users/{args.user_id}/token", bearer)
        else:
            raise SystemExit("unknown command")

        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    # user-*
    if args.cmd == "user-create":
        out = _request(
            "POST",
            f"{base}/v1/user/reminders",
            bearer,
            body={"text": args.text, "due_at": _due_at_or_none(args.due_at)},
        )
    elif args.cmd == "user-list":
        q = urlencode({"include_done": args.include_done.lower() == "true"})
        out = _request("GET", f"{base}/v1/user/reminders?{q}", bearer)
    elif args.cmd == "user-update":
        body = {"text": args.text, "due_at": _due_at_or_none(args.due_at) if args.due_at is not None else None}
        if args.done is not None:
            body["done"] = args.done.lower() == "true"
        out = _request("PATCH", f"{base}/v1/user/reminders/{args.reminder_id}", bearer, body=body)
    elif args.cmd == "user-delete":
        out = _request("DELETE", f"{base}/v1/user/reminders/{args.reminder_id}", bearer)
    else:
        raise SystemExit("unknown command")

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
