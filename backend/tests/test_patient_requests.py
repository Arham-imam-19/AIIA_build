"""Focused contract tests for patient-request validation."""

import pytest
from pydantic import ValidationError

from app.routers.patient_requests import (
    CreatePatientRequest,
    RespondPatientRequest,
)
from sqlmodel import Session, select

from app.enums import PatientRequestCategory, PatientRequestStatus, UserRole
from app.models import PatientRequest, User

def test_create_request_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        CreatePatientRequest(
            category="not_a_real_category",
            subject_line="Validation probe",
            message="This must be rejected before reaching the database.",
        )
def test_response_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        RespondPatientRequest(
            response="Validation probe response.",
            status="not_a_real_status",
        )
def test_response_cannot_reset_request_to_submitted() -> None:
    with pytest.raises(ValidationError):
        RespondPatientRequest(
            response="A handled request must not return to its initial state.",
            status="submitted",
        )
def test_patient_list_contains_only_their_own_requests(
    role_clients,
    seeded_engine,
) -> None:
    patient_client = role_clients[UserRole.PATIENT.value]

    with Session(seeded_engine) as session:
        patient_user = session.exec(
            select(User)
            .where(User.role == UserRole.PATIENT.value)
            .order_by(User.id)
        ).first()
        assert patient_user is not None

    response = patient_client.get("/api/patient-requests")

    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert all(
        item["patient_user_id"] == patient_user.id
        for item in items
    )


def test_patient_cannot_read_another_patients_request(
    role_clients,
    seeded_engine,
) -> None:
    patient_client = role_clients[UserRole.PATIENT.value]

    with Session(seeded_engine) as session:
        patient_user = session.exec(
            select(User)
            .where(User.role == UserRole.PATIENT.value)
            .order_by(User.id)
        ).first()
        assert patient_user is not None

        other_request = session.exec(
            select(PatientRequest).where(
                PatientRequest.patient_user_id != patient_user.id
            )
        ).first()
        assert other_request is not None
        other_request_id = other_request.id

    response = patient_client.get(
        f"/api/patient-requests/{other_request_id}"
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "cannot view another patient's request"
@pytest.mark.parametrize(
    "role",
    [
        UserRole.INSTITUTION_ADMIN.value,
        UserRole.PRINCIPAL_INVESTIGATOR.value,
        UserRole.COORDINATOR.value,
    ],
)
def test_site_scoped_staff_cannot_read_other_site_requests(
    role_clients,
    seeded_engine,
    role: str,
) -> None:
    staff_client = role_clients[role]

    with Session(seeded_engine) as session:
        staff_user = session.exec(
            select(User)
            .where(User.role == role)
            .order_by(User.id)
        ).first()
        assert staff_user is not None
        assert staff_user.site_id is not None

        other_request = session.exec(
            select(PatientRequest).where(
                PatientRequest.site_id != staff_user.site_id
            )
        ).first()
        assert other_request is not None
        other_request_id = other_request.id

    list_response = staff_client.get("/api/patient-requests")

    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert items
    assert all(
        item["site_id"] == staff_user.site_id
        for item in items
    )

    detail_response = staff_client.get(
        f"/api/patient-requests/{other_request_id}"
    )

    assert detail_response.status_code == 403
@pytest.mark.parametrize(
    "role",
    [
        UserRole.SPONSOR.value,
        UserRole.ETHICS_COMMITTEE.value,
        UserRole.REGULATOR.value,
    ],
)
def test_unassigned_oversight_roles_cannot_read_patient_requests(
    role_clients,
    role: str,
) -> None:
    response = role_clients[role].get("/api/patient-requests")

    assert response.status_code == 403
    assert "patient_request:read" in response.json()["detail"]
def test_patient_creation_derives_ownership_from_authenticated_user(
    role_clients,
    seeded_engine,
) -> None:
    patient_client = role_clients[UserRole.PATIENT.value]

    with Session(seeded_engine) as session:
        patient_user = session.exec(
            select(User)
            .where(User.role == UserRole.PATIENT.value)
            .order_by(User.id)
        ).first()
        assert patient_user is not None
        assert patient_user.site_id is not None
        assert patient_user.subject_id is not None

        other_site_request = session.exec(
            select(PatientRequest).where(
                PatientRequest.site_id != patient_user.site_id
            )
        ).first()
        assert other_site_request is not None
        other_site_id = other_site_request.site_id

    response = patient_client.post(
        "/api/patient-requests",
        json={
            "category": PatientRequestCategory.GENERAL_INQUIRY.value,
            "subject_line": "Automated ownership test",
            "message": "This request exists only inside the isolated test database.",
            "site_id": other_site_id,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["patient_user_id"] == patient_user.id
    assert body["subject_id"] == patient_user.subject_id
    assert body["site_id"] == patient_user.site_id
    assert body["category"] == PatientRequestCategory.GENERAL_INQUIRY.value
    assert body["status"] == PatientRequestStatus.SUBMITTED.value
def test_only_authorized_same_site_admin_can_respond(
    role_clients,
) -> None:
    patient_client = role_clients[UserRole.PATIENT.value]
    institution_admin_client = role_clients[
        UserRole.INSTITUTION_ADMIN.value
    ]

    create_response = patient_client.post(
        "/api/patient-requests",
        json={
            "category": PatientRequestCategory.MEDICATION_QUERY.value,
            "subject_line": "Automated response authorization test",
            "message": "This request exists only inside the isolated test database.",
        },
    )
    assert create_response.status_code == 201
    request_id = create_response.json()["id"]

    response_payload = {
        "response": "The institution administrator reviewed this request.",
        "status": PatientRequestStatus.RESOLVED.value,
    }

    patient_response = patient_client.patch(
        f"/api/patient-requests/{request_id}/respond",
        json=response_payload,
    )
    assert patient_response.status_code == 403
    assert "patient_request:respond" in patient_response.json()["detail"]

    admin_response = institution_admin_client.patch(
        f"/api/patient-requests/{request_id}/respond",
        json=response_payload,
    )
    assert admin_response.status_code == 200
    body = admin_response.json()
    assert body["status"] == PatientRequestStatus.RESOLVED.value
    assert body["admin_response"] == response_payload["response"]
    assert body["assigned_admin_id"] is not None
    assert body["resolved_at"] is not None
def test_institution_admin_cannot_respond_to_other_site_request(
    role_clients,
    seeded_engine,
) -> None:
    institution_admin_client = role_clients[
        UserRole.INSTITUTION_ADMIN.value
    ]

    with Session(seeded_engine) as session:
        admin_user = session.exec(
            select(User)
            .where(User.role == UserRole.INSTITUTION_ADMIN.value)
            .order_by(User.id)
        ).first()
        assert admin_user is not None
        assert admin_user.site_id is not None

        other_site_request = session.exec(
            select(PatientRequest).where(
                PatientRequest.site_id != admin_user.site_id
            )
        ).first()
        assert other_site_request is not None
        other_request_id = other_site_request.id

    response = institution_admin_client.patch(
        f"/api/patient-requests/{other_request_id}/respond",
        json={
            "response": "This cross-site response must be denied.",
            "status": PatientRequestStatus.RESOLVED.value,
        },
    )

    assert response.status_code == 403