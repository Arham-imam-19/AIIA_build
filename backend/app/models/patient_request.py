"""Patient requests and communications to Institution Admins."""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class PatientRequest(SQLModel, table=True):
    """A communication or request submitted by a trial participant/patient to the Institution Admin.

    Allows patients to report symptoms, request visit reschedules, ask medication/posology
    questions, or raise concerns directly with the hospital/institution administrative team.
    """

    __tablename__ = "patient_requests"

    id: int | None = Field(default=None, primary_key=True)
    site_id: int = Field(foreign_key="sites.id", index=True)
    trial_id: int | None = Field(default=None, foreign_key="trials.id", index=True)

    # The patient who submitted the request
    patient_user_id: int = Field(foreign_key="users.id", index=True)
    subject_id: int | None = Field(default=None, foreign_key="subjects.id", index=True)

    # Request classification and details
    category: str = Field(max_length=40, index=True)  # enums.PatientRequestCategory
    subject_line: str = Field(max_length=200)
    message: str = Field(max_length=3000)

    # Status & Administrative response
    status: str = Field(default="submitted", max_length=30, index=True)  # enums.PatientRequestStatus
    assigned_admin_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    admin_response: str | None = Field(default=None, max_length=3000)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = Field(default=None)
