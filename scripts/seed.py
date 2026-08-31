"""Fill the database with realistic synthetic trial data.

Run this against an empty database or use --reset to wipe and reseed:

    python scripts/seed.py --reset

The generator lives in `app/synthetic.py` so the same deterministic dataset can
be built anywhere (unit tests, migrations, local dev). This script is the thin
CLI wrapper that opens the session, runs the inserts, and prints the summary.

Passwords: every user in the seed dataset gets the same shared password, set in
`app/config.py` as DEMO_PASSWORD ("aiia2026"). The seed prints the five persona
logins at the end so a developer can copy-paste straight into the UI.
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
    EConsent,
    PatientRequest,
    Site,
    Subject,
    Trial,
    User,
    Visit,
)

# Children first: a table can only be emptied once nothing points into it.
TABLES_IN_DELETE_ORDER = (
    AuditLog,
    EConsent,
    PatientRequest,
    AdverseEvent,
    Visit,
    Subject,
    Site,
    Trial,
    User,
)

# The order the demo logins are printed in, matching the full hierarchy:
# Primary Admin -> Institution Admin -> Researcher (PI & CRC) -> Patient -> Oversight (Sponsor, Ethics, Regulator).
DEMO_ROLE_ORDER = (
    UserRole.ADMIN.value,
    UserRole.INSTITUTION_ADMIN.value,
    UserRole.PRINCIPAL_INVESTIGATOR.value,
    UserRole.COORDINATOR.value,
    UserRole.PATIENT.value,
    UserRole.SPONSOR.value,
    UserRole.ETHICS_COMMITTEE.value,
    UserRole.REGULATOR.value,
)


def _strip_references(row: dict) -> dict:
    """Drop keys prefixed with `_` that the generator uses for foreign-key
    resolution before passing the dict straight to a SQLModel constructor."""
    return {k: v for k, v in row.items() if not k.startswith("_")}


def _demo_hash() -> str:
    """One shared hash used for every synthetic account."""
    return security.hash_password(config.DEMO_PASSWORD)


from sqlalchemy import text


def wipe(session: Session) -> None:
    """Empty every application table in dependency order."""
    session.exec(text("UPDATE users SET subject_id = NULL, site_id = NULL"))
    session.exec(text("UPDATE subjects SET assigned_researcher_id = NULL, user_id = NULL"))
    session.exec(text("UPDATE trials SET activated_by_user_id = NULL"))
    session.commit()
    for model in TABLES_IN_DELETE_ORDER:
        session.exec(delete(model))  # type: ignore[call-overload]
    session.commit()


def seed(
    session: Session,
    reference_date: date | None = None,
    random_seed: int = synthetic.DEFAULT_SEED,
) -> dict:
    """Run the synthetic generator and commit the rows.

    Returns the summary dict with entity counts.
    """
    data = synthetic.generate(reference_date=reference_date, random_seed=random_seed)

    # ----------------------------------------------------------------- trial
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
    user_obj_by_email: dict[str, User] = {}
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
        user_obj_by_email[user.email] = user

    trial.activated_by_user_id = user_id_by_email[
        data["trial"]["_activated_by_email"]
    ]
    session.add(trial)
    session.flush()

    # ------------------------------------------------------------- subjects
    subject_id_by_code: dict[str, int] = {}
    subject_site_by_code: dict[str, int] = {}
    for row in data["subjects"]:
        site_code = row["_site_code"]
        site_id = site_id_by_code[site_code]
        # Lead researcher for this site (the PI)
        pi_spec = next((s for s in data["sites"] if s["site_code"] == site_code), None)
        pi_user_id = user_id_by_email.get(pi_spec["pi_email"]) if pi_spec else None

        subject = Subject(
            trial_id=trial_id,
            site_id=site_id,
            assigned_researcher_id=pi_user_id,
            **_strip_references(row),
        )
        session.add(subject)
        session.flush()
        subject_id_by_code[subject.subject_code] = subject.id  # type: ignore[index]
        subject_site_by_code[subject.subject_code] = site_id

    # Link demo patient accounts to their respective Subject records
    for row in data["users"]:
        if row.get("_subject_code") and row["_subject_code"] in subject_id_by_code:
            subj_id = subject_id_by_code[row["_subject_code"]]
            user_obj = user_obj_by_email[row["email"]]
            user_obj.subject_id = subj_id
            session.add(user_obj)
            # Also update subject.user_id
            subj_obj = session.get(Subject, subj_id)
            if subj_obj:
                subj_obj.user_id = user_obj.id
                session.add(subj_obj)
    session.flush()

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

    # ----------------------------------------------------- patient requests
    for row in data.get("patient_requests", []):
        patient_uid = user_id_by_email.get(row["_patient_email"])
        admin_uid = user_id_by_email.get(row.get("_assigned_admin_email"))
        site_id = site_id_by_code.get(row["_site_code"], 1)
        subj_id = subject_id_by_code.get(row.get("_subject_code"))
        if patient_uid:
            req = PatientRequest(
                site_id=site_id,
                trial_id=trial_id,
                patient_user_id=patient_uid,
                subject_id=subj_id,
                assigned_admin_id=admin_uid,
                **_strip_references(row),
            )
            session.add(req)

    # ----------------------------------------------------------- e-consents
    for row in data.get("econsents", []):
        subj_code = row["_subject_code"]
        subj_id = subject_id_by_code.get(subj_code)
        site_id = site_id_by_code.get(row["_site_code"], 1)
        subj_obj = session.get(Subject, subj_id) if subj_id else None
        user_uid = subj_obj.user_id if (subj_obj and subj_obj.user_id) else user_id_by_email.get("patient.01.014@demo.aiia-ctms.in", 1)
        if subj_id:
            econsent = EConsent(
                trial_id=trial_id,
                site_id=site_id,
                subject_id=subj_id,
                user_id=user_uid,
                **_strip_references(row),
            )
            session.add(econsent)

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
    return data["summary"] | {"reference_date": data["reference_date"], "trial": data["trial"]}


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
        ("patient requests", PatientRequest),
        ("e-consents", EConsent),
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
    print(f"  {'subjects enrolled':<20} {len(enrolled):>6}")
    print(f"  {'serious AEs':<20} {len(serious):>6}")
    print(f"  {'protocol deviations':<20} {len(deviations):>6}")
    print()


def print_demo_logins(session: Session) -> None:
    """Print one working login for each of the five personas.

    The password is the same for all of them, so a presenter only has to remember
    one string during a demo.
    """
    users = session.exec(select(User).order_by(User.id)).all()
    if not users:
        print("  no users in database; run seed first\n")
        return

    # One login per role: the first user found for each, which matches what
    # DEMO_ROLE_ORDER defines.
    by_role: dict[str, User] = {}
    for user in users:
        if user.role in DEMO_ROLE_ORDER and user.role not in by_role:
            by_role[user.role] = user

    print("\n  demo persona logins  (password for all: %s)" % config.DEMO_PASSWORD)
    print("  " + "-" * 62)
    for role in DEMO_ROLE_ORDER:
        user = by_role.get(role)
        if not user:
            continue
        role_label = user.role.replace("_", " ").title()
        site_note = (
            "site %02d" % user.site_id
            if user.site_id
            else "all sites"
        )
        print(f"  {role_label:<25} {user.email:<36} ({site_note})")
    print("  " + "-" * 62)
    print("  every account is synthetic; none contains real patient data.\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the AIIA CTMS database with synthetic Phase 1 data."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe all existing data before seeding.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Do not insert anything; just print row counts.",
    )
    parser.add_argument(
        "--passwords",
        action="store_true",
        help="Do not insert anything; just print the demo login credentials.",
    )
    parser.add_argument(
        "--date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="Reference date for synthetic generation (YYYY-MM-DD, default today).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=synthetic.DEFAULT_SEED,
        help=f"PRNG seed (default {synthetic.DEFAULT_SEED}).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    engine = get_engine()
    ok, error = check_database()
    if not ok:
        print(f"Database error: {error}")
        sys.exit(1)

    with Session(engine) as session:
        if args.report_only:
            report(session)
            return

        if args.passwords:
            print_demo_logins(session)
            return

        has_trials = session.exec(select(Trial.id)).first() is not None

        if has_trials and not args.reset:
            print(
                "\n  database already contains data. Use --reset to wipe and re-seed, "
                "or --report-only to inspect.\n"
            )
            report(session)
            print_demo_logins(session)
            return

        if args.reset:
            print("\n  wiping existing data...")
            wipe(session)

        print(f"\n  generating synthetic dataset (seed={args.seed})...")
        summary = seed(session, reference_date=args.date, random_seed=args.seed)

        print(f"  seeded trial: {summary['trial']['protocol_number']}")
        report(session)
        print_demo_logins(session)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
