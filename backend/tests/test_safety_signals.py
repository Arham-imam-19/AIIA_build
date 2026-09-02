"""Focused pure and API tests for demo PRR safety-signal detection."""

from app.enums import UserRole
from app.services.safety_signals import SignalEvent, SignalSite, calculate_safety_signals
from tests.conftest import client_for_user, users_by_role


def test_pure_service_calculates_exact_two_by_two_counts_and_prr():
    result = calculate_safety_signals(
        7,
        [SignalSite(id=1, code="01", name="Target")],
        [
            *[SignalEvent(1, "Headache") for _ in range(4)],
            *[SignalEvent(1, "Other") for _ in range(6)],
            SignalEvent(2, "Headache"),
            *[SignalEvent(2, "Other") for _ in range(9)],
        ],
    )

    item = next(item for item in result["items"] if item["term"] == "Headache")
    assert (item["a"], item["b"], item["c"], item["d"]) == (4, 6, 1, 9)
    assert item["prr"] == 4.0
    assert item["chi_square"] == 2.4
    assert item["calculation_status"] == "estimable"
    assert item["signal"] is False


def test_pure_service_handles_empty_data():
    result = calculate_safety_signals(
        9, [SignalSite(id=1, code="01", name="Empty")], []
    )

    assert result["trial_id"] == 9
    assert result["calculation_status"] == "no_data"
    assert result["calculation_reason"] == "trial has no adverse events"
    assert result["items"] == []
    assert result["thresholds"] == {
        "minimum_count": 3,
        "minimum_prr": 2.0,
        "minimum_chi_square": 4.0,
    }
    assert "not validated pharmacovigilance" in result["disclaimer"]


def test_pure_service_reports_zero_denominators_without_non_finite_values():
    no_comparator = calculate_safety_signals(
        1,
        [SignalSite(id=1, code="01", name="Only site")],
        [SignalEvent(1, "Headache") for _ in range(3)],
    )["items"][0]
    assert no_comparator["prr"] is None
    assert no_comparator["chi_square"] is None
    assert no_comparator["calculation_status"] == "not_estimable"
    assert "no adverse events are available at other trial sites" in no_comparator[
        "calculation_reason"
    ]

    zero_comparator_term = calculate_safety_signals(
        1,
        [SignalSite(id=1, code="01", name="Target")],
        [
            *[SignalEvent(1, "Headache") for _ in range(3)],
            SignalEvent(1, "Other"),
            *[SignalEvent(2, "Other") for _ in range(4)],
        ],
    )["items"]
    headache = next(item for item in zero_comparator_term if item["term"] == "Headache")
    assert headache["prr"] is None
    assert headache["chi_square"] == 4.8
    assert headache["signal"] is False
    assert "target term has no adverse events at other trial sites" in headache[
        "calculation_reason"
    ]


def test_api_returns_deterministic_verbatim_term_inventory(client):
    response = client.get("/api/trials/1/safety-signals")
    assert response.status_code == 200
    payload = response.json()

    assert payload["trial_id"] == 1
    assert payload["items"]
    ordering = [
        (item["site_code"], item["site_id"], item["term"])
        for item in payload["items"]
    ]
    assert ordering == sorted(ordering)
    assert all("meddra" not in key for item in payload["items"] for key in item)


def test_seeded_jaipur_loose_stools_is_a_signal(client):
    payload = client.get("/api/trials/1/safety-signals").json()
    item = next(
        item
        for item in payload["items"]
        if item["site_code"] == "02" and item["term"] == "Loose stools"
    )

    assert "Jaipur" in item["site_name"]
    assert item["a"] >= payload["thresholds"]["minimum_count"]
    assert item["prr"] >= payload["thresholds"]["minimum_prr"]
    assert item["chi_square"] >= payload["thresholds"]["minimum_chi_square"]
    assert item["signal"] is True


def test_authorization_allows_safety_read_roles_and_denies_patient(role_clients):
    allowed_roles = (
        UserRole.INSTITUTION_ADMIN,
        UserRole.PRINCIPAL_INVESTIGATOR,
        UserRole.COORDINATOR,
        UserRole.SPONSOR,
        UserRole.ETHICS_COMMITTEE,
        UserRole.REGULATOR,
    )
    for role in allowed_roles:
        assert role_clients[role.value].get(
            "/api/trials/1/safety-signals"
        ).status_code == 200

    assert role_clients[UserRole.PATIENT.value].get(
        "/api/trials/1/safety-signals"
    ).status_code == 403


def test_anonymous_access_is_denied(anonymous_client):
    assert anonymous_client.get("/api/trials/1/safety-signals").status_code == 401


def test_site_scoped_roles_receive_only_their_site(seeded_engine):
    for role in (
        UserRole.INSTITUTION_ADMIN,
        UserRole.PRINCIPAL_INVESTIGATOR,
        UserRole.COORDINATOR,
    ):
        user = users_by_role(seeded_engine, role.value)[1]
        response = client_for_user(seeded_engine, user).get(
            "/api/trials/1/safety-signals"
        )
        assert response.status_code == 200
        assert response.json()["items"]
        assert {item["site_id"] for item in response.json()["items"]} == {user.site_id}


def test_trial_wide_roles_receive_all_trial_sites(role_clients):
    for role in (
        UserRole.SPONSOR,
        UserRole.ETHICS_COMMITTEE,
        UserRole.REGULATOR,
    ):
        response = role_clients[role.value].get("/api/trials/1/safety-signals")
        assert response.status_code == 200
        assert {item["site_code"] for item in response.json()["items"]} == {
            "01",
            "02",
            "03",
            "04",
        }


def test_missing_trial_returns_404(client):
    response = client.get("/api/trials/999999/safety-signals")
    assert response.status_code == 404
    assert response.json()["detail"] == "trial 999999 not found"
