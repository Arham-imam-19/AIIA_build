"""Focused API tests for enrolling and randomizing a screening Subject."""

from __future__ import annotations

import json
from datetime import date, timedelta
from itertools import count

import pytest
from sqlmodel import Session, select

from app.enums import AuditAction, SiteStatus, StudyArm, SubjectStatus, TrialStatus, UserRole
from app.models import AuditLog, Site, Subject, Trial
from app.routers import subjects as subjects_router
from tests.conftest import client_for_user, users_by_role


_IDS = count(1)


def route(subject_id: int) -> str:
    return f"/api/subjects/{subject_id}/enrollment"


def payload(**changes) -> dict:
    today = date.today().isoformat()
    body = {"enrollment_date": today, "randomization_date": today, "arm": "treatment"}
    body.update(changes)
    return body


def make_subject(engine, *, site_id: int | None = None, status: str = "screening", **changes) -> int:
    with Session(engine) as session:
        site = session.get(Site, site_id) if site_id is not None else session.exec(select(Site).order_by(Site.id)).first()
        assert site is not None and site.id is not None
        values = {
            "trial_id": site.trial_id,
            "site_id": site.id,
            "subject_code": f"P06-{next(_IDS):05d}",
            "status": status,
            "screening_date": date.today() - timedelta(days=7),
            "enrollment_date": None,
            "randomization_date": None,
            "arm": StudyArm.NOT_RANDOMIZED.value,
            "year_of_birth": 1990,
            "age_at_enrollment": None,
            "sex": "female",
            "height_cm": 160.0,
            "weight_kg": 55.0,
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


def snapshot(engine, subject_id: int) -> tuple[Subject, list[AuditLog]]:
    with Session(engine) as session:
        subject = session.get(Subject, subject_id)
        assert subject is not None
        session.expunge(subject)
        audits = list(session.exec(select(AuditLog).where(AuditLog.entity_type == "subjects", AuditLog.entity_id == subject_id).order_by(AuditLog.id)).all())
        for entry in audits:
            session.expunge(entry)
        return subject, audits


def assert_unchanged(engine, subject_id: int, before: Subject, audit_count: int) -> None:
    after, audits = snapshot(engine, subject_id)
    assert after.model_dump() == before.model_dump()
    assert len(audits) == audit_count


def test_admin_success_exact_response_persistence_timestamp_and_audit(client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    before, _ = snapshot(seeded_engine, subject_id)
    response = client.patch(route(subject_id), json=payload(arm="comparator", prakriti="vata_pitta"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"id", "trial_id", "site_id", "subject_code", "status", "enrollment_date", "randomization_date", "arm", "prakriti", "updated_at"}
    assert body["id"] == subject_id
    assert body["status"] == SubjectStatus.ENROLLED.value
    assert body["arm"] == StudyArm.COMPARATOR.value
    assert body["prakriti"] == "vata_pitta"

    subject, audits = snapshot(seeded_engine, subject_id)
    assert subject.updated_at > before.updated_at
    assert subject.age_at_enrollment is None
    assert subject.screening_date == before.screening_date
    assert subject.screen_failure_reason is None
    assert subject.completed_date is None
    assert subject.withdrawal_date is None
    assert subject.withdrawal_reason is None
    assert len(audits) == 1
    entry = audits[0]
    assert (entry.action, entry.entity_type, entry.entity_id, entry.entity_label) == (AuditAction.UPDATE.value, "subjects", subject.id, subject.subject_code)
    assert entry.field_name == "enrollment"
    assert json.loads(entry.old_value) == {"status": "screening", "enrollment_date": None, "randomization_date": None, "arm": "not_randomized", "prakriti": None}
    assert json.loads(entry.new_value) == {"status": "enrolled", "enrollment_date": date.today().isoformat(), "randomization_date": date.today().isoformat(), "arm": "comparator", "prakriti": "vata_pitta"}
    assert entry.reason == "Subject enrolled and randomized."
    assert entry.trial_id == subject.trial_id
    assert entry.user_id is not None


@pytest.mark.parametrize("role", [UserRole.PRINCIPAL_INVESTIGATOR, UserRole.COORDINATOR])
def test_assigned_site_writer_succeeds(seeded_engine, role):
    user = users_by_role(seeded_engine, role.value)[0]
    assert user.site_id is not None
    subject_id = make_subject(seeded_engine, site_id=user.site_id)
    assert client_for_user(seeded_engine, user).patch(route(subject_id), json=payload()).status_code == 200


def test_omitted_prakriti_stays_null_and_dates_may_differ(client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    enrollment = date.today() - timedelta(days=2)
    response = client.patch(route(subject_id), json=payload(enrollment_date=enrollment.isoformat(), arm="placebo"))
    assert response.status_code == 200
    assert response.json()["prakriti"] is None
    assert response.json()["enrollment_date"] == enrollment.isoformat()
    assert response.json()["randomization_date"] == date.today().isoformat()


def test_anonymous_is_401(anonymous_client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    assert anonymous_client.patch(route(subject_id), json=payload()).status_code == 401


@pytest.mark.parametrize("role", [UserRole.SPONSOR, UserRole.ETHICS_COMMITTEE, UserRole.REGULATOR])
def test_roles_without_permission_are_403(role_clients, seeded_engine, role):
    subject_id = make_subject(seeded_engine)
    assert role_clients[role.value].patch(route(subject_id), json=payload()).status_code == 403


def test_foreign_site_is_403(seeded_engine):
    users = users_by_role(seeded_engine, UserRole.PRINCIPAL_INVESTIGATOR.value)
    caller = users[0]
    foreign = next(user for user in users[1:] if user.site_id != caller.site_id)
    subject_id = make_subject(seeded_engine, site_id=foreign.site_id)
    assert client_for_user(seeded_engine, caller).patch(route(subject_id), json=payload()).status_code == 403


def test_missing_subject_is_404(client):
    assert client.patch(route(9_999_999), json=payload()).status_code == 404


@pytest.mark.parametrize("bad", [
    {"randomization_date": date.today().isoformat(), "arm": "treatment"},
    {"enrollment_date": date.today().isoformat(), "arm": "treatment"},
    {"enrollment_date": date.today().isoformat(), "randomization_date": date.today().isoformat()},
    {"enrollment_date": "bad", "randomization_date": date.today().isoformat(), "arm": "treatment"},
    payload(arm="invalid"), payload(arm="not_randomized"), payload(prakriti="invalid"),
    payload(trial_id=1), payload(site_id=1), payload(status="enrolled"),
    payload(screening_date=date.today().isoformat()), payload(screen_failure_reason="failed"),
    payload(completed_date=date.today().isoformat()), payload(withdrawal_reason="left"),
    payload(created_at="now"), payload(age_at_enrollment=36),
])
def test_invalid_request_is_422_without_side_effects(client, seeded_engine, bad):
    subject_id = make_subject(seeded_engine)
    before, audits = snapshot(seeded_engine, subject_id)
    assert client.patch(route(subject_id), json=bad).status_code == 422
    assert_unchanged(seeded_engine, subject_id, before, len(audits))


@pytest.mark.parametrize("changes,code", [
    ({"enrollment_date": (date.today() - timedelta(days=8)).isoformat()}, "ENROLLMENT_DATES_OUT_OF_ORDER"),
    ({"randomization_date": (date.today() - timedelta(days=1)).isoformat()}, "ENROLLMENT_DATES_OUT_OF_ORDER"),
    ({"enrollment_date": (date.today() + timedelta(days=1)).isoformat(), "randomization_date": (date.today() + timedelta(days=1)).isoformat()}, "FUTURE_SUBJECT_DATE"),
])
def test_date_conflicts_are_structured_409(client, seeded_engine, changes, code):
    subject_id = make_subject(seeded_engine)
    response = client.patch(route(subject_id), json=payload(**changes))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == code


@pytest.mark.parametrize("status,changes", [
    (SubjectStatus.SCREEN_FAILED.value, {"screen_failure_reason": "failed"}),
    (SubjectStatus.ACTIVE.value, {"enrollment_date": date.today(), "randomization_date": date.today(), "arm": "treatment"}),
    (SubjectStatus.COMPLETED.value, {"enrollment_date": date.today(), "randomization_date": date.today(), "arm": "treatment", "completed_date": date.today()}),
    (SubjectStatus.WITHDRAWN.value, {"enrollment_date": date.today(), "randomization_date": date.today(), "arm": "treatment", "withdrawal_date": date.today(), "withdrawal_reason": "left"}),
    (SubjectStatus.LOST_TO_FOLLOW_UP.value, {"enrollment_date": date.today(), "randomization_date": date.today(), "arm": "treatment", "withdrawal_date": date.today(), "withdrawal_reason": "lost"}),
])
def test_non_screening_sources_are_409(client, seeded_engine, status, changes):
    subject_id = make_subject(seeded_engine, status=status, **changes)
    response = client.patch(route(subject_id), json=payload())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TRANSITION_NOT_ALLOWED"


def test_incompatible_existing_lifecycle_state_is_409(client, seeded_engine):
    subject_id = make_subject(seeded_engine, completed_date=date.today())
    response = client.patch(route(subject_id), json=payload())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OUTCOME_FIELDS_MUST_BE_EMPTY"


@pytest.mark.parametrize("entity", ["trial", "site"])
def test_non_recruiting_trial_or_site_is_409(client, seeded_engine, entity):
    subject_id = make_subject(seeded_engine)
    with Session(seeded_engine) as session:
        subject = session.get(Subject, subject_id)
        assert subject is not None
        trial_id = subject.trial_id
        site_id = subject.site_id
        row = session.get(Trial, trial_id) if entity == "trial" else session.get(Site, site_id)
        assert row is not None
        original = row.status
        row.status = TrialStatus.ACTIVE.value if entity == "trial" else SiteStatus.SUSPENDED.value
        session.add(row)
        session.commit()
    try:
        assert client.patch(route(subject_id), json=payload()).status_code == 409
    finally:
        with Session(seeded_engine) as session:
            row = session.get(Trial, trial_id) if entity == "trial" else session.get(Site, site_id)
            row.status = original
            session.add(row)
            session.commit()


def test_broken_trial_site_linkage_is_409(client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    with Session(seeded_engine) as session:
        subject = session.get(Subject, subject_id)
        values = session.get(Trial, subject.trial_id).model_dump(exclude={"id"})
        values.update(
            title=f"P06 other {subject_id}",
            protocol_number=f"P06-OTHER-{subject_id}",
            ctri_number=None,
        )
        other_trial = Trial(**values)
        session.add(other_trial)
        session.commit()
        session.refresh(other_trial)
        subject.trial_id = other_trial.id
        session.add(subject)
        session.commit()
    assert client.patch(route(subject_id), json=payload()).status_code == 409


def test_exact_p03_call_and_no_event_publication(monkeypatch, client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    real = subjects_router.validate_subject_transition
    calls = []
    def spy(subject, target, **kwargs):
        calls.append((subject.id, target, kwargs))
        return real(subject, target, **kwargs)
    monkeypatch.setattr(subjects_router, "validate_subject_transition", spy)
    assert client.patch(route(subject_id), json=payload(arm="placebo")).status_code == 200
    assert calls == [(subject_id, SubjectStatus.ENROLLED.value, {"as_of": date.today(), "enrollment_date": date.today(), "randomization_date": date.today(), "arm": "placebo"})]
    assert "events" not in subjects_router.__dict__


def test_audit_failure_rolls_back(monkeypatch, client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    before, audits = snapshot(seeded_engine, subject_id)
    monkeypatch.setattr(subjects_router.audit, "record", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("audit failed")))
    with pytest.raises(RuntimeError, match="audit failed"):
        client.patch(route(subject_id), json=payload())
    assert_unchanged(seeded_engine, subject_id, before, len(audits))


def test_repeated_request_has_one_success_and_one_audit(client, seeded_engine):
    subject_id = make_subject(seeded_engine)
    assert client.patch(route(subject_id), json=payload()).status_code == 200
    second = client.patch(route(subject_id), json=payload())
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "TRANSITION_NOT_ALLOWED"
    assert len(snapshot(seeded_engine, subject_id)[1]) == 1


def test_unrelated_subject_remains_unchanged(client, seeded_engine):
    target_id = make_subject(seeded_engine)
    other_id = make_subject(seeded_engine)
    before, audits = snapshot(seeded_engine, other_id)
    assert client.patch(route(target_id), json=payload()).status_code == 200
    assert_unchanged(seeded_engine, other_id, before, len(audits))
