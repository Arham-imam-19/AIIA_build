"""Focused API tests for recording Visit outcomes."""

from __future__ import annotations

import itertools
import json
from datetime import date, timedelta

import pytest
from sqlmodel import Session, select

from app.enums import AuditAction, SubjectStatus, UserRole, VisitStatus
from app.models import AuditLog, Site, Subject, Trial, Visit
from app.routers import subjects as subjects_router
from tests.conftest import client_for_user, users_by_role


_IDS = itertools.count(1)


def route(visit_id: int) -> str:
    return f"/api/visits/{visit_id}/outcome"


def make_visit(engine, *, site_id=None, subject_status="active", scheduled=None,
               visit_status="scheduled") -> int:
    with Session(engine) as session:
        site = session.get(Site, site_id) if site_id else session.exec(
            select(Site).order_by(Site.id)
        ).first()
        assert site is not None and site.id is not None
        enrolled = date.today() - timedelta(days=40)
        subject = Subject(
            trial_id=site.trial_id, site_id=site.id,
            subject_code=f"P08-{next(_IDS):05d}", status=subject_status,
            screening_date=enrolled - timedelta(days=7), enrollment_date=enrolled,
            randomization_date=enrolled, arm="treatment", sex="female",
        )
        session.add(subject)
        session.flush()
        row = Visit(
            subject_id=subject.id, trial_id=site.trial_id, visit_name="Week 4",
            visit_number=2, visit_day=28,
            scheduled_date=scheduled if scheduled is not None else date.today(),
            status=visit_status,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.id is not None
        return row.id


def snapshot(engine, visit_id):
    with Session(engine) as session:
        row = session.get(Visit, visit_id)
        assert row is not None
        values = row.model_dump()
        audits = list(session.exec(select(AuditLog).where(
            AuditLog.entity_type == "visits", AuditLog.entity_id == visit_id,
            AuditLog.field_name == "outcome",
        ).order_by(AuditLog.id)).all())
        for entry in audits:
            session.expunge(entry)
        return values, audits


def completed(**changes):
    payload = {
        "status": "completed", "actual_date": date.today().isoformat(),
        "is_protocol_deviation": False, "deviation_description": None,
    }
    payload.update(changes)
    return payload


def missed(**changes):
    payload = {
        "status": "missed", "actual_date": None,
        "is_protocol_deviation": True, "deviation_description": "No contact.",
    }
    payload.update(changes)
    return payload


def test_completion_is_narrow_atomic_and_audited(client, seeded_engine):
    visit_id = make_visit(seeded_engine)
    before, _ = snapshot(seeded_engine, visit_id)
    response = client.patch(route(visit_id), json=completed())
    assert response.status_code == 200, response.text
    assert set(response.json()) == {
        "id", "subject_id", "status", "scheduled_date", "actual_date",
        "is_protocol_deviation", "deviation_description",
        "performed_by_user_id", "updated_at",
    }
    after, audits = snapshot(seeded_engine, visit_id)
    assert after["status"] == VisitStatus.COMPLETED.value
    assert after["performed_by_user_id"] is not None
    for field in ("subject_id", "trial_id", "visit_name", "visit_number",
                  "visit_day", "scheduled_date"):
        assert after[field] == before[field]
    assert len(audits) == 1
    entry = audits[0]
    assert (entry.action, entry.field_name, entry.reason) == (
        AuditAction.UPDATE.value, "outcome", "Visit completed.",
    )
    assert json.loads(entry.old_value)["status"] == "scheduled"
    assert json.loads(entry.new_value)["status"] == "completed"


def test_deviated_completion_and_missed_normalization(client, seeded_engine):
    late = make_visit(seeded_engine, scheduled=date.today() - timedelta(days=4))
    response = client.patch(route(late), json=completed(
        deviation_description="  Travel delay.  ",
    ))
    assert response.status_code == 200
    assert response.json()["is_protocol_deviation"] is True
    assert response.json()["deviation_description"] == "Travel delay."

    absent = make_visit(seeded_engine, scheduled=date.today() - timedelta(days=4))
    response = client.patch(route(absent), json=missed(is_protocol_deviation=False))
    assert response.status_code == 200
    assert response.json()["is_protocol_deviation"] is True
    assert response.json()["performed_by_user_id"] is None
    assert snapshot(seeded_engine, absent)[1][0].reason == "Visit marked missed."


def test_missing_foreign_site_and_permission(client, role_clients, seeded_engine):
    assert client.patch(route(999999), json=completed()).status_code == 404
    users = users_by_role(seeded_engine, UserRole.COORDINATOR.value)
    caller, foreign = users[0], users[1]
    visit_id = make_visit(seeded_engine, site_id=foreign.site_id)
    assert client_for_user(seeded_engine, caller).patch(
        route(visit_id), json=completed()
    ).status_code == 403
    for role in (UserRole.SPONSOR, UserRole.REGULATOR):
        assert role_clients[role.value].patch(
            route(visit_id), json=completed()
        ).status_code == 403


def test_lifecycle_transition_and_date_conflicts_have_no_effect(client, seeded_engine):
    cases = [
        (make_visit(seeded_engine, subject_status=SubjectStatus.ENROLLED.value), completed()),
        (make_visit(seeded_engine, visit_status=VisitStatus.COMPLETED.value), completed()),
        (make_visit(seeded_engine), completed(actual_date=(date.today() + timedelta(days=1)).isoformat())),
        (make_visit(seeded_engine), missed()),
    ]
    for visit_id, payload in cases:
        before = snapshot(seeded_engine, visit_id)
        assert client.patch(route(visit_id), json=payload).status_code == 409
        assert snapshot(seeded_engine, visit_id) == before


@pytest.mark.parametrize("extra", [
    {"scheduled_date": "2026-01-01"}, {"performed_by_user_id": 1},
    {"notes": "x"}, {"unknown": True},
])
def test_server_controlled_or_unknown_fields_are_422(client, seeded_engine, extra):
    visit_id = make_visit(seeded_engine)
    before = snapshot(seeded_engine, visit_id)
    assert client.patch(route(visit_id), json=completed(**extra)).status_code == 422
    assert snapshot(seeded_engine, visit_id) == before


def test_missing_schedule_and_broken_linkage_are_controlled_409(client, seeded_engine):
    missing = make_visit(seeded_engine)
    broken = make_visit(seeded_engine)
    with Session(seeded_engine) as session:
        session.get(Visit, missing).scheduled_date = None
        session.get(Visit, broken).trial_id = 999999
        session.commit()
    assert client.patch(route(missing), json=completed()).status_code == 409
    assert client.patch(route(broken), json=completed()).status_code == 409


def test_audit_failure_rolls_back_and_other_visit_is_unchanged(
    monkeypatch, client, seeded_engine,
):
    target = make_visit(seeded_engine)
    other = make_visit(seeded_engine)
    before_target = snapshot(seeded_engine, target)
    before_other = snapshot(seeded_engine, other)
    monkeypatch.setattr(
        subjects_router.audit, "record",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("audit failed")),
    )
    with pytest.raises(RuntimeError, match="audit failed"):
        client.patch(route(target), json=completed())
    assert snapshot(seeded_engine, target) == before_target
    assert snapshot(seeded_engine, other) == before_other
