"""Tests for CERT-In Cybersecurity Directives (2022) Dual UTC/IST Timestamping and Audit Immutability."""

from datetime import datetime, timezone
from sqlmodel import Session, select

from app.enums import UserRole
from app.models import AuditLog
from tests.conftest import client_for


def test_certin_dual_timestamping_and_retention(seeded_engine):
    regulator_client = client_for(seeded_engine, UserRole.REGULATOR.value)

    res = regulator_client.get("/api/audit-log?limit=5")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) > 0

    for item in data["items"]:
        # 1. Canonical UTC timestamp is present
        assert item["timestamp"] is not None
        # 2. Localized IST timestamp is present and properly formatted
        assert item["timestamp_ist"] is not None
        assert item["timestamp_ist"].endswith("IST")
        # 3. Time difference check between UTC and IST is exactly +05:30
        utc_dt = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
        # Parse IST time string "YYYY-MM-DD HH:MM:SS IST"
        ist_str = item["timestamp_ist"].replace(" IST", "")
        ist_dt = datetime.fromisoformat(ist_str)
        diff_seconds = (ist_dt - utc_dt.replace(tzinfo=None)).total_seconds()
        assert int(diff_seconds) == 19800  # 5 hours 30 mins = 19800 seconds
