"""What each role sees on their dashboard.

Five people open the same system and need five different first screens. A
coordinator wants to know which visits are due this week; a regulator wants to
know whether the trial was registered before it enrolled anyone. Neither cares
about the other's question.

Every builder here returns the same shape, so the React side has one renderer
rather than five:

    tiles   the big numbers across the top
    blocks  everything below them, each tagged with a `kind` the UI knows:
              table      rows and columns
              breakdown  a labelled list with proportions
              series     points over time, for a line chart
              checklist  pass/fail items, for compliance gates

Adding a KPI means adding a dict here. No frontend change needed - which is the
point, because Phase 6 is where the visuals get attention, not now.

Every number is computed from the tables on each call. Nothing is cached and
nothing is stored, so a dashboard cannot show a figure the database disagrees
with.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.enums import AEOutcome, AESeverity, SubjectStatus, UserRole, VisitStatus
from app.events import bus
from app.models import AdverseEvent, AuditLog, PatientRequest, Site, Subject, Trial, User, Visit
from app.rbac import CurrentUser, Permission
from app.routers.stats import build_stats, build_timeline, resolve_trial, visits_at_site

# How long a serious adverse event may take to reach the ethics committee before
# it counts as late. India's NDCT Rules 2019 set tight deadlines (an initial
# report within 24 hours, a detailed one within 14 days); a single 7-day window is
# the simplification for this demo, and Phase 5 replaces it with the real gates.
SAE_REPORTING_WINDOW_DAYS = 7

# How far ahead "coming up" means on the coordinator's screen.
UPCOMING_WINDOW_DAYS = 14

# Outcomes that mean an event has not resolved yet, so somebody still has to
# follow it up.
OPEN_OUTCOMES = (AEOutcome.ONGOING.value, AEOutcome.RECOVERING.value)


# --------------------------------------------------------------- small helpers


def _tile(key: str, label: str, value, hint: str | None = None, tone: str = "neutral"):
    """One headline number.

    `tone` is a hint to the UI, not a decision: "good", "warn", "bad" or
    "neutral". Phase 6 decides what those look like.
    """
    return {"key": key, "label": label, "value": value, "hint": hint, "tone": tone}


def _table(key: str, title: str, columns: list[tuple[str, str]], rows: list[dict],
           note: str | None = None, empty: str = "Nothing to show."):
    return {
        "kind": "table",
        "key": key,
        "title": title,
        "note": note,
        "empty": empty,
        "columns": [{"key": k, "label": label} for k, label in columns],
        "rows": rows,
    }


def _breakdown(key: str, title: str, counts: dict[str, int], note: str | None = None):
    """A labelled list with proportions, e.g. participants by status."""
    total = sum(counts.values())
    return {
        "kind": "breakdown",
        "key": key,
        "title": title,
        "note": note,
        "total": total,
        "items": [
            {
                "label": name.replace("_", " "),
                "value": count,
                "percent": round(count * 100 / total, 1) if total else 0.0,
            }
            for name, count in sorted(counts.items(), key=lambda kv: -kv[1])
        ],
    }


def _checklist(key: str, title: str, items: list[dict], note: str | None = None):
    passed = sum(1 for item in items if item["ok"])
    return {
        "kind": "checklist",
        "key": key,
        "title": title,
        "note": note,
        "passed": passed,
        "total": len(items),
        "items": items,
    }


def _check(label: str, ok: bool, detail: str) -> dict:
    return {"label": label, "ok": bool(ok), "detail": detail}


def _percent(part: int, whole: int) -> float:
    return round(part * 100 / whole, 1) if whole > 0 else 0.0


def _site_codes(session: Session, trial_id: int) -> dict[int, str]:
    return {
        site_id: code
        for site_id, code in session.exec(
            select(Site.id, Site.site_code).where(Site.trial_id == trial_id)
        ).all()
    }


def _subject_codes(session: Session, subject_ids: list[int]) -> dict[int, str]:
    """Subject codes for a handful of ids, in one query rather than N."""
    if not subject_ids:
        return {}
    return {
        sid: code
        for sid, code in session.exec(
            select(Subject.id, Subject.subject_code).where(
                Subject.id.in_(subject_ids)  # type: ignore[union-attr]
            )
        ).all()
    }


def _scoped_ae(statement, user: CurrentUser):
    site_id = user.scope_site_id
    return statement if site_id is None else statement.where(AdverseEvent.site_id == site_id)


def _scoped_visits(statement, user: CurrentUser):
    site_id = user.scope_site_id
    return statement if site_id is None else statement.where(visits_at_site(site_id))


def _scoped_subjects(statement, user: CurrentUser):
    site_id = user.scope_site_id
    return statement if site_id is None else statement.where(Subject.site_id == site_id)


def _open_ae_count(session: Session, trial_id: int, user: CurrentUser) -> int:
    statement = select(func.count()).select_from(AdverseEvent).where(
        AdverseEvent.trial_id == trial_id,
        AdverseEvent.outcome.in_(OPEN_OUTCOMES),  # type: ignore[union-attr]
    )
    return int(session.exec(_scoped_ae(statement, user)).one())


def _recent_ae_rows(
    session: Session, trial_id: int, user: CurrentUser, limit: int = 6
) -> list[dict]:
    """The newest adverse events, formatted for a table."""
    statement = (
        select(AdverseEvent)
        .where(AdverseEvent.trial_id == trial_id)
        .order_by(AdverseEvent.onset_date.desc(), AdverseEvent.id.desc())  # type: ignore[union-attr]
        .limit(limit)
    )
    events = list(session.exec(_scoped_ae(statement, user)).all())
    codes = _subject_codes(session, [e.subject_id for e in events])
    sites = _site_codes(session, trial_id)
    return [
        {
            "ae_number": event.ae_number,
            "subject": codes.get(event.subject_id, "?"),
            "site": sites.get(event.site_id, "?"),
            "term": event.term_verbatim,
            "severity": event.severity,
            "serious": "yes" if event.is_serious else "no",
            "causality": event.causality.replace("_", " "),
            "onset": event.onset_date.isoformat() if event.onset_date else None,
            "outcome": event.outcome.replace("_", " "),
        }
        for event in events
    ]


def _sae_reporting(session: Session, trial_id: int, user: CurrentUser) -> dict:
    """Serious events and whether each reached the ethics committee in time.

    This is the compliance question the Ethics Committee and the Regulator both
    ask, so it is computed once and used by both dashboards.
    """
    statement = (
        select(AdverseEvent)
        .where(AdverseEvent.trial_id == trial_id, AdverseEvent.is_serious == True)  # noqa: E712
        .order_by(AdverseEvent.onset_date.desc())  # type: ignore[union-attr]
    )
    events = list(session.exec(_scoped_ae(statement, user)).all())
    codes = _subject_codes(session, [e.subject_id for e in events])
    sites = _site_codes(session, trial_id)

    rows: list[dict] = []
    late = 0
    unreported = 0
    today_eval = date.today()
    for event in events:
        delay: int | None = None
        if event.reported_to_ec_date and event.reported_date:
            delay = (event.reported_to_ec_date - event.reported_date).days
        if not event.reported_to_ec:
            unreported += 1
            verdict = "not reported"
        elif delay is not None and delay > SAE_REPORTING_WINDOW_DAYS:
            late += 1
            verdict = f"late ({delay} days)"
        else:
            verdict = f"on time ({delay} days)" if delay is not None else "on time"

        # NDCT Rules 2019 24h expedited reporting check
        expedited_due = event.onset_date + timedelta(days=1)
        if event.reported_to_ec:
            urgency = "COMPLIANT_SUBMITTED"
        elif today_eval > expedited_due:
            urgency = "EXPEDITED_OVERDUE"
        else:
            urgency = "EXPEDITED_DUE_SOON"

        rows.append(
            {
                "event_id": event.id,
                "ae_number": event.ae_number,
                "subject": codes.get(event.subject_id, "?"),
                "site": sites.get(event.site_id, "?"),
                "term": event.term_verbatim,
                "criteria": event.seriousness_criteria,
                "onset": event.onset_date.isoformat() if event.onset_date else None,
                "reported": event.reported_date.isoformat() if event.reported_date else None,
                "to_ethics": (
                    event.reported_to_ec_date.isoformat()
                    if event.reported_to_ec_date
                    else None
                ),
                "days": delay,
                "urgency": urgency,
                "verdict": verdict,
            }
        )

    total = len(events)
    on_time = total - late - unreported
    return {
        "rows": rows,
        "total": total,
        "late": late,
        "unreported": unreported,
        "on_time": on_time,
        "compliance_percent": _percent(on_time, total),
    }


def _deviation_rows(
    session: Session, trial_id: int, user: CurrentUser, limit: int = 8
) -> list[dict]:
    statement = (
        select(Visit)
        .where(Visit.trial_id == trial_id, Visit.is_protocol_deviation == True)  # noqa: E712
        .order_by(Visit.scheduled_date.desc())  # type: ignore[union-attr]
        .limit(limit)
    )
    visits = list(session.exec(_scoped_visits(statement, user)).all())
    codes = _subject_codes(session, [v.subject_id for v in visits])
    return [
        {
            "subject": codes.get(visit.subject_id, "?"),
            "visit": visit.visit_name,
            "scheduled": visit.scheduled_date.isoformat() if visit.scheduled_date else None,
            "actual": visit.actual_date.isoformat() if visit.actual_date else None,
            "status": visit.status,
            "description": visit.deviation_description or "-",
        }
        for visit in visits
    ]


def _upcoming_visit_rows(
    session: Session, trial_id: int, user: CurrentUser, today: date, limit: int = 10
) -> list[dict]:
    statement = (
        select(Visit)
        .where(
            Visit.trial_id == trial_id,
            Visit.status == VisitStatus.SCHEDULED.value,
            Visit.scheduled_date.is_not(None),  # type: ignore[union-attr]
            Visit.scheduled_date >= today,
        )
        .order_by(Visit.scheduled_date)
        .limit(limit)
    )
    visits = list(session.exec(_scoped_visits(statement, user)).all())
    codes = _subject_codes(session, [v.subject_id for v in visits])
    return [
        {
            "subject": codes.get(visit.subject_id, "?"),
            "visit": visit.visit_name,
            "scheduled": visit.scheduled_date.isoformat() if visit.scheduled_date else None,
            "in_days": (visit.scheduled_date - today).days if visit.scheduled_date else None,
        }
        for visit in visits
    ]


def _count_visits(session: Session, trial_id: int, user: CurrentUser, *conditions) -> int:
    statement = select(func.count()).select_from(Visit).where(Visit.trial_id == trial_id)
    for condition in conditions:
        statement = statement.where(condition)
    return int(session.exec(_scoped_visits(statement, user)).one())


def _screening_rows(
    session: Session, trial_id: int, user: CurrentUser, today: date, limit: int = 10
) -> list[dict]:
    """Participants still in screening - the coordinator's live to-do list."""
    statement = (
        select(Subject)
        .where(
            Subject.trial_id == trial_id,
            Subject.status == SubjectStatus.SCREENING.value,
        )
        .order_by(Subject.screening_date)
        .limit(limit)
    )
    subjects = list(session.exec(_scoped_subjects(statement, user)).all())
    return [
        {
            "subject": subject.subject_code,
            "screened": (
                subject.screening_date.isoformat() if subject.screening_date else None
            ),
            "waiting_days": (
                (today - subject.screening_date).days if subject.screening_date else None
            ),
            "sex": subject.sex,
            "age": subject.age_at_enrollment,
        }
        for subject in subjects
    ]


# ----------------------------------------------------------- the five builders


def _investigator(session, user, stats, trial, today) -> tuple[list, list]:
    """Principal Investigator: my site, clinically. Am I recruiting, and is
    anyone getting hurt?"""
    tid = trial.id
    enrol = stats["enrollment"]
    safety = stats["safety"]
    open_aes = _open_ae_count(session, tid, user)
    due_soon = _count_visits(
        session,
        tid,
        user,
        Visit.status == VisitStatus.SCHEDULED.value,
        Visit.scheduled_date.is_not(None),  # type: ignore[union-attr]
        Visit.scheduled_date >= today,
        Visit.scheduled_date <= today + timedelta(days=UPCOMING_WINDOW_DAYS),
    )
    active = enrol["by_status"].get(SubjectStatus.ACTIVE.value, 0)

    tiles = [
        _tile("screened", "Screened", enrol["screened"],
              f"{enrol['screen_failed']} screen failures"),
        _tile("enrolled", "Enrolled", enrol["enrolled"],
              f"{enrol['percent_of_target']}% of this site's target of {enrol['target']}",
              "good" if enrol["percent_of_target"] >= 80 else "warn"),
        _tile("active", "On treatment", active, "in follow-up now"),
        _tile("open_aes", "Open adverse events", open_aes,
              "ongoing or still recovering",
              "warn" if open_aes else "good"),
        _tile("serious", "Serious events", safety["serious"],
              "hospitalisation, life-threatening or worse",
              "bad" if safety["serious"] else "good"),
        _tile("deviations", "Protocol deviations", stats["visits"]["protocol_deviations"],
              f"{stats['visits']['deviation_rate']}% of visits due"),
        _tile("due_soon", f"Visits due in {UPCOMING_WINDOW_DAYS} days", due_soon,
              "at this site"),
        _tile("uncoded", "Events awaiting coding", safety["awaiting_meddra_coding"],
              "MedDRA queue (Phase 4)"),
    ]

    blocks = [
        _breakdown("by_status", "My participants", enrol["by_status"],
                   "Everyone screened at this site, by where they are now."),
        _table(
            "recent_aes",
            "Latest adverse events at my site",
            [("ae_number", "AE"), ("subject", "Participant"), ("term", "Event"),
             ("severity", "Severity"), ("serious", "Serious"),
             ("causality", "Causality"), ("onset", "Onset")],
            _recent_ae_rows(session, tid, user),
            note="Severity is how intense it was; serious is the regulatory "
                 "category that starts a reporting clock. They are not the same thing.",
            empty="No adverse events reported at this site.",
        ),
        {
            "kind": "series",
            "key": "recruitment",
            "title": "My recruitment curve",
            "note": "Cumulative enrolments per month against this site's target.",
            "x": "month",
            "lines": [
                {"key": "cumulative", "label": "Enrolled (cumulative)"},
                {"key": "target", "label": "Site target"},
            ],
            "points": build_timeline(session, user, tid)["points"],
        },
    ]
    return tiles, blocks


def _coordinator(session, user, stats, trial, today) -> tuple[list, list]:
    """Clinical Research Coordinator: what needs doing this week?"""
    tid = trial.id
    visits = stats["visits"]
    by_status = visits["by_status"]
    overdue = _count_visits(
        session,
        tid,
        user,
        Visit.status == VisitStatus.SCHEDULED.value,
        Visit.scheduled_date.is_not(None),  # type: ignore[union-attr]
        Visit.scheduled_date < today,
    )
    in_screening = stats["enrollment"]["by_status"].get(SubjectStatus.SCREENING.value, 0)
    due_soon = _count_visits(
        session,
        tid,
        user,
        Visit.status == VisitStatus.SCHEDULED.value,
        Visit.scheduled_date.is_not(None),  # type: ignore[union-attr]
        Visit.scheduled_date >= today,
        Visit.scheduled_date <= today + timedelta(days=UPCOMING_WINDOW_DAYS),
    )

    tiles = [
        _tile("due_soon", f"Due in {UPCOMING_WINDOW_DAYS} days", due_soon,
              "book these now", "warn" if due_soon else "neutral"),
        _tile("overdue", "Past their date", overdue,
              "still marked scheduled", "bad" if overdue else "good"),
        _tile("completed", "Visits completed", by_status.get(VisitStatus.COMPLETED.value, 0),
              f"of {visits['total']} in the schedule"),
        _tile("missed", "Visits missed", by_status.get(VisitStatus.MISSED.value, 0),
              "window closed without the visit",
              "bad" if by_status.get(VisitStatus.MISSED.value, 0) else "good"),
        _tile("in_screening", "In screening", in_screening, "awaiting an eligibility decision"),
        _tile("uncoded", "Events to code", stats["safety"]["awaiting_meddra_coding"],
              "no MedDRA term yet"),
        _tile("deviations", "Deviations logged", visits["protocol_deviations"],
              f"{visits['deviation_rate']}% of visits due"),
        _tile("enrolled", "Enrolled here", stats["enrollment"]["enrolled"],
              f"{stats['enrollment']['screened']} screened"),
    ]

    blocks = [
        _table(
            "upcoming",
            "Next appointments",
            [("subject", "Participant"), ("visit", "Visit"),
             ("scheduled", "Scheduled"), ("in_days", "In days")],
            _upcoming_visit_rows(session, tid, user, today),
            note="The protocol's timetable for this site, soonest first.",
            empty="No upcoming visits scheduled at this site.",
        ),
        _table(
            "screening",
            "Waiting on an eligibility decision",
            [("subject", "Participant"), ("screened", "Screened on"),
             ("waiting_days", "Waiting (days)"), ("sex", "Sex"), ("age", "Age")],
            _screening_rows(session, tid, user, today),
            empty="Nobody is mid-screening at this site.",
        ),
        _breakdown("visit_status", "Visit schedule", by_status,
                   "Every visit row for this site's participants."),
    ]
    return tiles, blocks


def _sponsor(session, user, stats, trial, today) -> tuple[list, list]:
    """Sponsor: is the study on track, across every site?"""
    enrol = stats["enrollment"]
    safety = stats["safety"]
    recruiting = sum(
        1 for site in stats["sites"]["detail"] if site["status"] == "recruiting"
    )
    days_left = (trial.planned_end_date - today).days if trial.planned_end_date else None

    tiles = [
        _tile("enrolled", "Enrolled", enrol["enrolled"],
              f"of {enrol['target']} planned",
              "good" if enrol["percent_of_target"] >= 80 else "warn"),
        _tile("percent", "Of target", f"{enrol['percent_of_target']}%",
              "recruitment progress"),
        _tile("screening_rate", "Screening success", f"{enrol['screening_success_rate']}%",
              f"{enrol['screened']} screened, {enrol['screen_failed']} failed"),
        _tile("sites", "Sites recruiting", f"{recruiting} / {stats['sites']['total']}",
              "actively enrolling"),
        _tile("aes", "Adverse events", safety["adverse_events"],
              f"{safety['percent_of_enrolled_with_ae']}% of participants affected"),
        _tile("serious", "Serious events", safety["serious"],
              "reportable to the ethics committee",
              "bad" if safety["serious"] else "good"),
        _tile("deviation_rate", "Deviation rate", f"{stats['visits']['deviation_rate']}%",
              f"{stats['visits']['protocol_deviations']} of "
              f"{stats['visits']['due_so_far']} visits due"),
        _tile("days_left", "Days to planned end",
              days_left if days_left is not None else "-",
              trial.planned_end_date.isoformat() if trial.planned_end_date else "no end date"),
    ]

    blocks = [
        _table(
            "site_performance",
            "Site performance",
            [("site_code", "Site"), ("name", "Institute"), ("city", "City"),
             ("screened", "Screened"), ("enrolled", "Enrolled"),
             ("target_enrollment", "Target"), ("percent_of_target", "% of target"),
             ("status", "Status")],
            stats["sites"]["detail"],
            note="Recruitment is uneven on purpose - a sponsor's first job is to "
                 "notice which site needs help.",
        ),
        {
            "kind": "series",
            "key": "recruitment",
            "title": "Cumulative enrolment",
            "note": "The curve a sponsor lives in. A flattening line is the first "
                    "sign the trial will miss its recruitment deadline.",
            "x": "month",
            "lines": [
                {"key": "cumulative", "label": "Enrolled (cumulative)"},
                {"key": "target", "label": "Target"},
            ],
            "points": build_timeline(session, user, trial.id)["points"],
        },
        _breakdown("by_arm", "Randomisation balance", stats["by_arm"],
                   "Groups should come out roughly even. A lopsided split is worth "
                   "explaining before the analysis, not after."),
    ]
    return tiles, blocks


def _ethics(session, user, stats, trial, today) -> tuple[list, list]:
    """Ethics Committee: is this study still safe and still being run properly?"""
    tid = trial.id
    safety = stats["safety"]
    sae = _sae_reporting(session, tid, user)
    severe = safety["by_severity"].get(AESeverity.SEVERE.value, 0)

    tiles = [
        _tile("serious", "Serious events", sae["total"],
              "each one is reportable to this committee",
              "bad" if sae["total"] else "good"),
        _tile("reported_late", "Reported late", sae["late"],
              f"later than {SAE_REPORTING_WINDOW_DAYS} days after the report date",
              "bad" if sae["late"] else "good"),
        _tile("unreported", "Not yet reported", sae["unreported"],
              "still owed to this committee",
              "bad" if sae["unreported"] else "good"),
        _tile("compliance", "Reported on time", f"{sae['compliance_percent']}%",
              "of all serious events",
              "good" if sae["compliance_percent"] >= 90 else "warn"),
        _tile("severe", "Severe events", severe,
              "severity, not seriousness - a different question"),
        _tile("all_aes", "All adverse events", safety["adverse_events"],
              f"across {stats['sites']['total']} sites"),
        _tile("deviations", "Protocol deviations", stats["visits"]["protocol_deviations"],
              f"{stats['visits']['deviation_rate']}% of visits due"),
        _tile("approval", "Ethics approval",
              trial.ethics_approval_date.isoformat() if trial.ethics_approval_date else "none",
              trial.ethics_approval_number or "not recorded",
              "good" if trial.ethics_approval_date else "bad"),
    ]

    blocks = [
        _table(
            "sae_reporting",
            "Serious adverse events and their reporting",
            [("ae_number", "AE"), ("site", "Site"), ("term", "Event"),
             ("criteria", "Why serious"), ("onset", "Onset"),
             ("urgency", "24h Regulatory Clock"),
             ("reported", "Reported"), ("to_ethics", "To ethics"),
             ("days", "Days"), ("verdict", "Verdict")],
            sae["rows"],
            note=f"The window used here is {SAE_REPORTING_WINDOW_DAYS} days. Phase 5 "
                 "replaces it with the real NDCT Rules 2019 deadlines.",
            empty="No serious adverse events reported.",
        ),
        _checklist(
            "ethics_snapshot",
            "Compliance snapshot",
            [
                _check("Ethics approval on record", bool(trial.ethics_approval_date),
                       trial.ethics_approval_number or "no approval number recorded"),
                _check("Every serious event reported", sae["unreported"] == 0,
                       f"{sae['unreported']} still owed to this committee"),
                _check("All reports inside the window", sae["late"] == 0,
                       f"{sae['late']} arrived later than "
                       f"{SAE_REPORTING_WINDOW_DAYS} days"),
                _check("Deviations are being recorded",
                       stats["visits"]["protocol_deviations"] > 0,
                       "A trial reporting zero deviations is usually under-reporting, "
                       "not perfect."),
            ],
            note="Phase 5 turns this into a scored, per-trial compliance report.",
        ),
        _breakdown("by_causality", "Was the treatment to blame?", safety["by_causality"],
                   "The investigator's judgement on each event, from unrelated to definite."),
        _table(
            "deviations",
            "Recent protocol deviations",
            [("subject", "Participant"), ("visit", "Visit"),
             ("scheduled", "Scheduled"), ("actual", "Actual"),
             ("description", "What happened")],
            _deviation_rows(session, tid, user),
            note="Deviations are expected. What matters is that each one is written "
                 "down rather than quietly fixed.",
            empty="No deviations recorded.",
        ),
    ]
    return tiles, blocks


def _regulator(session, user, stats, trial, today) -> tuple[list, list]:
    """Regulator: was this trial run lawfully, and can I prove it from the record?"""
    tid = trial.id
    sae = _sae_reporting(session, tid, user)
    audit = stats.get("audit", {})

    # Was the trial registered with CTRI before the first person was enrolled?
    # India requires registration before enrolment begins, so this ordering is a
    # legal gate, not a nicety.
    first_enrolment = session.exec(
        select(func.min(Subject.enrollment_date)).where(Subject.trial_id == tid)
    ).one()
    if isinstance(first_enrolment, tuple):  # pragma: no cover - driver difference
        first_enrolment = first_enrolment[0]
    registered_in_time = bool(
        trial.ctri_registration_date
        and first_enrolment
        and trial.ctri_registration_date <= first_enrolment
    )

    sites = session.exec(select(Site).where(Site.trial_id == tid)).all()
    activated = sum(1 for site in sites if site.activation_date is not None)

    tiles = [
        _tile("ctri", "CTRI registration", trial.ctri_number or "not registered",
              trial.ctri_registration_date.isoformat()
              if trial.ctri_registration_date else "no registration date",
              "good" if trial.ctri_number else "bad"),
        _tile("ethics", "Ethics approval",
              trial.ethics_approval_date.isoformat()
              if trial.ethics_approval_date else "none",
              trial.ethics_approval_number or "not recorded",
              "good" if trial.ethics_approval_date else "bad"),
        _tile("status", "Trial status", trial.status.replace("_", " "),
              f"{trial.phase.replace('_', ' ')} · {trial.design}"),
        _tile("audit", "Audit entries", audit.get("entries", 0),
              "append-only, 21 CFR Part 11"),
        _tile("sae_compliance", "SAE reporting", f"{sae['compliance_percent']}%",
              f"{sae['on_time']} of {sae['total']} inside the window",
              "good" if sae["compliance_percent"] >= 90 else "bad"),
        _tile("deviation_rate", "Deviation rate", f"{stats['visits']['deviation_rate']}%",
              f"{stats['visits']['protocol_deviations']} recorded"),
        _tile("sites", "Sites activated", f"{activated} / {len(sites)}",
              "cleared to enrol"),
        _tile("enrolled", "Enrolled", stats["enrollment"]["enrolled"],
              f"of {stats['enrollment']['target']} approved"),
    ]

    blocks = [
        _checklist(
            "ndct_gates",
            "NDCT Rules 2019 gates",
            [
                _check("Ethics committee approval obtained",
                       bool(trial.ethics_approval_date),
                       trial.ethics_approval_number or "no approval on record"),
                _check("Regulatory permission on record",
                       bool(trial.regulatory_approval_number),
                       trial.regulatory_approval_number or "no permission number"),
                _check("Registered with CTRI", bool(trial.ctri_number),
                       trial.ctri_number or "not registered"),
                _check("Registered before first enrolment", registered_in_time,
                       f"CTRI {trial.ctri_registration_date or '-'}, "
                       f"first enrolment {first_enrolment or '-'}"),
                _check("Every site activated before use", activated == len(sites),
                       f"{activated} of {len(sites)} sites have an activation date"),
                _check("Serious events reported in time",
                       sae["late"] == 0 and sae["unreported"] == 0,
                       f"{sae['late']} late, {sae['unreported']} unreported"),
                _check("Audit trail present", audit.get("entries", 0) > 0,
                       f"{audit.get('entries', 0)} entries, insert-only"),
            ],
            note="India's New Drugs and Clinical Trials Rules 2019 - the legal gates "
                 "a trial passes through, in order. Phase 5 enforces them as workflow "
                 "and scores the result.",
        ),
        _table(
            "audit_tail",
            "Recent audit entries",
            [("at", "When"), ("who", "Who"), ("role", "Role"),
             ("action", "Action"), ("what", "Record"), ("reason", "Reason")],
            _audit_rows(session, tid) if user.can(Permission.AUDIT_READ) else [],
            note="Who did what, newest first. Entries are only ever added, never "
                 "edited or deleted.",
            empty="No audit entries yet.",
        ),
        _table(
            "sites",
            "Sites and their status",
            [("site_code", "Site"), ("name", "Institute"), ("city", "City"),
             ("status", "Status"), ("enrolled", "Enrolled"),
             ("target_enrollment", "Target")],
            stats["sites"]["detail"],
        ),
        {
            **_table(
                "sae_reporting",
                "Serious adverse events",
                [("ae_number", "AE"), ("site", "Site"), ("term", "Event"),
                 ("onset", "Onset"), ("urgency", "24h Regulatory Clock"),
                 ("to_ethics", "To ethics"), ("days", "Days"), ("verdict", "Verdict")],
                sae["rows"],
                empty="No serious adverse events reported.",
            ),
            "row_action": {
                "kind": "safety_report",
                "id_key": "event_id",
                "label": "PDF",
            },
        },
    ]
    return tiles, blocks


def _audit_rows(session: Session, trial_id: int, limit: int = 12) -> list[dict]:
    entries = session.exec(
        select(AuditLog)
        .where(AuditLog.trial_id == trial_id)
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())  # type: ignore[union-attr]
        .limit(limit)
    ).all()
    return [
        {
            "at": entry.timestamp.isoformat(timespec="seconds") if entry.timestamp else None,
            "who": entry.user_email or "system",
            "role": (entry.user_role or "-").replace("_", " "),
            "action": entry.action,
            "what": f"{entry.entity_type} {entry.entity_label or entry.entity_id or ''}".strip(),
            "reason": entry.reason or "-",
        }
        for entry in entries
    ]


def _institution_admin(
    session: Session, user: CurrentUser, stats: dict, trial: Trial, today: date
) -> tuple[list[dict], list[dict]]:
    site_id = user.scope_site_id
    site_obj = session.get(Site, site_id) if site_id else None
    site_name = site_obj.name if site_obj else (user.organization or "All Sites")
    site_code = site_obj.site_code if site_obj else ""

    # Personnel count
    researchers = list(session.exec(
        select(User).where(User.site_id == site_id, User.is_active == True)  # noqa: E712
    ).all()) if site_id else []

    # Patient requests
    req_query = select(PatientRequest).where(PatientRequest.site_id == site_id) if site_id else select(PatientRequest)
    requests = list(session.exec(req_query.order_by(PatientRequest.created_at.desc())).all())
    pending_reqs = sum(1 for r in requests if r.status != "resolved")

    enrolled = stats.get("enrollment", {}).get("enrolled", 0)
    screened = stats.get("enrollment", {}).get("screened", 0)
    target = stats.get("enrollment", {}).get("target", 0)
    recruitment_pct = stats.get("enrollment", {}).get("percent_of_target", 0)
    sae_count = stats.get("safety", {}).get("serious", 0)
    open_ae_val = _open_ae_count(session, trial.id, user)
    deviations = stats.get("visits", {}).get("protocol_deviations", 0)

    tiles = [
        _tile("institution", "Institution", f"{site_code} {site_name}".strip() or "All Sites", tone="neutral"),
        _tile("researchers", "Researchers & Staff", len(researchers), hint="Active personnel", tone="good"),
        _tile("enrolled", "Recruited", f"{enrolled} / {target}", hint=f"{recruitment_pct}% of target", tone="good" if recruitment_pct >= 80 else "warn"),
        _tile("pending_requests", "Pending Patient Requests", pending_reqs, hint="Requires admin action", tone="warn" if pending_reqs > 0 else "good"),
        _tile("open_aes", "Open Safety Events", open_ae_val, tone="warn" if open_ae_val > 0 else "good"),
        _tile("sae_count", "Serious AEs", sae_count, tone="bad" if sae_count > 0 else "good"),
        _tile("deviations", "Protocol Deviations", deviations, tone="warn" if deviations > 0 else "neutral"),
        _tile("screened", "Screened Participants", screened, hint=f"{enrolled} enrolled", tone="neutral"),
    ]

    req_rows = [
        {
            "category": r.category.replace("_", " ").title(),
            "subject": r.subject_line,
            "status": r.status.upper(),
            "date": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "-",
            "response": r.admin_response or "Awaiting response",
        }
        for r in requests[:8]
    ]

    staff_rows = [
        {
            "name": u.full_name,
            "role": u.role.replace("_", " ").title(),
            "email": u.email,
            "phone": u.phone or "—",
        }
        for u in researchers
    ]

    blocks = [
        _table(
            "patient_requests",
            "Patient Inquiries & Communications",
            [
                ("category", "Category"),
                ("subject", "Subject"),
                ("status", "Status"),
                ("date", "Submitted"),
                ("response", "Response"),
            ],
            req_rows,
            empty="No patient inquiries submitted yet.",
        ),
        _table(
            "staff",
            "Institutional Researchers & Clinical Staff",
            [
                ("name", "Name"),
                ("role", "Role"),
                ("email", "Email"),
                ("phone", "Phone"),
            ],
            staff_rows,
            empty="No staff members assigned.",
        ),
        _breakdown(
            "status_breakdown",
            "Participant Status Breakdown",
            stats.get("subjects_by_status", {}),
        ),
    ]
    return tiles, blocks


def _patient(
    session: Session, user: CurrentUser, stats: dict, trial: Trial, today: date
) -> tuple[list[dict], list[dict]]:
    # Fetch linked subject record
    subject = session.get(Subject, user.subject_id) if user.subject_id else None
    site = session.get(Site, user.site_id) if user.site_id else (session.get(Site, subject.site_id) if subject else None)

    # Fetch patient's visits
    visits = []
    if subject:
        visits = list(session.exec(select(Visit).where(Visit.subject_id == subject.id).order_by(Visit.visit_number)).all())

    next_visit = next((v for v in visits if v.status == "scheduled" and v.scheduled_date and v.scheduled_date >= today), None)
    completed_visits = sum(1 for v in visits if v.status == "completed")

    # Fetch patient's requests
    requests = list(session.exec(
        select(PatientRequest).where(PatientRequest.patient_user_id == user.id).order_by(PatientRequest.created_at.desc())
    ).all())
    resolved_count = sum(1 for r in requests if r.status == "resolved")

    # Care team
    pi_user = session.exec(select(User).where(User.site_id == user.site_id, User.role == UserRole.PRINCIPAL_INVESTIGATOR.value)).first()
    crc_user = session.exec(select(User).where(User.site_id == user.site_id, User.role == UserRole.COORDINATOR.value)).first()

    tiles = [
        _tile("my_id", "Participant ID", subject.subject_code if subject else "Assigned", tone="neutral"),
        _tile("my_status", "Trial Status", (subject.status if subject else "Enrolled").replace("_", " ").title(), tone="good"),
        _tile("next_visit", "Next Appointment", str(next_visit.scheduled_date) if next_visit else "None scheduled", hint=next_visit.visit_name if next_visit else None, tone="good"),
        _tile("completed_visits", "Completed Visits", f"{completed_visits} / {len(visits)}", tone="good"),
        _tile("requests_submitted", "My Inquiries", len(requests), tone="neutral"),
        _tile("requests_resolved", "Resolved", resolved_count, tone="good" if resolved_count == len(requests) else "warn"),
        _tile("institution", "Hospital", site.name if site else "AIIA", tone="neutral"),
        _tile("trial", "Protocol", trial.short_title, tone="neutral"),
    ]

    req_rows = [
        {
            "category": r.category.replace("_", " ").title(),
            "subject": r.subject_line,
            "status": r.status.upper(),
            "date": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "-",
            "response": r.admin_response or "Pending review by hospital admin",
        }
        for r in requests
    ]

    visit_rows = [
        {
            "visit": v.visit_name,
            "scheduled": str(v.scheduled_date or "—"),
            "status": v.status.replace("_", " ").title(),
            "notes": v.notes or "—",
        }
        for v in visits
    ]

    care_team_rows = []
    if pi_user:
        care_team_rows.append({"name": pi_user.full_name, "role": "Principal Investigator", "contact": pi_user.email})
    if crc_user:
        care_team_rows.append({"name": crc_user.full_name, "role": "Study Coordinator", "contact": crc_user.email})

    blocks = [
        _table(
            "my_requests",
            "My Inquiries & Hospital Communications",
            [
                ("category", "Category"),
                ("subject", "Subject"),
                ("status", "Status"),
                ("date", "Submitted"),
                ("response", "Hospital Admin Response"),
            ],
            req_rows,
            empty="You have not submitted any inquiries. Use the 'Contact Hospital Admin' action below to submit a question or request.",
        ),
        _table(
            "my_schedule",
            "My Protocol Visit Schedule",
            [
                ("visit", "Visit"),
                ("scheduled", "Date"),
                ("status", "Status"),
                ("notes", "Instructions / Notes"),
            ],
            visit_rows,
            empty="No schedule available.",
        ),
        _table(
            "care_team",
            "My Clinical Care Team",
            [
                ("name", "Name"),
                ("role", "Role"),
                ("contact", "Email"),
            ],
            care_team_rows,
            empty="Care team details will appear once assigned.",
        ),
    ]
    return tiles, blocks


BUILDERS = {
    UserRole.ADMIN.value: _regulator,
    UserRole.INSTITUTION_ADMIN.value: _institution_admin,
    UserRole.PRINCIPAL_INVESTIGATOR.value: _investigator,
    UserRole.COORDINATOR.value: _coordinator,
    UserRole.PATIENT.value: _patient,
    UserRole.SPONSOR.value: _sponsor,
    UserRole.ETHICS_COMMITTEE.value: _ethics,
    UserRole.REGULATOR.value: _regulator,
}

HEADLINES = {
    UserRole.ADMIN.value: (
        "Primary Administrator view",
        "System governance, institution oversight, and global CTMS audit trail.",
    ),
    UserRole.INSTITUTION_ADMIN.value: (
        "Institution Administration",
        "Site governance, researcher coordination, recruitment KPIs, and patient inquiry management.",
    ),
    UserRole.PRINCIPAL_INVESTIGATOR.value: (
        "My site",
        "Recruitment, safety and deviations for the site I am responsible for.",
    ),
    UserRole.COORDINATOR.value: (
        "This week at my site",
        "Visits due, people mid-screening, and data still waiting to be entered.",
    ),
    UserRole.PATIENT.value: (
        "Patient Portal",
        "My clinical trial schedule, assigned care team, and direct communications with hospital administration.",
    ),
    UserRole.SPONSOR.value: (
        "Study overview",
        "Every site, one screen: is this trial on track and is it safe?",
    ),
    UserRole.ETHICS_COMMITTEE.value: (
        "Safety and ethics review",
        "Serious events, how fast they reached this committee, and protocol deviations.",
    ),
    UserRole.REGULATOR.value: (
        "Regulatory oversight",
        "Registration, approvals, reporting timeliness and the audit trail.",
    ),
}


def build_dashboard(
    session: Session, user: CurrentUser, trial_id: int | None = None
) -> dict:
    """The whole payload for one user's dashboard.

    Called by `GET /api/dashboard` and again by the WebSocket on every event, so
    the live update and the first paint are always the same code path - a live
    number can never disagree with a refreshed one.
    """
    stats = build_stats(session, user, trial_id)
    title, subtitle = HEADLINES.get(user.role, ("Dashboard", ""))

    common = {
        "role": user.role,
        "role_label": user.role_label,
        "title": title,
        "subtitle": subtitle,
        "user": {"id": user.id, "name": user.full_name, "email": user.email},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # Which fan-out backend is live, so the demo can say "this is Redis"
        # honestly, or notice that it fell back.
        "live": {"backend": bus.backend, "detail": bus.detail},
        "data_notice": "All data in this system is synthetic. No real patient data.",
    }

    if not stats.get("seeded"):
        return common | {
            "seeded": False,
            "message": stats.get("message"),
            "tiles": [],
            "blocks": [],
        }

    trial = resolve_trial(session, trial_id)
    assert trial is not None  # build_stats already established this
    today = date.today()
    builder = BUILDERS.get(user.role, _sponsor)
    tiles, blocks = builder(session, user, stats, trial, today)

    return common | {
        "seeded": True,
        "scope": stats["scope"],
        "trial": stats["trial"],
        "tiles": tiles,
        "blocks": blocks,
    }
