"""Focused API and generated-file tests for de-identified safety-case PDFs."""

from io import BytesIO

from pypdf import PdfReader
from sqlmodel import Session, select

from app.enums import UserRole
from app.models import AdverseEvent, Site, Subject, Trial


def first_case(engine):
    with Session(engine) as session:
        event = session.exec(select(AdverseEvent).order_by(AdverseEvent.id)).first()
        assert event is not None
        subject = session.get(Subject, event.subject_id)
        site = session.get(Site, event.site_id)
        trial = session.get(Trial, event.trial_id)
        assert subject is not None
        assert site is not None
        assert trial is not None
        return event, subject, site, trial


def extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    assert len(reader.pages) >= 1
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_export_returns_valid_deidentified_pdf(client, seeded_engine):
    event, subject, site, trial = first_case(seeded_engine)

    response = client.get(f"/api/adverse-events/{event.id}/safety-report.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="safety-report-'
    )
    assert response.content.startswith(b"%PDF-")

    text = extract_pdf_text(response.content)
    assert "DE-IDENTIFIED DEMO SAFETY CASE REPORT" in text
    assert event.ae_number in text
    assert event.term_verbatim in text
    assert subject.subject_code in text
    assert site.name in text
    assert trial.protocol_number in text
    assert "not an official regulatory submission" in text.lower()


def test_export_omits_patient_portal_and_consent_identity(client, seeded_engine):
    event, _subject, _site, _trial = first_case(seeded_engine)

    response = client.get(f"/api/adverse-events/{event.id}/safety-report.pdf")
    assert response.status_code == 200
    text = extract_pdf_text(response.content).lower()

    forbidden_identity_labels = (
        "patient name",
        "patient email",
        "signer name",
        "signature data",
        "abha",
        "ip address",
        "user agent",
        "patient request",
    )
    assert all(label not in text for label in forbidden_identity_labels)


def test_only_export_roles_can_download_report(role_clients, seeded_engine):
    event, _subject, _site, _trial = first_case(seeded_engine)
    path = f"/api/adverse-events/{event.id}/safety-report.pdf"

    for role in (UserRole.ADMIN, UserRole.SPONSOR, UserRole.REGULATOR):
        assert role_clients[role.value].get(path).status_code == 200

    for role in (
        UserRole.INSTITUTION_ADMIN,
        UserRole.PRINCIPAL_INVESTIGATOR,
        UserRole.COORDINATOR,
        UserRole.PATIENT,
        UserRole.ETHICS_COMMITTEE,
    ):
        assert role_clients[role.value].get(path).status_code == 403


def test_anonymous_export_is_denied(anonymous_client, seeded_engine):
    event, _subject, _site, _trial = first_case(seeded_engine)

    response = anonymous_client.get(
        f"/api/adverse-events/{event.id}/safety-report.pdf"
    )

    assert response.status_code == 401


def test_missing_adverse_event_returns_404(client):
    response = client.get("/api/adverse-events/999999/safety-report.pdf")

    assert response.status_code == 404
    assert response.json()["detail"] == "no adverse event with id 999999"

def test_regulator_dashboard_exposes_safety_report_actions(role_clients):
    dashboard = role_clients[UserRole.REGULATOR.value].get("/api/dashboard").json()
    block = next(item for item in dashboard["blocks"] if item["key"] == "sae_reporting")

    assert block["row_action"] == {
        "kind": "safety_report",
        "id_key": "event_id",
        "label": "PDF",
    }
    assert block["rows"]
    assert all(isinstance(row["event_id"], int) for row in block["rows"])


def test_ethics_dashboard_does_not_expose_safety_report_actions(role_clients):
    dashboard = role_clients[UserRole.ETHICS_COMMITTEE.value].get(
        "/api/dashboard"
    ).json()
    block = next(item for item in dashboard["blocks"] if item["key"] == "sae_reporting")

    assert "row_action" not in block


def test_mismatched_case_linkage_returns_controlled_409(client, seeded_engine):
    with Session(seeded_engine) as session:
        event = session.exec(select(AdverseEvent).order_by(AdverseEvent.id)).first()
        assert event is not None
        other_site = session.exec(
            select(Site).where(
                Site.trial_id == event.trial_id,
                Site.id != event.site_id,
            )
        ).first()
        assert other_site is not None
        event_id = event.id
        original_site_id = event.site_id
        event.site_id = other_site.id
        session.add(event)
        session.commit()

    try:
        response = client.get(f"/api/adverse-events/{event_id}/safety-report.pdf")
        assert response.status_code == 409
        assert response.json()["detail"] == (
            "adverse event has inconsistent trial, site, or subject linkage"
        )
    finally:
        with Session(seeded_engine) as session:
            event = session.get(AdverseEvent, event_id)
            assert event is not None
            event.site_id = original_site_id
            session.add(event)
            session.commit()
