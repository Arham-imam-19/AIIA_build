"""User accounts and their roles."""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import utcnow


class User(SQLModel, table=True):
    """A person who logs into the system.

    Passwords: `hashed_password` is nullable and left empty by the Phase 1 seed.
    Authentication arrives in Phase 2, which is where hashing and login
    credentials are added. A user row existing does not yet mean it can log in.
    """

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)

    email: str = Field(max_length=255, unique=True, index=True)
    full_name: str = Field(max_length=200)

    # One of enums.UserRole. Stored as a plain string - see enums.py for why.
    role: str = Field(max_length=40, index=True)

    # Set in Phase 2 when authentication lands.
    hashed_password: str | None = Field(default=None, max_length=255)

    # Site staff (investigators, coordinators) belong to one site. Sponsors,
    # regulators and ethics-committee members oversee all sites, so this is null
    # for them.
    site_id: int | None = Field(default=None, foreign_key="sites.id", index=True)

    organization: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)

    is_active: bool = Field(default=True)

    created_at: datetime = Field(default_factory=utcnow)
    last_login_at: datetime | None = Field(default=None)
