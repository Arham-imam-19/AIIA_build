"""Make something happen, from the terminal, and watch the dashboards move.

Run with:
    docker compose exec backend python scripts/simulate.py
    docker compose exec backend python scripts/simulate.py adverse-event --serious
    docker compose exec backend python scripts/simulate.py --count 5 --every 4
    docker compose exec backend python scripts/simulate.py --as sponsor   # a 403, on purpose

This is the command-line twin of the "Simulate an event" button in the UI. Same
endpoints, same audit entries, same broadcast - so it is useful when you want the
dashboard on the projector and your hands in a terminal instead of a second tab.

It talks to the running API over HTTP rather than writing to the database
directly, and that is the whole point. A row inserted behind the API's back would
change the numbers but announce nothing: no permission check, no audit entry, and
no event on the bus, so no open dashboard would ever hear about it. Going through
the API means this script proves the same path the browser uses.

Only the standard library is imported, so it also runs on a laptop with nothing
installed:  python scripts/simulate.py --url http://localhost:8000

NEVER point this at anything but the synthetic demo database.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_URL = "http://localhost:8000"

# What each action does, in one line, so the terminal says what to look for on
# screen instead of just "201 Created". Kept word-for-word in step with the
# `moves` strings in backend/app/routers/simulate.py, which label the UI buttons.
ACTIONS = {
    "enrollment": "Screened, Enrolled, % of target, the recruitment curve",
    "adverse-event": "Adverse events, Serious events, Events awaiting coding",
    "deviation": "Protocol deviations, Deviation rate, Visits completed",
}

# Short names for the five personas, because typing "principal_investigator" at a
# demo is a way to mistype it. Only these five are here because only these five
# are published by /api/auth/demo-users; for anyone else, pass --email/--password.
PERSONAS = {
    "pi": "principal_investigator",
    "investigator": "principal_investigator",
    "crc": "coordinator",
    "coordinator": "coordinator",
    "sponsor": "sponsor",
    "ethics": "ethics_committee",
    "regulator": "regulator",
}


# --------------------------------------------------------------------- plumbing


def call(
    base: str,
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
) -> tuple[int, object]:
    """One HTTP call. Returns (status, decoded body) and never raises for a 4xx.

    A 403 is a *result* here, not a crash: `--as sponsor` is a demo step that
    shows a monitor cannot enter trial data.
    """
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        base.rstrip("/") + path, data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw or b"null")
        except ValueError:
            return exc.code, raw.decode(errors="replace")
    except urllib.error.URLError as exc:
        print(f"✗ cannot reach the API at {base}: {exc.reason}")
        print("  Is the stack up? Try: docker compose up -d")
        raise SystemExit(1) from exc


def detail_of(body: object) -> str:
    """The API's explanation for a refusal, whatever shape it arrived in."""
    if isinstance(body, dict) and "detail" in body:
        return str(body["detail"])
    return str(body)


# ------------------------------------------------------------------ signing in


def find_login(base: str, persona: str) -> tuple[str, str]:
    """Look up one demo persona's email and password from the API.

    `/api/auth/demo-users` only answers while APP_ENV=development, which is
    deliberate - a deployed system must not hand out logins. Outside development,
    pass --email and --password yourself.
    """
    status, body = call(base, "GET", "/api/auth/demo-users")
    if status == 404:
        print("✗ the demo-users endpoint is switched off (APP_ENV is not development)")
        print("  Pass the login explicitly: --email <address> --password <password>")
        raise SystemExit(1)
    if status != 200 or not isinstance(body, dict):
        print(f"✗ unexpected reply from /api/auth/demo-users ({status}): {body}")
        raise SystemExit(1)
    if not body.get("seeded"):
        print("✗ there are no users yet. Load the synthetic data first:")
        print("  docker compose exec backend python scripts/seed.py")
        raise SystemExit(1)

    role = PERSONAS[persona]
    for user in body["users"]:
        if user["role"] == role:
            return user["email"], body["password"]

    available = ", ".join(sorted({user["role"] for user in body["users"]}))
    print(f"✗ no seeded user with role {role}. Available: {available}")
    raise SystemExit(1)


def sign_in(base: str, email: str, password: str) -> tuple[str, dict]:
    """Exchange an email and password for an access token."""
    status, body = call(
        base, "POST", "/api/auth/login", payload={"email": email, "password": password}
    )
    if status != 200 or not isinstance(body, dict):
        print(f"✗ login failed for {email}: {detail_of(body)}")
        raise SystemExit(1)
    return body["access_token"], body["user"]


# ------------------------------------------------------------------- the action


def describe(action: str, body: dict) -> str:
    """One line naming the row that was just written."""
    if action == "enrollment":
        row = body["subject"]
        return (
            f"{row['subject_code']} enrolled at site {row['site_code']} "
            f"({row['arm']}, prakriti {row['prakriti']})"
        )
    if action == "adverse-event":
        row = body["adverse_event"]
        kind = "SERIOUS adverse event" if row["is_serious"] else "adverse event"
        return (
            f"{row['ae_number']} - {kind}: {row['term_verbatim']} "
            f"({row['severity']}) for {row['subject_code']}"
        )
    row = body["visit"]
    return (
        f"{row['subject_code']} {row['visit_name']} completed "
        f"{row['days_late']} days late - logged as a protocol deviation"
    )


def fire(base: str, token: str, action: str, *, serious: bool, site_id: int | None) -> bool:
    """Fire one simulated action. Returns True if a row was written."""
    payload: dict = {"serious": serious}
    if site_id is not None:
        payload["site_id"] = site_id

    status, body = call(base, "POST", f"/api/simulate/{action}", token=token, payload=payload)

    if status == 201 and isinstance(body, dict):
        print(f"✓ {describe(action, body)}")
        print("  audit entry written, event broadcast on aiia:events")
        print(f"  watch on screen: {ACTIONS[action]}")
        return True

    if status == 403:
        # Not a failure of the script - a demonstration that permissions hold.
        print(f"• refused (403): {detail_of(body)}")
        print("  That is the rule working: only the site roles enter trial data.")
        return False

    if status == 409:
        print(f"• nothing to do (409): {detail_of(body)}")
        return False

    print(f"✗ unexpected {status}: {detail_of(body)}")
    raise SystemExit(1)


# ----------------------------------------------------------------------- the CLI


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fire simulated trial events so the live dashboards move.",
        epilog="Restore the baseline dataset afterwards with: "
        "python scripts/seed.py --reset",
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="enrollment",
        choices=sorted(ACTIONS),
        help="what to simulate (default: enrollment)",
    )
    parser.add_argument(
        "--serious",
        action="store_true",
        help="adverse-event only: report a serious event, the one that moves the "
        "Ethics Committee and Regulator screens",
    )
    parser.add_argument(
        "--as",
        dest="persona",
        default="coordinator",
        choices=sorted(PERSONAS),
        help="which persona fires it (default: coordinator, the site role that "
        "enters data). Try --as sponsor to see the refusal.",
    )
    parser.add_argument("--email", help="log in as this address instead of a persona")
    parser.add_argument("--password", help="password for --email")
    parser.add_argument(
        "--site-id",
        type=int,
        help="which site to write to; ignored for site-scoped personas, who always "
        "write to their own",
    )
    parser.add_argument(
        "--count", type=int, default=1, metavar="N", help="fire N times (default: 1)"
    )
    parser.add_argument(
        "--every",
        type=float,
        default=3.0,
        metavar="SECONDS",
        help="pause between events when --count > 1 (default: 3)",
    )
    parser.add_argument(
        "--url", default=DEFAULT_URL, help=f"API base URL (default: {DEFAULT_URL})"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base = args.url

    if args.email:
        if not args.password:
            print("✗ --email needs --password")
            return 2
        email, password = args.email, args.password
    else:
        email, password = find_login(base, args.persona)

    token, user = sign_in(base, email, password)
    where = f"site {user['site_id']}" if user.get("site_id") else "all sites"
    print(f"✓ signed in as {user['full_name']} - {user['role_label']} ({where})")
    print()

    written = 0
    for attempt in range(args.count):
        if attempt:
            time.sleep(max(0.0, args.every))
        if fire(base, token, args.action, serious=args.serious, site_id=args.site_id):
            written += 1
        if args.count > 1:
            print()

    # Being polite about the token: it stays valid for hours otherwise, and the
    # audit trail should show the session closing.
    call(base, "POST", "/api/auth/logout", token=token)

    if written:
        print(f"{written} row(s) written. All synthetic. Restore the baseline with:")
        print("  docker compose exec backend python scripts/seed.py --reset")
    return 0


if __name__ == "__main__":
    sys.exit(main())
