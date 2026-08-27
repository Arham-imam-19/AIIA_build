"""Focused API tests for scheduling one manually specified Visit."""

from __future__ import annotations

import itertools
import json
from datetime import date, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.enums import AuditAction, SubjectStatus, UserRole, VisitStatus
from app.main import app
from app.models import AuditLog, Site, Subject, Visit
from app.routers import subjects as subjects_router
from tests.conftest import client_for_user, users_by_role


_IDS = itertools.count(1)


def route(subject_id: int) -> str:
    return f"/api/subjects/{subject_id}/visits"


def payload(**changes) -> dict:
    body = {
        "visit_name": "  Week 4 Follow-up  ",
        "visit_number": 101,
        "visit_day": 28,
        "scheduled_date": date.today().isoformat(),
    }
    body.update(changes)
    return body


def make_subject(
    engine,
    *,
    site_id: int | None = None,
    status: str = SubjectStatus.ENROLLED.value,
    **changes,
) -> int:
    with Session(engine) as session:
        site = session.get(Site, site_id) if site_id is not None else session.exec(
            select(Site).order_by(Site.id)
        ).first()
        assert site is not None and site.id is not None
        enrolled = date.today() - timedelta(days=1)
        values = {
            "trial_id": site.trial_id,
            "site_id": site.id,
            "subject_code": f"P10-{next(_IDS):05d}",
            "status": status,
            "screening_date": enrolled - timedelta(days=7),
            "enrollment_date": enrolled,
            "randomization_date": enrolled,
            "arm": "treatment",
            "sex": "female",
        }
        values.update(changes)
        subject = Subject(**values)
        session.add(subject)
        session.commit()
        session.refresh(subject)
        assert subject.id is not None
        return subject.id


def scheduled(engine, subject_id: int) -> tuple[list[Visit], list[AuditLog]]:
    with Session(engine) as session:
        visits = list(session.exec(select(Visit).where(
            Visit.subject_id == subject_id,
            Visit.visit_number >= 100,
        ).order_by(Visit.id)).all())
        audits = list(session.exec(select(AuditLog).where(
            AuditLog.entity_type == "visits",
            AuditLog.field_name == "schedule",
            AuditLog.entity_id.in_([row.id for row in visits]),
        ).order_by(AuditLog.id)).all()) if visits else []
        for row in [*visits, *audits]:
            session.expunge(row)
        return visits, audits


@pytest.mark.parametrize("status", [SubjectStatus.ENROLLED.value, SubjectStatus.ACTIVE.value])
def test_success_is_narrow_initialized_and_audited(client, seeded_engine, status):
    subject_id = make_subject(seeded_engine, status=status)
    response = client.post(route(subject_id), json=payload())
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {
        "id", "subject_id", "trial_id", "visit_name", "visit_number",
        "visit_day", "scheduled_date", "status", "created_at", "updated_at",
    }
    assert body["subject_id"] == subject_id
    assert body["visit_name"] == "Week 4 Follow-up"
    assert body["status"] == VisitStatus.SCHEDULED.value
    assert body["created_at"] == body["updated_at"]

    visits, audits = scheduled(seeded_engine, subject_id)
    assert len(visits) == len(audits) == 1
    visit = visits[0]
    assert (visit.actual_date, visit.is_protocol_deviation,
            visit.deviation_description, visit.notes,
            visit.performed_by_user_id) == (None, False, None, None, None)
    entry = audits[0]
    assert (entry.action, entry.entity_type, entry.entity_id,
            entry.field_name, entry.old_value, entry.reason) == (
        AuditAction.CREATE.value, "visits", visit.id,
        "schedule", None, "Visit scheduled.",
    )
    assert json.loads(entry.new_value) == {
        "scheduled_date": date.today().isoformat(),
        "status": "scheduled",
        "visit_day": 28,
        "visit_name": "Week 4 Follow-up",
        "visit_number": 101,
    }
    assert entry.trial_id == visit.trial_id


@pytest.mark.parametrize("visit_day", [-14, 0, 84])
def test_negative_zero_and_positive_visit_days_are_valid(client, seeded_engine, visit_day):
    subject_id = make_subject(seeded_engine)
    response = client.post(route(subject_id), json=payload(visit_day=visit_day))
    assert response.status_code == 201, response.text
    assert response.json()["visit_day"] == visit_day


@pytest.mark.parametrize("status", [
    SubjectStatus.SCREENING.value,
    SubjectStatus.SCREEN_FAILED.value,
    SubjectStatus.COMPLETED.value,
    SubjectStatus.WITHDRAWN.value,
    SubjectStatus.LOST_TO_FOLLOW_UP.value,
])
def test_other_subject_states_are_409(client, seeded_engine, status):
    subject_id = make_subject(seeded_engine, status=status)
    assert client.post(route(subject_id), json=payload()).status_code == 409
    assert scheduled(seeded_engine, subject_id) == ([], [])


def test_missing_foreign_site_permissions_and_admin_scope(client, role_clients, seeded_engine):
    assert client.post(route(999999), json=payload()).status_code == 404
    coordinators = users_by_role(seeded_engine, UserRole.COORDINATOR.value)
    caller, foreign = coordinators[0], coordinators[1]
    foreign_subject = make_subject(seeded_engine, site_id=foreign.site_id)
    assert client_for_user(seeded_engine, caller).post(
        route(foreign_subject), json=payload()
    ).status_code == 403

    own_subject = make_subject(seeded_engine, site_id=caller.site_id)
    assert client_for_user(seeded_engine, caller).post(
        route(own_subject), json=payload()
    ).status_code == 201

    for role in (UserRole.SPONSOR, UserRole.ETHICS_COMMITTEE, UserRole.REGULATOR):
        subject_id = make_subject(seeded_engine)
        assert role_clients[role.value].post(
            route(subject_id), json=payload()
        ).status_code == 403

    admin_subject = make_subject(seeded_engine, site_id=foreign.site_id)
    assert client.post(route(admin_subject), json=payload()).status_code == 201


def test_broken_linkage_is_controlled_409(client, seeded_engine):
    subject_id = make_subject(seeded_engine, trial_id=999999)
    assert client.post(route(subject_id), json=payload()).status_code == 409
    assert scheduled(seeded_engine, subject_id) == ([], [])


@pytest.mark.parametrize("changes", [
    {"visit_name": "   "},
    {"visit_name": "x" * 121},
    {"visit_number": 0},
    {"scheduled_date": (date.today() - timedelta(days=1)).isoformat()},
])
def test_invalid_schedule_facts_are_422(client, seeded_engine, changes):
    subject_id = make_subject(seeded_engine)
    assert client.post(route(subject_id), json=payload(**changes)).status_code == 422
    assert scheduled(seeded_engine, subject_id) == ([], [])


@pytest.mark.parametrize("scheduled_date", [date.today(), date.today() + timedelta(days=30)])
def test_today_and_future_dates_are_valid(client, seeded_engine, scheduled_date):
    subject_id = make_subject(seeded_engine)
    response = client.post(
        route(subject_id), json=payload(scheduled_date=scheduled_date.isoformat())
    )
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("field,value", [
    ("subject_id", 1), ("trial_id", 1), ("status", "completed"),
    ("actual_date", "2026-08-27"), ("is_protocol_deviation", True),
    ("deviation_description", "x"), ("performed_by_user_id", 1),
    ("notes", "x"), ("created_at", "now"), ("updated_at", "now"),
    ("unknown", True),
])
def test_server_controlled_and_unknown_fields_are_422(client, seeded_engine, field, value):
    subject_id = make_subject(seeded_engine)
    assert client.post(route(subject_id), json=payload(**{field: value})).status_code == 422


def test_duplicate_number_is_409_but_different_subject_is_allowed(client, seeded_engine):
    first = make_subject(seeded_engine)
    second = make_subject(seeded_engine)
    assert client.post(route(first), json=payload()).status_code == 201
    assert client.post(route(first), json=payload()).status_code == 409
    assert client.post(route(second), json=payload()).status_code == 201
    assert len(scheduled(seeded_engine, first)[0]) == 1


def test_audit_failure_rolls_back_visit(client, seeded_engine, monkeypatch):
    subject_id = make_subject(seeded_engine)
    monkeypatch.setattr(
        subjects_router.audit,
        "record",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("audit failed")),
    )
    with pytest.raises(RuntimeError, match="audit failed"):
        client.post(route(subject_id), json=payload())
    assert scheduled(seeded_engine, subject_id) == ([], [])


def test_unrelated_integrity_error_is_not_mislabeled(client, seeded_engine, monkeypatch):
    subject_id = make_subject(seeded_engine)
    error = IntegrityError("insert", {}, Exception("different constraint"))
    monkeypatch.setattr(
        Session,
        "flush",
        lambda *_a, **_k: (_ for _ in ()).throw(error),
    )
    with pytest.raises(IntegrityError):
        client.post(route(subject_id), json=payload())


def test_model_metadata_and_routes_have_no_collision():
    table = Visit.__table__
    unique = {
        (constraint.name, tuple(column.name for column in constraint.columns))
        for constraint in table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }
    assert ("uq_visits_subject_id_visit_number", ("subject_id", "visit_number")) in unique

    matching = [
        route for route in app.routes
        if getattr(route, "path", None) == "/api/subjects/{subject_id}/visits"
    ]
    assert {method for route in matching for method in route.methods} == {"GET", "POST"}
    path = app.openapi()["paths"]["/api/subjects/{subject_id}/visits"]
    assert set(path) == {"get", "post"}
    assert "201" in path["post"]["responses"]
