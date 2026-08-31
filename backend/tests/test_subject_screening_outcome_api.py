"""Focused API tests for recording a Subject's failed screening outcome."""

from __future__ import annotations

import json
from datetime import date, timedelta
from itertools import count

import pytest
from sqlmodel import Session, select

from app.enums import AuditAction, StudyArm, SubjectStatus, UserRole
from app.models import AuditLog, Site, Subject
from app.routers import subjects as subjects_router
from tests.conftest import client_for_user, users_by_role


_IDS = count(1)


def route(subject_id: int) -> str:
    return f"/api/subjects/{subject_id}/screening-outcome"


def payload(**changes) -> dict:
    body = {"outcome": "screen_failed", "reason": "Did not meet eligibility criteria"}
    body.update(changes)
    return body


def make_subject(engine, *, site_id: int | None = None, status: str = "screening", **changes) -> int:
    with Session(engine) as session:
        if site_id is None:
            site = session.exec(select(Site).order_by(Site.id)).first()
            assert site is not None and site.id is not None
            site_id = site.id
        site = session.get(Site, site_id)
        assert site is not None
        values = {
            "trial_id": site.trial_id,
            "site_id": site_id,
            "subject_code": f"P05-{next(_IDS):05d}",
            "status": status,
            "screening_date": date.today() - timedelta(days=2),
            "enrollment_date": None,
            "randomization_date": None,
            "arm": StudyArm.NOT_RANDOMIZED.value,
            "year_of_birth": 1990,
            "age_at_enrollment": None,
            "sex": "female",
            "height_cm": None,
            "weight_kg": None,
            "prakriti": None,
            "completed_date": None,
            "withdrawal_date": None,
            "withdrawal_reason": None,
            "screen_failure_reason": None,
        }
        values.update(changes)
        subject = Subject(**values)
        session.add(subject)
        session.commit()
        session.refresh(subject)
        assert subject.id is not None
        return subject.id


def subject_and_audits(engine, subject_id: int) -> tuple[Subject, list[AuditLog]]:
    with Session(engine) as session:
        subject = session.get(Subject, subject_id)
        assert subject is not None
        session.expunge(subject)
        audits = list(
            session.exec(
                select(AuditLog)
                .where(AuditLog.entity_type == "subjects", AuditLog.entity_id == subject_id)
                .order_by(AuditLog.id)
            ).all()
        )
        for entry in audits:
            session.expunge(entry)
        return subject, audits


def assert_unchanged(engine, subject_id: int, before: dict, audit_count: int) -> None:
    subject, audits = subject_and_audits(engine, subject_id)
    assert subject.model_dump() == before
    assert len(audits) == audit_count


def test_admin_success_is_narrow_atomic_and_audited(client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    before, _ = subject_and_audits(seeded_engine, subject_id)
    response = client.patch(route(subject_id), json=payload(reason="  Not eligible  "))
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "id", "trial_id", "site_id", "subject_code", "status",
        "screen_failure_reason", "updated_at",
    }
    assert body["id"] == subject_id
    assert body["status"] == SubjectStatus.SCREEN_FAILED.value
    assert body["screen_failure_reason"] == "Not eligible"

    subject, audits = subject_and_audits(seeded_engine, subject_id)
    assert subject.status == SubjectStatus.SCREEN_FAILED.value
    assert subject.screen_failure_reason == "Not eligible"
    assert subject.screening_date == before.screening_date
    assert subject.arm == StudyArm.NOT_RANDOMIZED.value
    assert subject.enrollment_date is None
    assert subject.randomization_date is None
    assert subject.completed_date is None
    assert subject.withdrawal_date is None
    assert subject.withdrawal_reason is None
    assert subject.updated_at > before.updated_at
    assert len(audits) == 1
    entry = audits[0]
    assert entry.action == AuditAction.UPDATE.value
    assert entry.entity_type == "subjects"
    assert entry.entity_id == subject.id
    assert entry.entity_label == subject.subject_code
    assert entry.field_name == "screening_outcome"
    assert json.loads(entry.old_value) == {"status": "screening", "screen_failure_reason": None}
    assert json.loads(entry.new_value) == {
        "status": "screen_failed", "screen_failure_reason": "Not eligible"
    }
    assert entry.reason == "Subject failed screening."
    assert entry.trial_id == subject.trial_id
    assert entry.user_id is not None


@pytest.mark.parametrize("role", [UserRole.PRINCIPAL_INVESTIGATOR, UserRole.COORDINATOR])
def test_site_scoped_writers_succeed_at_assigned_site(seeded_engine, role):
    user = users_by_role(seeded_engine, role.value)[0]
    assert user.site_id is not None
    subject_id = make_subject(seeded_engine, site_id=user.site_id)
    response = client_for_user(seeded_engine, user).patch(route(subject_id), json=payload())
    assert response.status_code == 200, response.text


def test_foreign_site_is_403(seeded_engine):
    users = users_by_role(seeded_engine, UserRole.PRINCIPAL_INVESTIGATOR.value)
    caller = users[0]
    foreign = next(user for user in users[1:] if user.site_id != caller.site_id)
    assert foreign.site_id is not None
    subject_id = make_subject(seeded_engine, site_id=foreign.site_id)
    before, audits = subject_and_audits(seeded_engine, subject_id)
    response = client_for_user(seeded_engine, caller).patch(route(subject_id), json=payload())
    assert response.status_code == 403
    assert_unchanged(seeded_engine, subject_id, before.model_dump(), len(audits))


def test_anonymous_is_401(anonymous_client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    before, audits = subject_and_audits(seeded_engine, subject_id)
    assert anonymous_client.patch(route(subject_id), json=payload()).status_code == 401
    assert_unchanged(seeded_engine, subject_id, before.model_dump(), len(audits))


@pytest.mark.parametrize("role", [UserRole.SPONSOR, UserRole.ETHICS_COMMITTEE, UserRole.REGULATOR])
def test_roles_without_subject_write_are_403(role_clients, seeded_engine, role):
    subject_id = make_subject(seeded_engine)
    before, audits = subject_and_audits(seeded_engine, subject_id)
    response = role_clients[role.value].patch(route(subject_id), json=payload())
    assert response.status_code == 403
    assert "subject:write" in response.json()["detail"]
    assert_unchanged(seeded_engine, subject_id, before.model_dump(), len(audits))


def test_unknown_subject_is_404(client):
    assert client.patch(route(9_999_999), json=payload()).status_code == 404


@pytest.mark.parametrize(
    "bad_payload",
    [
        {"outcome": "screen_failed"},
        {"reason": "reason"},
        {"outcome": "screen_failed", "reason": ""},
        {"outcome": "screen_failed", "reason": "   "},
        {"outcome": "screen_failed", "reason": "x" * 501},
        {"outcome": "screen_failed", "reason": "reason", "site_id": 1},
        {"outcome": "enrolled", "reason": "reason"},
    ],
)
def test_invalid_input_is_422_without_side_effects(client, seeded_engine, bad_payload):
    subject_id = make_subject(seeded_engine)
    before, audits = subject_and_audits(seeded_engine, subject_id)
    assert client.patch(route(subject_id), json=bad_payload).status_code == 422
    assert_unchanged(seeded_engine, subject_id, before.model_dump(), len(audits))


@pytest.mark.parametrize(
    "status,changes",
    [
        (SubjectStatus.SCREEN_FAILED.value, {"screen_failure_reason": "Already failed"}),
        (SubjectStatus.ENROLLED.value, {"enrollment_date": date.today(), "randomization_date": date.today(), "arm": StudyArm.TREATMENT.value}),
        (SubjectStatus.ACTIVE.value, {"enrollment_date": date.today(), "randomization_date": date.today(), "arm": StudyArm.PLACEBO.value}),
        (SubjectStatus.COMPLETED.value, {"enrollment_date": date.today(), "randomization_date": date.today(), "arm": StudyArm.TREATMENT.value, "completed_date": date.today()}),
        (SubjectStatus.WITHDRAWN.value, {"enrollment_date": date.today(), "randomization_date": date.today(), "arm": StudyArm.PLACEBO.value, "withdrawal_date": date.today(), "withdrawal_reason": "withdrew"}),
        (SubjectStatus.LOST_TO_FOLLOW_UP.value, {"enrollment_date": date.today(), "randomization_date": date.today(), "arm": StudyArm.PLACEBO.value, "withdrawal_date": date.today(), "withdrawal_reason": "lost"}),
    ],
)
def test_invalid_source_status_is_409_without_mutation_or_audit(client, seeded_engine, status, changes):
    subject_id = make_subject(seeded_engine, status=status, **changes)
    before, audits = subject_and_audits(seeded_engine, subject_id)
    response = client.patch(route(subject_id), json=payload())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TRANSITION_NOT_ALLOWED"
    assert_unchanged(seeded_engine, subject_id, before.model_dump(), len(audits))


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"arm": StudyArm.TREATMENT.value}, "ARM_MUST_REMAIN_NOT_RANDOMIZED"),
        ({"enrollment_date": date.today()}, "ENROLLMENT_FIELDS_MUST_BE_EMPTY"),
        ({"completed_date": date.today()}, "EXIT_FIELDS_MUST_BE_EMPTY"),
        ({"withdrawal_date": date.today(), "withdrawal_reason": "exit"}, "EXIT_FIELDS_MUST_BE_EMPTY"),
    ],
)
def test_incompatible_existing_data_is_409(client, seeded_engine, changes, code):
    subject_id = make_subject(seeded_engine, **changes)
    before, audits = subject_and_audits(seeded_engine, subject_id)
    response = client.patch(route(subject_id), json=payload())
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": code,
        "message": response.json()["detail"]["message"],
    }
    assert_unchanged(seeded_engine, subject_id, before.model_dump(), len(audits))


def test_audit_failure_rolls_back_subject(monkeypatch, client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    before, audits = subject_and_audits(seeded_engine, subject_id)

    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(subjects_router.audit, "record", fail_audit)
    with pytest.raises(RuntimeError, match="audit failed"):
        client.patch(route(subject_id), json=payload())
    assert_unchanged(seeded_engine, subject_id, before.model_dump(), len(audits))


def test_calls_p03_and_does_not_publish_events(monkeypatch, client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    real_validator = subjects_router.validate_subject_transition
    calls = []

    def spy(subject, target_status, **kwargs):
        calls.append((subject.id, target_status, kwargs))
        return real_validator(subject, target_status, **kwargs)

    monkeypatch.setattr(subjects_router, "validate_subject_transition", spy)
    response = client.patch(route(subject_id), json=payload(reason="  failed  "))
    assert response.status_code == 200
    assert len(calls) == 1
    called_id, target, kwargs = calls[0]
    assert called_id == subject_id
    assert target == SubjectStatus.SCREEN_FAILED.value
    assert kwargs == {"as_of": date.today(), "screen_failure_reason": "failed"}
    assert "events" not in subjects_router.__dict__


def test_unrelated_subject_is_unchanged(client, seeded_engine):
    target_id = make_subject(seeded_engine)
    unrelated_id = make_subject(seeded_engine)
    unrelated, audits = subject_and_audits(seeded_engine, unrelated_id)
    assert client.patch(route(target_id), json=payload()).status_code == 200
    assert_unchanged(seeded_engine, unrelated_id, unrelated.model_dump(), len(audits))
