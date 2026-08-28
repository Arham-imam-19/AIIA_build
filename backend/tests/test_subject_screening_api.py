"""Focused API tests for creating a de-identified Subject in screening."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pytest
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.enums import AuditAction, SiteStatus, StudyArm, SubjectStatus, TrialStatus, UserRole
from app.main import app
from app.models import AuditLog, Site, Subject, Trial
from app.db import get_session
from app.rbac import CurrentUser, get_current_user
from app.routers import subjects as subjects_router
from tests.conftest import ScopedClient, client_for_user, session_override, users_by_role


ROUTE = "/api/subjects"
SERVER_FIELDS = [
    "subject_code", "status", "arm", "age_at_enrollment", "enrollment_date",
    "randomization_date", "completed_date", "withdrawal_date",
    "withdrawal_reason", "screen_failure_reason", "created_at", "updated_at",
]


def today() -> date:
    return date.today()


@dataclass(frozen=True)
class TrialSiteSnapshot:
    trial_id: int
    site_id: int
    site_code: str


def trial_and_site(engine) -> TrialSiteSnapshot:
    with Session(engine) as session:
        trial = session.exec(select(Trial).order_by(Trial.id)).first()
        assert trial is not None
        site = session.exec(
            select(Site).where(Site.trial_id == trial.id).order_by(Site.id)
        ).first()
        assert site is not None
        trial.status = TrialStatus.RECRUITING.value
        site.status = SiteStatus.RECRUITING.value
        session.add(trial)
        session.add(site)
        session.commit()
        assert trial.id is not None and site.id is not None
        return TrialSiteSnapshot(
            trial_id=trial.id,
            site_id=site.id,
            site_code=site.site_code,
        )


def request_body(target: TrialSiteSnapshot, **changes) -> dict:
    body = {
        "trial_id": target.trial_id,
        "site_id": target.site_id,
        "screening_date": str(today()),
        "sex": "female",
    }
    body.update(changes)
    return body


def counts(session: Session) -> tuple[int, int]:
    subjects = session.exec(select(func.count()).select_from(Subject)).one()
    audits = session.exec(select(func.count()).select_from(AuditLog)).one()
    return subjects, audits


def assert_no_change(engine, before: tuple[int, int]) -> None:
    with Session(engine) as session:
        assert counts(session) == before


def test_admin_creates_exact_screening_state_and_one_audit(client, seeded_engine):
    target = trial_and_site(seeded_engine)
    with Session(seeded_engine) as session:
        before = counts(session)

    response = client.post(
        ROUTE,
        json=request_body(
            target, year_of_birth=1990, height_cm=162.5, weight_kg=61.0
        ),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {
        "id", "trial_id", "site_id", "subject_code", "status", "arm",
        "screening_date", "sex", "year_of_birth", "height_cm", "weight_kg",
        "created_at", "updated_at",
    }
    assert body["trial_id"] == target.trial_id
    assert body["site_id"] == target.site_id
    assert body["subject_code"].startswith(f"AIIA-ASH-{target.site_code}-")
    assert body["status"] == SubjectStatus.SCREENING.value
    assert body["arm"] == StudyArm.NOT_RANDOMIZED.value
    assert body["created_at"] == body["updated_at"]

    with Session(seeded_engine) as session:
        assert counts(session) == (before[0] + 1, before[1] + 1)
        subject = session.get(Subject, body["id"])
        assert subject is not None
        assert subject.model_dump(exclude={"id", "trial_id", "site_id", "subject_code", "created_at", "updated_at"}) == {
            "status": "screening", "screening_date": today(),
            "enrollment_date": None, "randomization_date": None,
            "arm": "not_randomized", "year_of_birth": 1990,
            "age_at_enrollment": None, "sex": "female", "height_cm": 162.5,
            "weight_kg": 61.0, "prakriti": None,
            "assigned_researcher_id": None, "user_id": None,
            "completed_date": None,
            "withdrawal_date": None, "withdrawal_reason": None,
            "screen_failure_reason": None,
        }
        audit = session.exec(select(AuditLog).order_by(AuditLog.id.desc())).first()
        assert audit is not None
        assert audit.action == AuditAction.CREATE.value
        assert audit.entity_type == "subjects"
        assert audit.entity_id == subject.id
        assert audit.entity_label == subject.subject_code
        assert audit.trial_id == target.trial_id
        assert audit.reason == "Subject entered screening."
        assert audit.user_id is not None


@pytest.mark.parametrize("role", [UserRole.PRINCIPAL_INVESTIGATOR, UserRole.COORDINATOR])
@pytest.mark.parametrize("include_site", [False, True])
def test_scoped_writer_uses_assigned_site(seeded_engine, role, include_site):
    user = users_by_role(seeded_engine, role.value)[0]
    assert user.site_id is not None
    with Session(seeded_engine) as session:
        site = session.get(Site, user.site_id)
        assert site is not None
        trial = session.get(Trial, site.trial_id)
        assert trial is not None
        assert trial.id is not None and site.id is not None
        target = TrialSiteSnapshot(trial.id, site.id, site.site_code)
    payload = request_body(target)
    if not include_site:
        del payload["site_id"]
    response = client_for_user(seeded_engine, user).post(ROUTE, json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["site_id"] == user.site_id
    assert response.json()["year_of_birth"] is None
    assert response.json()["height_cm"] is None
    assert response.json()["weight_kg"] is None


def test_anonymous_request_is_401_without_side_effects(anonymous_client, seeded_engine):
    target = trial_and_site(seeded_engine)
    with Session(seeded_engine) as session:
        before = counts(session)
    assert anonymous_client.post(ROUTE, json=request_body(target)).status_code == 401
    assert_no_change(seeded_engine, before)


@pytest.mark.parametrize(
    "role", [UserRole.SPONSOR, UserRole.ETHICS_COMMITTEE, UserRole.REGULATOR]
)
def test_roles_without_subject_write_are_403(role_clients, seeded_engine, role):
    target = trial_and_site(seeded_engine)
    with Session(seeded_engine) as session:
        before = counts(session)
    response = role_clients[role.value].post(ROUTE, json=request_body(target))
    assert response.status_code == 403
    assert "subject:write" in response.json()["detail"]
    assert_no_change(seeded_engine, before)


def test_scoped_writer_requesting_foreign_site_is_403(seeded_engine):
    users = users_by_role(seeded_engine, UserRole.PRINCIPAL_INVESTIGATOR.value)
    assert len(users) >= 2
    caller = users[0]
    with Session(seeded_engine) as session:
        own_site = session.get(Site, caller.site_id)
        foreign_site = session.get(Site, users[1].site_id)
        assert own_site is not None and foreign_site is not None
        trial = session.get(Trial, own_site.trial_id)
        assert trial is not None
        assert trial.id is not None and foreign_site.id is not None
        target = TrialSiteSnapshot(trial.id, foreign_site.id, foreign_site.site_code)
        before = counts(session)
    response = client_for_user(seeded_engine, caller).post(
        ROUTE, json=request_body(target)
    )
    assert response.status_code == 403
    assert_no_change(seeded_engine, before)


def test_scoped_writer_cannot_request_a_trial_other_than_the_assigned_sites(
    seeded_engine,
):
    target = trial_and_site(seeded_engine)
    caller = users_by_role(seeded_engine, UserRole.COORDINATOR.value)[0]
    assert caller.site_id == target.site_id or caller.site_id is not None
    with Session(seeded_engine) as session:
        assigned_site = session.get(Site, caller.site_id)
        assert assigned_site is not None
        trial = session.get(Trial, target.trial_id)
        assert trial is not None
        values = trial.model_dump(exclude={"id"})
        values.update(
            protocol_number="SYNTHETIC-P04-SCOPED-OTHER",
            ctri_number=None,
            ctri_registration_date=None,
        )
        other = Trial(**values)
        session.add(other)
        session.commit()
        session.refresh(other)
        assert other.id is not None and assigned_site.id is not None
        request_target = TrialSiteSnapshot(
            other.id, assigned_site.id, assigned_site.site_code
        )
        before = counts(session)
    payload = request_body(request_target)
    del payload["site_id"]
    response = client_for_user(seeded_engine, caller).post(ROUTE, json=payload)
    assert response.status_code == 404
    assert_no_change(seeded_engine, before)


@pytest.mark.parametrize("site_id", [None, 999999])
def test_scoped_writer_with_invalid_assignment_is_409(seeded_engine, site_id):
    target = trial_and_site(seeded_engine)
    caller = CurrentUser(
        id=999999,
        email="invalid-scope@example.test",
        full_name="Invalid Scope",
        role=UserRole.COORDINATOR.value,
        site_id=site_id,
    )

    async def override_user() -> CurrentUser:
        return caller

    scoped_client = ScopedClient(
        app,
        overrides={
            get_session: session_override(seeded_engine),
            get_current_user: override_user,
        },
    )
    payload = request_body(target)
    del payload["site_id"]
    with Session(seeded_engine) as session:
        before = counts(session)
    response = scoped_client.post(ROUTE, json=payload)
    assert response.status_code == 409
    assert_no_change(seeded_engine, before)


def test_unrestricted_writer_requires_site_id(client, seeded_engine):
    target = trial_and_site(seeded_engine)
    payload = request_body(target)
    del payload["site_id"]
    assert client.post(ROUTE, json=payload).status_code == 404


@pytest.mark.parametrize("missing", ["trial_id", "screening_date", "sex"])
def test_required_fields_are_required(client, seeded_engine, missing):
    target = trial_and_site(seeded_engine)
    payload = request_body(target)
    del payload[missing]
    assert client.post(ROUTE, json=payload).status_code == 422


@pytest.mark.parametrize("field", SERVER_FIELDS + ["prakriti", "name", "address", "medical_record_id"])
def test_server_controlled_identifying_and_unknown_fields_are_rejected(
    client, seeded_engine, field
):
    target = trial_and_site(seeded_engine)
    payload = request_body(target)
    payload[field] = "not allowed"
    assert client.post(ROUTE, json=payload).status_code == 422


@pytest.mark.parametrize(
    "changes",
    [
        {"sex": "invalid"},
        {"screening_date": str(today() + timedelta(days=1))},
        {"year_of_birth": today().year + 1},
        {"height_cm": 0}, {"height_cm": -1}, {"height_cm": "Infinity"},
        {"weight_kg": 0}, {"weight_kg": -1}, {"weight_kg": "NaN"},
    ],
)
def test_invalid_values_are_422_without_side_effects(client, seeded_engine, changes):
    target = trial_and_site(seeded_engine)
    with Session(seeded_engine) as session:
        before = counts(session)
    assert client.post(ROUTE, json=request_body(target, **changes)).status_code == 422
    assert_no_change(seeded_engine, before)


def test_missing_trial_and_site_are_404(client, seeded_engine):
    target = trial_and_site(seeded_engine)
    with Session(seeded_engine) as session:
        before = counts(session)
    assert client.post(ROUTE, json=request_body(target, trial_id=999999)).status_code == 404
    assert client.post(ROUTE, json=request_body(target, site_id=999999)).status_code == 404
    assert_no_change(seeded_engine, before)


def test_cross_trial_site_is_404(client, seeded_engine):
    target = trial_and_site(seeded_engine)
    with Session(seeded_engine) as session:
        trial = session.get(Trial, target.trial_id)
        assert trial is not None
        values = trial.model_dump(exclude={"id"})
        values.update(
            protocol_number="SYNTHETIC-P04-OTHER",
            ctri_number=None,
            ctri_registration_date=None,
        )
        other = Trial(**values)
        session.add(other)
        session.commit()
        session.refresh(other)
        assert other.id is not None
        request_target = TrialSiteSnapshot(other.id, target.site_id, target.site_code)
    response = client.post(ROUTE, json=request_body(request_target))
    assert response.status_code == 404


@pytest.mark.parametrize("status", [s.value for s in TrialStatus if s is not TrialStatus.RECRUITING])
def test_non_recruiting_trial_is_409(client, seeded_engine, status):
    target = trial_and_site(seeded_engine)
    with Session(seeded_engine) as session:
        stored = session.get(Trial, target.trial_id)
        assert stored is not None
        stored.status = status
        session.add(stored)
        session.commit()
        before = counts(session)
    assert client.post(ROUTE, json=request_body(target)).status_code == 409
    assert_no_change(seeded_engine, before)


@pytest.mark.parametrize(
    "status", [SiteStatus.PLANNED, SiteStatus.ACTIVATED, SiteStatus.SUSPENDED, SiteStatus.CLOSED]
)
def test_non_recruiting_site_is_409(client, seeded_engine, status):
    target = trial_and_site(seeded_engine)
    with Session(seeded_engine) as session:
        stored = session.get(Site, target.site_id)
        assert stored is not None
        stored.status = status.value
        session.add(stored)
        session.commit()
        before = counts(session)
    assert client.post(ROUTE, json=request_body(target)).status_code == 409
    assert_no_change(seeded_engine, before)


def test_code_uses_highest_valid_tail_and_ignores_unrelated_codes(client, seeded_engine):
    target = trial_and_site(seeded_engine)
    with Session(seeded_engine) as session:
        template = session.exec(select(Subject).where(Subject.site_id == target.site_id)).first()
        assert template is not None
        values = template.model_dump(exclude={"id", "subject_code"})
        session.add(Subject(subject_code=f"AIIA-ASH-{target.site_code}-999", **values))
        session.add(Subject(subject_code=f"OTHER-{target.site_code}-5000", **values))
        session.add(Subject(subject_code=f"AIIA-ASH-{target.site_code}-NOT-A-NUMBER", **values))
        session.commit()
    response = client.post(ROUTE, json=request_body(target))
    assert response.status_code == 201, response.text
    assert response.json()["subject_code"] == f"AIIA-ASH-{target.site_code}-1000"


def test_unique_code_collision_is_409_and_rolls_back(client, seeded_engine, monkeypatch):
    target = trial_and_site(seeded_engine)
    with Session(seeded_engine) as session:
        existing = session.exec(select(Subject).where(Subject.site_id == target.site_id)).first()
        assert existing is not None
        existing_code = existing.subject_code
        before = counts(session)
    monkeypatch.setattr(subjects_router, "_next_subject_code", lambda *_: existing_code)
    response = client.post(ROUTE, json=request_body(target))
    assert response.status_code == 409
    assert_no_change(seeded_engine, before)


def test_unrelated_integrity_error_is_not_mislabeled(client, seeded_engine, monkeypatch):
    target = trial_and_site(seeded_engine)
    error = IntegrityError("insert", {}, Exception("different constraint"))
    monkeypatch.setattr(Session, "flush", lambda *_args, **_kwargs: (_ for _ in ()).throw(error))
    with pytest.raises(IntegrityError):
        client.post(ROUTE, json=request_body(target))


def test_audit_failure_rolls_back_subject(client, seeded_engine, monkeypatch):
    target = trial_and_site(seeded_engine)
    with Session(seeded_engine) as session:
        before = counts(session)
    monkeypatch.setattr(subjects_router.audit, "record", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("audit failed")))
    with pytest.raises(RuntimeError, match="audit failed"):
        client.post(ROUTE, json=request_body(target))
    assert_no_change(seeded_engine, before)
