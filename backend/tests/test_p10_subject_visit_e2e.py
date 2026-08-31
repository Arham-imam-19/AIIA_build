"""Narrow end-to-end production Subject and Visit lifecycle test."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.enums import SiteStatus, SubjectStatus, TrialStatus, VisitStatus
from app.models import AuditLog, Site, Subject, Trial, Visit


def recruiting_trial_site(engine) -> tuple[int, int]:
    with Session(engine) as session:
        trial = session.exec(select(Trial).order_by(Trial.id)).first()
        assert trial is not None and trial.id is not None
        site = session.exec(
            select(Site).where(Site.trial_id == trial.id).order_by(Site.id)
        ).first()
        assert site is not None and site.id is not None
        trial.status = TrialStatus.RECRUITING.value
        site.status = SiteStatus.RECRUITING.value
        session.add(trial)
        session.add(site)
        session.commit()
        return trial.id, site.id


def test_complete_subject_and_visit_api_lifecycle(client, seeded_engine):
    trial_id, site_id = recruiting_trial_site(seeded_engine)
    today = date.today().isoformat()

    screening = client.post("/api/subjects", json={
        "trial_id": trial_id,
        "site_id": site_id,
        "screening_date": today,
        "sex": "female",
        "year_of_birth": 1990,
    })
    assert screening.status_code == 201, screening.text
    subject_id = screening.json()["id"]

    enrollment = client.patch(f"/api/subjects/{subject_id}/enrollment", json={
        "enrollment_date": today,
        "randomization_date": today,
        "arm": "treatment",
        "prakriti": "vata_pitta",
    })
    assert enrollment.status_code == 200, enrollment.text

    activation = client.patch(f"/api/subjects/{subject_id}/activation", json={})
    assert activation.status_code == 200, activation.text

    scheduling = client.post(f"/api/subjects/{subject_id}/visits", json={
        "visit_name": "Baseline",
        "visit_number": 1,
        "visit_day": 0,
        "scheduled_date": today,
    })
    assert scheduling.status_code == 201, scheduling.text
    visit_id = scheduling.json()["id"]

    visit_outcome = client.patch(f"/api/visits/{visit_id}/outcome", json={
        "status": "completed",
        "actual_date": today,
        "is_protocol_deviation": False,
        "deviation_description": None,
    })
    assert visit_outcome.status_code == 200, visit_outcome.text

    subject_outcome = client.patch(f"/api/subjects/{subject_id}/outcome", json={
        "status": "completed",
        "completed_date": today,
        "withdrawal_date": None,
        "withdrawal_reason": None,
    })
    assert subject_outcome.status_code == 200, subject_outcome.text

    with Session(seeded_engine) as session:
        subject = session.get(Subject, subject_id)
        visit = session.get(Visit, visit_id)
        assert subject is not None and subject.status == SubjectStatus.COMPLETED.value
        assert visit is not None and visit.status == VisitStatus.COMPLETED.value
        audits = list(session.exec(select(AuditLog).where(
            ((AuditLog.entity_type == "subjects") & (AuditLog.entity_id == subject_id))
            | ((AuditLog.entity_type == "visits") & (AuditLog.entity_id == visit_id))
        ).order_by(AuditLog.id)).all())
        assert len(audits) == 6
        assert [entry.field_name for entry in audits] == [
            None, "enrollment", "activation", "schedule", "outcome", "outcome"
        ]


def test_visit_outcome_before_activation_is_controlled_conflict(client, seeded_engine):
    trial_id, site_id = recruiting_trial_site(seeded_engine)
    today = date.today().isoformat()
    screening = client.post("/api/subjects", json={
        "trial_id": trial_id, "site_id": site_id,
        "screening_date": today, "sex": "male",
    })
    subject_id = screening.json()["id"]
    assert client.patch(f"/api/subjects/{subject_id}/enrollment", json={
        "enrollment_date": today, "randomization_date": today, "arm": "placebo",
    }).status_code == 200
    scheduling = client.post(f"/api/subjects/{subject_id}/visits", json={
        "visit_name": "Baseline", "visit_number": 1,
        "visit_day": 0, "scheduled_date": today,
    })
    assert scheduling.status_code == 201
    response = client.patch(f"/api/visits/{scheduling.json()['id']}/outcome", json={
        "status": "completed", "actual_date": today,
        "is_protocol_deviation": False, "deviation_description": None,
    })
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SUBJECT_NOT_ACTIVE"
