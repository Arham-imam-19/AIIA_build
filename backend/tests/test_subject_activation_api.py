"""Focused API tests for contemporaneous first-dose Subject activation."""

from __future__ import annotations

import itertools
import json
from datetime import date, timedelta

import pytest
from sqlmodel import Session, select

from app.enums import AuditAction, SiteStatus, StudyArm, SubjectStatus, TrialStatus, UserRole
from app.models import AuditLog, Site, Subject, Trial
from app.routers import subjects as subjects_router
from tests.conftest import client_for_user, users_by_role


_IDS = itertools.count(1)


def route(subject_id: int) -> str:
    return f"/api/subjects/{subject_id}/activation"


def make_subject(engine, *, site_id: int | None = None, status: str = "enrolled", **changes) -> int:
    with Session(engine) as session:
        site = session.get(Site, site_id) if site_id is not None else session.exec(select(Site).order_by(Site.id)).first()
        assert site is not None and site.id is not None
        enrolled = date.today() - timedelta(days=1)
        values = {
            "trial_id": site.trial_id,
            "site_id": site.id,
            "subject_code": f"P07-{next(_IDS):05d}",
            "status": status,
            "screening_date": enrolled - timedelta(days=7),
            "enrollment_date": enrolled,
            "randomization_date": enrolled,
            "arm": StudyArm.TREATMENT.value,
            "sex": "female",
            "prakriti": "vata_pitta",
            "screen_failure_reason": None,
            "completed_date": None,
            "withdrawal_date": None,
            "withdrawal_reason": None,
        }
        values.update(changes)
        row = Subject(**values)
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.id is not None
        return row.id


def snapshot(engine, subject_id: int) -> tuple[dict, list[AuditLog]]:
    with Session(engine) as session:
        subject = session.get(Subject, subject_id)
        assert subject is not None
        values = subject.model_dump()
        audits = list(session.exec(select(AuditLog).where(
            AuditLog.entity_type == "subjects", AuditLog.entity_id == subject_id
        ).order_by(AuditLog.id)).all())
        for entry in audits:
            session.expunge(entry)
        return values, audits


def test_success_persists_only_activation_facts_and_one_audit(client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    before, _ = snapshot(seeded_engine, subject_id)
    response = client.patch(route(subject_id), json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"id", "trial_id", "site_id", "subject_code", "status", "updated_at"}
    assert body["status"] == SubjectStatus.ACTIVE.value

    after, audits = snapshot(seeded_engine, subject_id)
    assert after["status"] == SubjectStatus.ACTIVE.value
    assert after["updated_at"] > before["updated_at"]
    for field in ("enrollment_date", "randomization_date", "arm", "prakriti"):
        assert after[field] == before[field]
    assert len(audits) == 1
    entry = audits[0]
    assert (entry.action, entry.entity_type, entry.entity_id) == (
        AuditAction.UPDATE.value, "subjects", subject_id
    )
    assert entry.field_name == "activation"
    assert json.loads(entry.old_value) == {"status": SubjectStatus.ENROLLED.value}
    assert json.loads(entry.new_value) == {"status": SubjectStatus.ACTIVE.value}
    assert entry.reason == "Subject activated after first dose confirmation."


@pytest.mark.parametrize("role", [UserRole.PRINCIPAL_INVESTIGATOR, UserRole.COORDINATOR])
def test_assigned_site_clinical_writer_can_activate(seeded_engine, role):
    user = users_by_role(seeded_engine, role.value)[0]
    subject_id = make_subject(seeded_engine, site_id=user.site_id)
    assert client_for_user(seeded_engine, user).patch(route(subject_id), json={}).status_code == 200


def test_foreign_site_is_403(seeded_engine):
    users = users_by_role(seeded_engine, UserRole.PRINCIPAL_INVESTIGATOR.value)
    caller = users[0]
    foreign = next(user for user in users[1:] if user.site_id != caller.site_id)
    subject_id = make_subject(seeded_engine, site_id=foreign.site_id)
    assert client_for_user(seeded_engine, caller).patch(route(subject_id), json={}).status_code == 403


def test_missing_subject_is_404(client):
    assert client.patch(route(999999), json={}).status_code == 404


@pytest.mark.parametrize("role", [UserRole.SPONSOR, UserRole.ETHICS_COMMITTEE, UserRole.REGULATOR])
def test_roles_without_subject_write_are_403(role_clients, seeded_engine, role):
    subject_id = make_subject(seeded_engine)
    assert role_clients[role.value].patch(route(subject_id), json={}).status_code == 403


@pytest.mark.parametrize("status", [
    SubjectStatus.SCREENING.value,
    SubjectStatus.ACTIVE.value,
    SubjectStatus.COMPLETED.value,
    SubjectStatus.WITHDRAWN.value,
    SubjectStatus.LOST_TO_FOLLOW_UP.value,
])
def test_invalid_current_status_is_409(client, seeded_engine, status):
    subject_id = make_subject(seeded_engine, status=status)
    response = client.patch(route(subject_id), json={})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TRANSITION_NOT_ALLOWED"


def test_unknown_request_field_is_422_without_side_effects(client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    before, audits = snapshot(seeded_engine, subject_id)
    assert client.patch(route(subject_id), json={"activation_date": date.today().isoformat()}).status_code == 422
    assert snapshot(seeded_engine, subject_id) == (before, audits)


@pytest.mark.parametrize("entity", ["trial", "site"])
def test_non_recruiting_trial_or_site_is_409(client, seeded_engine, entity):
    subject_id = make_subject(seeded_engine)
    with Session(seeded_engine) as session:
        subject = session.get(Subject, subject_id)
        assert subject is not None
        row = session.get(Trial, subject.trial_id) if entity == "trial" else session.get(Site, subject.site_id)
        assert row is not None
        original_status = row.status
        row_id = row.id
        row.status = TrialStatus.ACTIVE.value if entity == "trial" else SiteStatus.SUSPENDED.value
        session.add(row)
        session.commit()
    try:
        assert client.patch(route(subject_id), json={}).status_code == 409
    finally:
        with Session(seeded_engine) as session:
            row = session.get(Trial if entity == "trial" else Site, row_id)
            assert row is not None
            row.status = original_status
            session.add(row)
            session.commit()


def test_broken_trial_site_linkage_is_controlled_409(client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    with Session(seeded_engine) as session:
        subject = session.get(Subject, subject_id)
        assert subject is not None
        other_site = session.exec(select(Site).where(Site.trial_id != subject.trial_id)).first()
        if other_site is None:
            source = session.get(Trial, subject.trial_id)
            clone_id = next(_IDS)
            values = source.model_dump(exclude={"id", "protocol_number", "ctri_number"})
            values.update(
                protocol_number=f"P07-OTHER-{clone_id}",
                ctri_number=f"CTRI/2026/08/{clone_id:06d}",
            )
            other_trial = Trial(**values)
            session.add(other_trial)
            session.flush()
            site_values = session.get(Site, subject.site_id).model_dump(exclude={"id", "site_code"})
            site_values.update(trial_id=other_trial.id, site_code=f"P07-{next(_IDS)}")
            other_site = Site(**site_values)
            session.add(other_site)
            session.flush()
        subject.site_id = other_site.id
        session.add(subject)
        session.commit()
    response = client.patch(route(subject_id), json={})
    assert response.status_code == 409
    assert response.json()["detail"] == "subject has inconsistent Trial or Site linkage"


def test_audit_failure_rolls_back_activation(monkeypatch, client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    before, audits = snapshot(seeded_engine, subject_id)
    monkeypatch.setattr(subjects_router.audit, "record", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("audit failed")))
    with pytest.raises(RuntimeError, match="audit failed"):
        client.patch(route(subject_id), json={})
    assert snapshot(seeded_engine, subject_id) == (before, audits)


def test_repeated_request_has_one_success_and_one_audit(client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    assert client.patch(route(subject_id), json={}).status_code == 200
    assert client.patch(route(subject_id), json={}).status_code == 409
    assert len(snapshot(seeded_engine, subject_id)[1]) == 1


def test_unrelated_subject_remains_unchanged(client, seeded_engine):
    target_id = make_subject(seeded_engine)
    other_id = make_subject(seeded_engine)
    before = snapshot(seeded_engine, other_id)
    assert client.patch(route(target_id), json={}).status_code == 200
    assert snapshot(seeded_engine, other_id) == before
