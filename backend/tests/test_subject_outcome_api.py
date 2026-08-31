"""Focused API tests for recording terminal Subject outcomes."""

from __future__ import annotations

import itertools
import json
from datetime import date, timedelta

import pytest
from sqlmodel import Session, select

from app.enums import AuditAction, SiteStatus, StudyArm, SubjectStatus, TrialStatus, UserRole, VisitStatus
from app.models import AuditLog, Site, Subject, Trial, Visit
from app.routers import subjects as subjects_router
from tests.conftest import client_for_user, users_by_role


_IDS = itertools.count(1)


def route(subject_id: int) -> str:
    return f"/api/subjects/{subject_id}/outcome"


def make_subject(engine, *, site_id=None, status=SubjectStatus.ACTIVE.value, **changes) -> int:
    with Session(engine) as session:
        site = session.get(Site, site_id) if site_id else session.exec(select(Site).order_by(Site.id)).first()
        assert site is not None and site.id is not None
        enrolled = date.today() - timedelta(days=10)
        values = {
            "trial_id": site.trial_id, "site_id": site.id,
            "subject_code": f"P09-{next(_IDS):05d}", "status": status,
            "screening_date": enrolled - timedelta(days=7),
            "enrollment_date": enrolled, "randomization_date": enrolled,
            "arm": StudyArm.TREATMENT.value, "sex": "female",
            "prakriti": "vata_pitta", "screen_failure_reason": None,
            "completed_date": None, "withdrawal_date": None,
            "withdrawal_reason": None,
        }
        values.update(changes)
        row = Subject(**values)
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.id is not None
        return row.id


def snapshot(engine, subject_id: int):
    with Session(engine) as session:
        row = session.get(Subject, subject_id)
        assert row is not None
        values = row.model_dump()
        audits = list(session.exec(select(AuditLog).where(
            AuditLog.entity_type == "subjects", AuditLog.entity_id == subject_id,
            AuditLog.field_name == "outcome",
        ).order_by(AuditLog.id)).all())
        for entry in audits:
            session.expunge(entry)
        return values, audits


def completed(**changes):
    body = {"status": "completed", "completed_date": date.today().isoformat(),
            "withdrawal_date": None, "withdrawal_reason": None}
    body.update(changes)
    return body


def discontinued(status="withdrawn", **changes):
    body = {"status": status, "completed_date": None,
            "withdrawal_date": date.today().isoformat(),
            "withdrawal_reason": "  Participant exited.  "}
    body.update(changes)
    return body


@pytest.mark.parametrize(
    "start,payload,reason",
    [
        (SubjectStatus.ACTIVE.value, completed(), "Subject completed the study."),
        (SubjectStatus.ENROLLED.value, discontinued(), "Subject withdrawn from the study."),
        (SubjectStatus.ACTIVE.value, discontinued(), "Subject withdrawn from the study."),
        (SubjectStatus.ENROLLED.value, discontinued("lost_to_follow_up"), "Subject lost to follow-up."),
        (SubjectStatus.ACTIVE.value, discontinued("lost_to_follow_up"), "Subject lost to follow-up."),
    ],
)
def test_allowed_outcomes_are_narrow_normalized_and_audited(client, seeded_engine, start, payload, reason):
    subject_id = make_subject(seeded_engine, status=start)
    before, _ = snapshot(seeded_engine, subject_id)
    response = client.patch(route(subject_id), json=payload)
    assert response.status_code == 200, response.text
    assert set(response.json()) == {
        "id", "trial_id", "site_id", "subject_code", "status",
        "completed_date", "withdrawal_date", "withdrawal_reason", "updated_at",
    }
    after, audits = snapshot(seeded_engine, subject_id)
    assert after["status"] == payload["status"]
    assert after["withdrawal_reason"] == ("Participant exited." if payload["status"] != "completed" else None)
    for field in ("enrollment_date", "randomization_date", "arm", "prakriti"):
        assert after[field] == before[field]
    assert len(audits) == 1
    entry = audits[0]
    assert (entry.action, entry.entity_type, entry.entity_id, entry.field_name, entry.reason) == (
        AuditAction.UPDATE.value, "subjects", subject_id, "outcome", reason,
    )
    assert json.loads(entry.old_value) == {
        "completed_date": None, "status": start,
        "withdrawal_date": None, "withdrawal_reason": None,
    }
    assert json.loads(entry.new_value)["status"] == payload["status"]


@pytest.mark.parametrize("role", [UserRole.PRINCIPAL_INVESTIGATOR, UserRole.COORDINATOR])
def test_assigned_site_writers_can_record_outcome(seeded_engine, role):
    user = users_by_role(seeded_engine, role.value)[0]
    subject_id = make_subject(seeded_engine, site_id=user.site_id)
    assert client_for_user(seeded_engine, user).patch(route(subject_id), json=completed()).status_code == 200


def test_missing_foreign_site_and_permission(client, role_clients, seeded_engine):
    assert client.patch(route(999999), json=completed()).status_code == 404
    users = users_by_role(seeded_engine, UserRole.COORDINATOR.value)
    caller, foreign = users[0], users[1]
    subject_id = make_subject(seeded_engine, site_id=foreign.site_id)
    assert client_for_user(seeded_engine, caller).patch(route(subject_id), json=completed()).status_code == 403
    for role in (UserRole.SPONSOR, UserRole.ETHICS_COMMITTEE, UserRole.REGULATOR):
        assert role_clients[role.value].patch(route(subject_id), json=completed()).status_code == 403


@pytest.mark.parametrize("status", [
    SubjectStatus.SCREENING.value, SubjectStatus.SCREEN_FAILED.value,
    SubjectStatus.ENROLLED.value, SubjectStatus.COMPLETED.value,
    SubjectStatus.WITHDRAWN.value, SubjectStatus.LOST_TO_FOLLOW_UP.value,
])
def test_invalid_completion_starts_have_no_effect(client, seeded_engine, status):
    changes = {}
    if status == SubjectStatus.COMPLETED.value:
        changes["completed_date"] = date.today()
    if status in (SubjectStatus.WITHDRAWN.value, SubjectStatus.LOST_TO_FOLLOW_UP.value):
        changes.update(withdrawal_date=date.today(), withdrawal_reason="Exited")
    subject_id = make_subject(seeded_engine, status=status, **changes)
    before = snapshot(seeded_engine, subject_id)
    response = client.patch(route(subject_id), json=completed())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TRANSITION_NOT_ALLOWED"
    assert snapshot(seeded_engine, subject_id) == before


@pytest.mark.parametrize("payload", [
    completed(completed_date=None),
    completed(completed_date=(date.today() + timedelta(days=1)).isoformat()),
    completed(completed_date=(date.today() - timedelta(days=11)).isoformat()),
    discontinued(withdrawal_date=None),
    discontinued(withdrawal_date=(date.today() + timedelta(days=1)).isoformat()),
    discontinued(withdrawal_date=(date.today() - timedelta(days=11)).isoformat()),
    discontinued(withdrawal_reason="   "),
    discontinued(completed_date=date.today().isoformat()),
    discontinued("lost_to_follow_up", withdrawal_reason=""),
])
def test_invalid_lifecycle_facts_have_no_effect(client, seeded_engine, payload):
    subject_id = make_subject(seeded_engine)
    before = snapshot(seeded_engine, subject_id)
    assert client.patch(route(subject_id), json=payload).status_code == 409
    assert snapshot(seeded_engine, subject_id) == before


@pytest.mark.parametrize("extra", [
    {"subject_id": 1}, {"trial_id": 1}, {"site_id": 1}, {"arm": "placebo"},
    {"enrollment_date": "2026-08-01"}, {"screen_failure_reason": "x"},
    {"updated_at": "2026-08-27T00:00:00Z"}, {"visit_id": 1}, {"unknown": True},
])
def test_server_controlled_and_unknown_fields_are_422(client, seeded_engine, extra):
    subject_id = make_subject(seeded_engine)
    before = snapshot(seeded_engine, subject_id)
    assert client.patch(route(subject_id), json={**completed(), **extra}).status_code == 422
    assert snapshot(seeded_engine, subject_id) == before


def test_broken_linkage_is_controlled_409(client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    with Session(seeded_engine) as session:
        subject = session.get(Subject, subject_id)
        other_trial = session.exec(select(Trial).where(Trial.id != subject.trial_id)).first()
        if other_trial is None:
            source = session.get(Trial, subject.trial_id)
            assert source is not None
            clone_id = next(_IDS)
            values = source.model_dump(exclude={"id", "protocol_number", "ctri_number"})
            values.update(
                protocol_number=f"P09-OTHER-{clone_id}",
                ctri_number=f"CTRI/2026/08/P09-{clone_id:06d}",
            )
            other_trial = Trial(**values)
            session.add(other_trial)
            session.flush()
        assert other_trial.id is not None
        subject.trial_id = other_trial.id
        session.commit()
    before = snapshot(seeded_engine, subject_id)
    response = client.patch(route(subject_id), json=completed())
    assert response.status_code == 409
    assert response.json()["detail"] == "subject has inconsistent Trial or Site linkage"
    assert snapshot(seeded_engine, subject_id) == before


@pytest.mark.parametrize("entity", ["trial", "site"])
def test_non_recruiting_lifecycle_does_not_block_outcome(client, seeded_engine, entity):
    subject_id = make_subject(seeded_engine)
    with Session(seeded_engine) as session:
        subject = session.get(Subject, subject_id)
        row = session.get(Trial, subject.trial_id) if entity == "trial" else session.get(Site, subject.site_id)
        row.status = TrialStatus.TERMINATED.value if entity == "trial" else SiteStatus.SUSPENDED.value
        session.commit()
    assert client.patch(route(subject_id), json=completed()).status_code == 200


def test_audit_failure_rolls_back_and_unrelated_subject_is_unchanged(monkeypatch, client, seeded_engine):
    target = make_subject(seeded_engine)
    other = make_subject(seeded_engine)
    before_target = snapshot(seeded_engine, target)
    before_other = snapshot(seeded_engine, other)
    monkeypatch.setattr(subjects_router.audit, "record", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("audit failed")))
    with pytest.raises(RuntimeError, match="audit failed"):
        client.patch(route(target), json=completed())
    assert snapshot(seeded_engine, target) == before_target
    assert snapshot(seeded_engine, other) == before_other


def test_repeated_request_has_one_success_and_one_audit(client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    assert client.patch(route(subject_id), json=completed()).status_code == 200
    assert client.patch(route(subject_id), json=completed()).status_code == 409
    assert len(snapshot(seeded_engine, subject_id)[1]) == 1


def test_visits_of_every_status_remain_unchanged(client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    with Session(seeded_engine) as session:
        subject = session.get(Subject, subject_id)
        for number, status in enumerate((
            VisitStatus.SCHEDULED.value, VisitStatus.COMPLETED.value,
            VisitStatus.MISSED.value, VisitStatus.CANCELLED.value,
        ), start=1):
            session.add(Visit(
                subject_id=subject_id, trial_id=subject.trial_id,
                visit_name=f"Visit {number}", visit_number=number, visit_day=number,
                scheduled_date=date.today() + timedelta(days=number), status=status,
                actual_date=date.today() if status == VisitStatus.COMPLETED.value else None,
                is_protocol_deviation=status == VisitStatus.MISSED.value,
                deviation_description="Missed." if status == VisitStatus.MISSED.value else None,
            ))
        session.commit()
        before = [row.model_dump() for row in session.exec(select(Visit).where(Visit.subject_id == subject_id).order_by(Visit.id)).all()]
    assert client.patch(route(subject_id), json=completed()).status_code == 200
    with Session(seeded_engine) as session:
        after = [row.model_dump() for row in session.exec(select(Visit).where(Visit.subject_id == subject_id).order_by(Visit.id)).all()]
    assert after == before
