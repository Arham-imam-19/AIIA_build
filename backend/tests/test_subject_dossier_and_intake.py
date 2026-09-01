"""Tests for Subject Intake, Dossier Timeline, Adverse Event Reporting, and Protocol Deviations."""

from datetime import date
from sqlmodel import Session, select

from app.enums import UserRole
from app.models import Subject, Trial, Visit
from tests.conftest import client_for


def test_subject_dossier_and_timeline(seeded_engine):
    with Session(seeded_engine) as session:
        subject = session.exec(select(Subject)).first()
        assert subject is not None
        subject_id = subject.id

    coordinator_client = client_for(seeded_engine, UserRole.COORDINATOR.value)
    regulator_client = client_for(seeded_engine, UserRole.REGULATOR.value)

    # 1. Test coordinator dossier access (unmasked clinical view)
    res = coordinator_client.get(f"/api/subjects/{subject_id}/dossier")
    assert res.status_code == 200
    data = res.json()
    assert "profile" in data
    assert "timeline" in data
    assert "visits" in data
    assert "adverse_events" in data

    profile = data["profile"]
    assert profile["subject_code"] == subject.subject_code
    assert profile["is_dpdp_masked"] is False
    assert len(data["timeline"]) > 0

    # 2. Test regulator dossier access (DPDP masked view)
    reg_res = regulator_client.get(f"/api/subjects/{subject_id}/dossier")
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert reg_data["profile"]["is_dpdp_masked"] is True


def test_structured_adverse_event_creation(seeded_engine):
    with Session(seeded_engine) as session:
        subject = session.exec(select(Subject)).first()
        assert subject is not None
        trial_id = subject.trial_id
        site_id = subject.site_id
        subject_id = subject.id

    coordinator_client = client_for(seeded_engine, UserRole.COORDINATOR.value)

    payload = {
        "trial_id": trial_id,
        "site_id": site_id,
        "subject_id": subject_id,
        "term_verbatim": "Severe Burning Epigastric Pain",
        "description": "Patient reported burning sensation 30 min post dose",
        "onset_date": str(date.today()),
        "severity": "severe",
        "is_serious": True,
        "seriousness_criteria": "Inpatient Hospitalization Required",
        "causality": "probable",
        "outcome": "recovering",
        "action_taken": "Dose temporarily interrupted",
        "meddra_pt_code": "10019211",
        "meddra_pt_term": "Gastritis",
        "meddra_soc": "Gastrointestinal disorders",
    }

    res = coordinator_client.post("/api/adverse-events", json=payload)
    assert res.status_code == 201
    ae = res.json()
    assert ae["term_verbatim"] == "Severe Burning Epigastric Pain"
    assert ae["is_serious"] is True
    assert ae["regulatory_urgency"] in ("EXPEDITED_DUE_SOON", "EXPEDITED_OVERDUE")


def test_structured_protocol_deviation_creation(seeded_engine):
    with Session(seeded_engine) as session:
        visit = session.exec(select(Visit)).first()
        assert visit is not None
        subject = session.get(Subject, visit.subject_id)
        assert subject is not None
        trial_id = subject.trial_id
        subject_id = subject.id
        visit_id = visit.id

    coordinator_client = client_for(seeded_engine, UserRole.COORDINATOR.value)

    payload = {
        "trial_id": trial_id,
        "subject_id": subject_id,
        "visit_id": visit_id,
        "category": "VISIT WINDOW EXCEEDED",
        "description": "Patient attended visit 8 days past allowable +3 day protocol window due to travel",
        "clinical_impact": "No safety impact on vital parameters",
        "capa": "Coordinators reminded to send automated SMS reminders 48h in advance",
        "deviation_date": str(date.today()),
    }

    res = coordinator_client.post("/api/protocol-deviations", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "recorded"
    assert "VISIT WINDOW EXCEEDED" in data["description"]
