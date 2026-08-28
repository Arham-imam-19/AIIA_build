"""Electronic Informed Consent (e-Consent) records under NDCT Rules 2019 and 21 CFR Part 11."""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class EConsent(SQLModel, table=True):
    """A participant's digitally signed electronic informed consent record.

    Meets regulatory requirements under India's New Drugs and Clinical Trials Rules 2019
    and 21 CFR Part 11:
      * Explicit identity attribution (User & Subject)
      * Timestamped digital signature drawing (data URL)
      * Cryptographic SHA-256 integrity hash
      * Language selection record (English or Hindi)
      * Optional ABHA ID (Ayushman Bharat Health Account) linkage
    """

    __tablename__ = "econsents"

    id: int | None = Field(default=None, primary_key=True)
    trial_id: int = Field(foreign_key="trials.id", index=True)
    site_id: int = Field(foreign_key="sites.id", index=True)
    subject_id: int = Field(foreign_key="subjects.id", unique=True, index=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    # Consent form metadata
    language: str = Field(default="en", max_length=10)  # "en" or "hi"
    abha_id: str | None = Field(default=None, max_length=50)  # e.g., "14-9988-7766-5544"
    signer_name: str = Field(max_length=200)

    # Cryptographic & Visual Signature
    signature_data_url: str = Field(description="Base64 encoded PNG signature drawing")
    sha256_hash: str = Field(max_length=64, index=True, description="SHA-256 digest of signed payload")

    # Audit & Status
    status: str = Field(default="signed", max_length=30, index=True)  # enums.ConsentStatus
    signed_at: datetime = Field(default_factory=utcnow)
    ip_address: str | None = Field(default=None, max_length=100)
    user_agent: str | None = Field(default=None, max_length=300)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
