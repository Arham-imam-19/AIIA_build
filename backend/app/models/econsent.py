"""Electronic informed-consent records for the demonstration application."""

from datetime import datetime

from sqlalchemy import Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class EConsent(SQLModel, table=True):
    """A participant's electronic informed-consent demonstration record."""

    __tablename__ = "econsents"
    __table_args__ = (
        UniqueConstraint("subject_id", name="uq_econsents_subject_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    trial_id: int = Field(foreign_key="trials.id", index=True)
    site_id: int = Field(foreign_key="sites.id", index=True)
    subject_id: int = Field(foreign_key="subjects.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    # Consent form metadata
    language: str = Field(default="en", max_length=10)  # "en" or "hi"
    abha_id: str | None = Field(default=None, max_length=50)  # e.g., "14-9988-7766-5544"
    signer_name: str = Field(max_length=200)

    # Cryptographic & Visual Signature
    signature_data_url: str = Field(
        sa_column=Column(Text, nullable=False, doc="Base64 encoded PNG signature drawing")
    )
    sha256_hash: str = Field(max_length=64, index=True, description="SHA-256 digest of signed payload")

    # Audit & Status
    status: str = Field(default="signed", max_length=30, index=True)  # enums.ConsentStatus
    signed_at: datetime = Field(default_factory=utcnow)
    ip_address: str | None = Field(default=None, max_length=100)
    user_agent: str | None = Field(default=None, max_length=300)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
