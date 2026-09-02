"""Tests for Pharmacovigilance (NPvCC) SAE 24-Hour and 14-Day Regulatory Countdown Clocks under NDCT Rules 2019 (Rule 42)."""

from datetime import date, timedelta
from sqlmodel import Session, select

from app.enums import UserRole
from app.models import AdverseEvent, Trial
from tests.conftest import client_for


def test_sae_regulatory_clock_computation(seeded_engine):
    regulator_client = client_for(seeded_engine, UserRole.REGULATOR.value)

    # 1. Fetch adverse events via API
    res = regulator_client.get("/api/adverse-events?serious_only=true")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) > 0

    for item in data["items"]:
        assert item["is_serious"] is True
        assert item["expedited_deadline"] is not None
        assert item["detailed_report_deadline"] is not None
        assert item["regulatory_urgency"] in {
            "COMPLIANT_SUBMITTED",
            "EXPEDITED_OVERDUE",
            "EXPEDITED_DUE_SOON",
            "EXPEDITED_PENDING",
        }

        # Check deadline math: 1 day for expedited, 14 days for detailed analysis
        onset = date.fromisoformat(item["onset_date"])
        assert date.fromisoformat(item["expedited_deadline"]) == onset + timedelta(days=1)
        assert date.fromisoformat(item["detailed_report_deadline"]) == onset + timedelta(days=14)


def test_ethics_and_regulator_dashboard_sae_table_has_urgency(seeded_engine):
    ethics_client = client_for(seeded_engine, UserRole.ETHICS_COMMITTEE.value)
    res = ethics_client.get("/api/dashboard")
    assert res.status_code == 200
    blocks = res.json()["blocks"]
    sae_block = next((b for b in blocks if b["key"] == "sae_reporting"), None)
    assert sae_block is not None

    # Check that the 24h Regulatory Clock column is present in table definitions
    column_keys = [c["key"] for c in sae_block["columns"]]
    assert "urgency" in column_keys
    assert len(sae_block["rows"]) > 0
    for row in sae_block["rows"]:
        assert "urgency" in row
