"""Load a realistic SYNTHETIC Ayurveda clinical trial into the database.

Run with:
    docker compose exec backend python scripts/seed.py
    docker compose exec backend python scripts/seed.py --reset      # wipe first
    docker compose exec backend python scripts/seed.py --passwords  # logins only
    docker compose exec backend python scripts/seed.py --date 2026-08-25

NEVER put real patient data in here. Everything loaded must be synthetic.

What this script is, and is not
-------------------------------
It is a thin translator. All the interesting decisions - how many people
enrolled, when their visits fell, which adverse events happened - live in
`app/synthetic.py`, which is pure Python and unit-tested without a database.

This file does exactly two things that module cannot:

1. Insert the dictionaries as rows, parents before children.
2. Turn natural keys into integer ids. The generator says "this visit belongs to
   subject AIIA-ASH-02-014" because it cannot know that subject will end up as
   id 137. Every key starting with an underscore is one of these references.

Phase 2 added a third: give every seeded user a password hash so the five personas
can actually log in, and print those logins at the end so a demo needs no
guesswork.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime

from sqlmodel import Session, delete, select

from app import config, security, synthetic
from app.db import check_database, get_engine
from app.enums import UserRole
from app.models import (
    AdverseEvent,
    AuditLog,
    Site,
    Subject,
    Trial,
    User,
    Visit,
)

# Children first: a table can only be emptied once nothing points into it.
TABLES_IN_DELETE_ORDER = (AuditLog, AdverseEvent, Visit, Subject, User, Site, Trial)

# The order the demo logins are printed in, which is also the order to walk them
# in a presentation: from the person entering the data outwards to the person
# inspecting it.
DEMO_ROLE_ORDER = (
    UserRole.PRINCIPAL_INVESTIGATOR.value,
    UserRole.COORDINATOR.value,
    UserRole.SPONSOR.value,
    UserRole.ETHICS_COMMITTEE.value,
    UserRole.REGULATOR.value,
)


def _strip_references(row: dict) -> dict:
    """Drop the underscore-prefixed natural keys, keeping only real columns."""
    return {key: value for key, value in row.items() if not key.startswith("_")}


def already_seeded(session: Session) -> Trial | None:
    """Return the existing trial, if this database has been seeded before."""
    return session.exec(select(Trial)).first()


def wipe(session: Session) -> None:
    """Empty every table.

    Note this deletes the audit trail, which a real regulated system must never
    allow. It is acceptable here only because the whole database is synthetic
    demonstration data that gets rebuilt from scratch.
    """
    for model in TABLES_IN_DELETE_ORDER:
        session.exec(delete(model))
    session.commit()


def _demo_hash() -> str:
    """One bcrypt hash of the shared demo password, computed once.

    bcrypt is deliberately slow - that is the whole point of it - so hashing the
    same string twelve times would add three seconds to every seed for no benefit.
    Every demo user shares one password, so they share one hash.

    In a real system each user's password gets its own random salt and therefore
    its own hash. Here the twelve rows are identical, and that is fine precisely
    because none of these people exist.
    """
    return security.hash_password(config.DEMO_PASSWORD)


def set_demo_passwords(session: Session) -> int:
    """Give every user without a password the shared demo one. Returns how many.

    Separate from `seed()` so an already-seeded database can be brought up to
    Phase 2 without throwing away its data - which matters if you seeded before
    authentication existed.
    """
    users = session.exec(select(User).where(User.hashed_password.is_(None))).all()  # type: ignore[union-attr]
    if not users:
        return 0
    shared = _demo_hash()
    for user in users:
        user.hashed_password = shared
        session.add(user)
    session.commit()
    return len(users)


def demo_logins(session: Session) -> list[User]:
    """One user per persona, in presentation order.

    Picks the lowest id for each role, so the same person turns up every run and a
    rehearsed demo does not change under you.
    """
    chosen: list[User] = []
    for role in DEMO_ROLE_ORDER:
        user = session.exec(
            select(User)
            .where(User.role == role, User.hashed_password.is_not(None))  # type: ignore[union-attr]
            .order_by(User.id)
        ).first()
        if user is not None:
            chosen.append(user)
    return chosen


def print_demo_logins(session: Session) -> None:
    """Print the five personas' credentials - the whole point of the exercise."""
    users = demo_logins(session)
    if not users:
        print("\n  no users with passwords yet; run: python scripts/seed.py --passwords")
        return

    sites = {
        site.id: f"{site.site_code} {site.city}"
        for site in session.exec(select(Site)).all()
    }

    print("\n  demo logins - password is the same for everyone")
    print("  " + "-" * 74)
    print(f"  {'role':<26} {'email':<38} {'site'}")
    print("  " + "-" * 74)
    for user in users:
        scope = sites.get(user.site_id, "all sites") if user.site_id else "all sites"
        print(f"  {user.role.replace('_', ' '):<26} {user.email:<38} {scope}")
    print("  " + "-" * 74)
    print(f"  password: {config.DEMO_PASSWORD}")
    print("  Set a different one with DEMO_PASSWORD in .env before seeding.")
    print("  There is one more account, role 'admin', which sees everything:")
    admin = session.exec(
        select(User).where(User.role == UserRole.ADMIN.value).order_by(User.id)
    ).first()
    if admin is not None:
        print(f"    {admin.email}")


def seed(session: Session, reference_date: date | None, random_seed: int) -> dict:
    """Insert a whole synthetic trial and return the counts that were written."""
    data = synthetic.generate(reference_date=reference_date, random_seed=random_seed)

    # ---------------------------------------------------------------- trial
    trial = Trial(**_strip_references(data["trial"]))
    session.add(trial)
    # flush sends the INSERT so the database assigns an id, without ending the
    # transaction. If a later step fails, the whole seed still rolls back.
    session.flush()
    trial_id: int = trial.id  # type: ignore[assignment]

    # ---------------------------------------------------------------- sites
    site_id_by_code: dict[str, int] = {}
    for row in data["sites"]:
        site = Site(trial_id=trial_id, **_strip_references(row))
        session.add(site)
        session.flush()
        site_id_by_code[site.site_code] = site.id  # type: ignore[index]

    # ---------------------------------------------------------------- users
    # Every seeded user can log in from the moment the seed finishes. The
    # generator does not know or care about passwords, so they are attached here.
    shared_password_hash = _demo_hash()
    user_id_by_email: dict[str, int] = {}
    user_role_by_email: dict[str, str] = {}
    for row in data["users"]:
        user = User(
            site_id=site_id_by_code.get(row["_site_code"]),
            hashed_password=shared_password_hash,
            **_strip_references(row),
        )
        session.add(user)
        session.flush()
        user_id_by_email[user.email] = user.id  # type: ignore[index]
        user_role_by_email[user.email] = user.role

    # ------------------------------------------------------------- subjects
    subject_id_by_code: dict[str, int] = {}
    subject_site_by_code: dict[str, int] = {}
    for row in data["subjects"]:
        site_id = site_id_by_code[row["_site_code"]]
        subject = Subject(trial_id=trial_id, site_id=site_id, **_strip_references(row))
        session.add(subject)
        session.flush()
        subject_id_by_code[subject.subject_code] = subject.id  # type: ignore[index]
        subject_site_by_code[subject.subject_code] = site_id

    # --------------------------------------------------------------- visits
    for row in data["visits"]:
        visit = Visit(
            trial_id=trial_id,
            subject_id=subject_id_by_code[row["_subject_code"]],
            performed_by_user_id=user_id_by_email.get(row["_performed_by_email"]),
            **_strip_references(row),
        )
        session.add(visit)

    # ------------------------------------------------------- adverse events
    for row in data["adverse_events"]:
        subject_code = row["_subject_code"]
        event = AdverseEvent(
            trial_id=trial_id,
            subject_id=subject_id_by_code[subject_code],
            site_id=subject_site_by_code[subject_code],
            reported_by_user_id=user_id_by_email.get(row["_reported_by_email"]),
            **_strip_references(row),
        )
        session.add(event)

    # Flush so the audit entries below can look up the ids just assigned.
    session.flush()

    # ------------------------------------------------------------ audit log
    # An audit entry names the record it is about. Resolve entity_label back to
    # the row's id, so the audit view in the UI can link straight to it.
    entity_ids: dict[tuple[str, str], int] = {}
    for code, subject_id in subject_id_by_code.items():
        entity_ids[("subjects", code)] = subject_id
    for event_id, ae_number in session.exec(
        select(AdverseEvent.id, AdverseEvent.ae_number)
    ).all():
        entity_ids[("adverse_events", ae_number)] = event_id
    entity_ids[("trials", trial.protocol_number)] = trial_id

    for row in data["audit_logs"]:
        email = row["_user_email"]
        session.add(
            AuditLog(
                user_id=user_id_by_email.get(email),
                # Copied in as text so the entry still names who acted even if
                # the user record is later changed or deactivated.
                user_email=email,
                user_role=user_role_by_email.get(email),
                trial_id=trial_id,
                entity_id=entity_ids.get(
                    (row["entity_type"], row.get("entity_label", ""))
                ),
                **_strip_references(row),
            )
        )

    session.commit()
    return data["summary"] | {"reference_date": data["reference_date"]}


def report(session: Session) -> None:
    """Print what is actually in the database now, counted from the tables."""

    def count(model) -> int:
        return len(session.exec(select(model.id)).all())

    print("\n  in the database now")
    print("  " + "-" * 46)
    for label, model in (
        ("trials", Trial),
        ("sites", Site),
        ("users", User),
        ("subjects", Subject),
        ("visits", Visit),
        ("adverse events", AdverseEvent),
        ("audit entries", AuditLog),
    ):
        print(f"  {label:<20} {count(model):>6}")

    enrolled = session.exec(
        select(Subject.id).where(Subject.enrollment_date.is_not(None))  # type: ignore[union-attr]
    ).all()
    serious = session.exec(
        select(AdverseEvent.id).where(AdverseEvent.is_serious == True)  # noqa: E712
    ).all()
    deviations = session.exec(
        select(Visit.id).where(Visit.is_protocol_deviation == True)  # noqa: E712
    ).all()
    print("  " + "-" * 46)
    print(f"  {'enrolled participants':<20} {len(enrolled):>6}")
    print(f"  {'serious AEs':<20} {len(serious):>6}")
    print(f"  {'protocol deviations':<20} {len(deviations):>6}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the AIIA CTMS database with synthetic trial data."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete all existing rows before seeding (synthetic data only)",
    )
    parser.add_argument(
        "--passwords",
        action="store_true",
        help="only fill in missing login passwords and print the demo logins; "
        "does not touch trial data",
    )
    parser.add_argument(
        "--date",
        dest="reference_date",
        metavar="YYYY-MM-DD",
        help="the date to treat as today; data is generated backwards from it "
        "(default: the real today)",
    )
    parser.add_argument(
        "--seed",
        dest="random_seed",
        type=int,
        default=synthetic.DEFAULT_SEED,
        help=f"random seed, for a reproducible demo (default: {synthetic.DEFAULT_SEED})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    reference_date: date | None = None
    if args.reference_date:
        try:
            reference_date = datetime.strptime(args.reference_date, "%Y-%m-%d").date()
        except ValueError:
            print(f"✗ --date must look like 2026-08-25, got {args.reference_date!r}")
            return 2

    ok, detail = check_database()
    if not ok:
        print(f"✗ cannot reach the database: {detail}")
        print("  Is the stack up? Try: docker compose up -d")
        return 1
    print(f"✓ database reachable ({detail})")

    with Session(get_engine()) as session:
        try:
            existing = already_seeded(session)
        except Exception as exc:  # noqa: BLE001
            print(f"✗ cannot read the trials table: {type(exc).__name__}: {exc}")
            print("  Have the migrations run? Try: docker compose exec backend "
                  "alembic upgrade head")
            return 1

        if existing is not None:
            if args.passwords:
                filled = set_demo_passwords(session)
                if filled:
                    print(f"✓ set the demo password on {filled} user(s)")
                else:
                    print("• every user already has a password; nothing to change")
                print_demo_logins(session)
                return 0

            if not args.reset:
                print(f"• already seeded with {existing.protocol_number}; nothing to do")
                print("  To rebuild from scratch: python scripts/seed.py --reset")
                report(session)
                print_demo_logins(session)
                return 0
            print(f"• --reset given: clearing existing data ({existing.protocol_number})")
            wipe(session)
        elif args.passwords:
            print("• nothing is seeded yet, so there are no users to give passwords to")
            print("  Run without --passwords first: python scripts/seed.py")
            return 1

        print("• generating synthetic trial data...")
        summary = seed(session, reference_date, args.random_seed)

        print(f"✓ seeded, treating {summary['reference_date']} as today")
        report(session)
        print_demo_logins(session)

    print("\n  All data above is synthetic. No real patient data.")
    print("  Log in at:  http://localhost:5173")
    print("  Or by hand: curl -s -X POST http://localhost:8000/api/auth/login \\")
    print("                -H 'Content-Type: application/json' \\")
    print("                -d '{\"email\":\"vikram.desai@demo.aiia-ctms.in\","
          f"\"password\":\"{config.DEMO_PASSWORD}\"}}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
