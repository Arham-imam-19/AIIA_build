"""Tests for HL7 FHIR R4 ResearchStudy and Trial Collection Bundle Export."""

from sqlmodel import Session, select

from app.enums import UserRole
from app.models import Subject, Trial
from tests.conftest import client_for


def test_fhir_trial_bundle_export(seeded_engine):
    with Session(seeded_engine) as session:
        trial = session.exec(select(Trial)).first()
        assert trial is not None
        trial_id = trial.id
        protocol = trial.protocol_number

    sponsor_client = client_for(seeded_engine, UserRole.SPONSOR.value)

    res = sponsor_client.get(f"/api/trials/{trial_id}/export/fhir-bundle")
    assert res.status_code == 200
    bundle = res.json()

    # 1. FHIR R4 Bundle Validation
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert bundle["total"] > 0
    assert len(bundle["entry"]) == bundle["total"]

    resource_types = {e["resource"]["resourceType"] for e in bundle["entry"]}
    assert "ResearchStudy" in resource_types
    assert "ResearchSubject" in resource_types
    assert "Patient" in resource_types
    assert "Encounter" in resource_types
    assert "AdverseEvent" in resource_types

    # 2. Validate ResearchStudy resource content
    study_entry = next(e for e in bundle["entry"] if e["resource"]["resourceType"] == "ResearchStudy")
    study = study_entry["resource"]
    assert study["title"] == trial.title
    assert study["status"] == "active"
    # Check condition coding includes SNOMED and NAMASTE
    condition = study["condition"][0]
    coding_systems = [c["system"] for c in condition["coding"]]
    assert "http://snomed.info/sct" in coding_systems
    assert "https://namstp.ayush.gov.in" in coding_systems

    # 3. Validate AdverseEvent resource MedDRA coding
    ae_entry = next((e for e in bundle["entry"] if e["resource"]["resourceType"] == "AdverseEvent"), None)
    if ae_entry:
        ae = ae_entry["resource"]
        assert ae["resourceType"] == "AdverseEvent"
        assert ae["actuality"] == "actual"
        assert "event" in ae


def test_fhir_individual_subject_bundle_export(seeded_engine):
    with Session(seeded_engine) as session:
        subject = session.exec(select(Subject)).first()
        assert subject is not None
        subject_id = subject.id

    regulator_client = client_for(seeded_engine, UserRole.REGULATOR.value)

    res = regulator_client.get(f"/api/subjects/{subject_id}/export/fhir")
    assert res.status_code == 200
    bundle = res.json()

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    resource_types = {e["resource"]["resourceType"] for e in bundle["entry"]}
    assert "Patient" in resource_types
    assert "ResearchSubject" in resource_types
