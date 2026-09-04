"""Make something happen, from the terminal, and watch the dashboards move.

Run with:
    docker compose exec backend python scripts/simulate.py
    docker compose exec backend python scripts/simulate.py adverse-event --serious
    docker compose exec backend python scripts/simulate.py --count 5 --every 4
    docker compose exec backend python scripts/simulate.py --as sponsor   # a 403, on purpose
    docker compose exec backend python scripts/simulate.py ethics-revoke  # blocks enrollment
    docker compose exec backend python scripts/simulate.py ethics-approve # unblocks enrollment

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
from datetime import date, timedelta

DEFAULT_URL = "http://localhost:8000"

ACTIONS = {
    "enrollment": "Screened, Enrolled, % of target, the recruitment curve",
    "adverse-event": "Adverse events, Serious events, Events awaiting coding",
    "deviation": "Protocol deviations, Deviation rate, Visits completed",
    "ethics-approve": "IEC Approval Status, Unlocks screening and enrollment across all sites",
    "ethics-revoke": "IEC Approval Status, Blocks screening and enrollment (409 Conflict)",
    "audit-inspect": "Reads ALCOA+ audit trail entries with before/after diffs",
}

PERSONAS = {
    "admin": "admin",
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
    """One HTTP call. Returns (status, decoded body) and never raises for a 4xx."""
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
    """Look up one demo persona's email and password from the API."""
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


# ------------------------------------------------------------------- actions


def handle_ethics_action(base: str, token: str, action: str) -> bool:
    """Simulate ethics approval or revocation."""
    status_t, body_t = call(base, "GET", "/api/trials", token=token)
    trial_id = 1
    if status_t == 200 and isinstance(body_t, dict) and body_t.get("items"):
        trial_id = body_t["items"][0]["id"]

    today = date.today()
    if action == "ethics-approve":
        payload = {
            "ethics_approval_status": "approved",
            "ethics_approval_number": "IEC/AIIA/2026/042",
            "ethics_approval_date": today.isoformat(),
            "ethics_approval_valid_until": (today + timedelta(days=365)).isoformat(),
        }
        status, body = call(base, "PATCH", f"/api/trials/{trial_id}/ethics-approval", token=token, payload=payload)
        if status == 200:
            print(f"✓ Trial {trial_id} ethics status updated to APPROVED (IEC/AIIA/2026/042)")
            print("  Site enrollment gate UNLOCKED; event published to live bus.")
            return True
        print(f"• failed ({status}): {detail_of(body)}")
        return False
    elif action == "ethics-revoke":
        payload = {
            "ethics_approval_status": "pending",
            "ethics_approval_number": None,
            "ethics_approval_date": None,
            "ethics_approval_valid_until": None,
        }
        status, body = call(base, "PATCH", f"/api/trials/{trial_id}/ethics-approval", token=token, payload=payload)
        if status == 200:
            print(f"✓ Trial {trial_id} ethics status updated to PENDING")
            print("  Site enrollment gate LOCKED; doctors are physically blocked from enrolling.")
            return True
        print(f"• failed ({status}): {detail_of(body)}")
        return False
    return False


def handle_audit_inspect(base: str, token: str) -> bool:
    """Retrieve and display latest ALCOA+ audit entries."""
    status, body = call(base, "GET", "/api/audit-log?limit=5", token=token)
    if status == 200 and isinstance(body, dict):
        items = body.get("items", [])
        print(f"✓ Retrieved {len(items)} latest ALCOA+ Audit Log records (Total: {body.get('total')}):")
        for item in items:
            print(f"  - [{item['timestamp'][:19]}] {item['user_email']} ({item['user_role']}) -> {item['action'].upper()} on {item['entity_type']} #{item.get('entity_id')}: {item.get('reason') or '-'}")
        return True
    print(f"• failed to fetch audit log ({status}): {detail_of(body)}")
    return False


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
    if action in ("ethics-approve", "ethics-revoke"):
        return handle_ethics_action(base, token, action)
    if action == "audit-inspect":
        return handle_audit_inspect(base, token)

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
        print(f"• refused (403): {detail_of(body)}")
        print("  That is the rule working: only authorized roles may perform this action.")
        return False

    if status == 409:
        print(f"• blocked / conflict (409): {detail_of(body)}")
        return False

    print(f"✗ unexpected {status}: {detail_of(body)}")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", nargs="?", default="enrollment", choices=list(ACTIONS.keys()))
    parser.add_argument("--url", default=DEFAULT_URL, help=f"API base URL (default: {DEFAULT_URL})")
    parser.add_argument("--as", dest="persona", default=None, choices=list(PERSONAS.keys()))
    parser.add_argument("--email", help="sign in as this specific email")
    parser.add_argument("--password", help="password for --email")
    parser.add_argument("--serious", action="store_true", help="adverse-event only: mark as serious")
    parser.add_argument("--site-id", type=int, help="site ID (admin only)")
    parser.add_argument("--count", type=int, default=1, help="how many events to fire (default: 1)")
    parser.add_argument("--every", type=float, default=3.0, help="seconds between events (default: 3.0)")
    args = parser.parse_args()

    # Default persona per action
    persona = args.persona
    if not persona and not args.email:
        if args.action in ("ethics-approve", "ethics-revoke"):
            persona = "ethics"
        elif args.action == "audit-inspect":
            persona = "regulator"
        else:
            persona = "coordinator"

    if args.email:
        if not args.password:
            print("✗ --password is required with --email")
            raise SystemExit(2)
        email, password = args.email, args.password
    else:
        email, password = find_login(args.url, persona)

    token, user = sign_in(args.url, email, password)
    print(f"Signed in as: {user['full_name']} <{user['email']}> ({user['role']})")

    for i in range(args.count):
        if i > 0:
            time.sleep(args.every)
        ok = fire(args.url, token, args.action, serious=args.serious, site_id=args.site_id)
        if not ok and args.count > 1:
            print(f"Stopping after iteration {i+1} due to rejection.")
            break


if __name__ == "__main__":
    main()
