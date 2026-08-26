"""Tests for the read-only Phase 1 endpoints.

These run against a throwaway SQLite file seeded by the real seed script, so no
Postgres and no Docker are needed:

    pytest tests/test_api.py -q

The app normally hands every request a session pointing at DATABASE_URL. Here we
override that one dependency, which lets the actual routers, filters and
response models run untouched against a database we control. See conftest.py for
how that override is kept pointed at the right database.

Two fixtures on purpose, both from conftest.py:

  `client`       a fully seeded trial, signed in as an Administrator - the normal
                 case. Phase 2 locked every endpoint behind a token; the admin
                 holds every permission and sees every site, so the assertions
                 below still describe what an unrestricted caller gets.
  `empty_client` migrated but with no rows - what you see before running the
                 seed script. Endpoints must degrade politely, not throw a 500.

What each *role* sees, as opposed to what exists, is `test_rbac.py`'s job.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.models import AdverseEvent, AuditLog, Site, Subject, Trial, User, Visit
from app.routers.common import MAX_PAGE_SIZE


@pytest.fixture(scope="module")
def counts(seeded_engine) -> dict:
    """Row counts read straight from the tables.

    Every number an endpoint reports is checked against these, not against
    hardcoded literals. That way the tests keep working if the generator's
    volumes are tuned, but still catch an endpoint that miscounts.
    """
    with Session(seeded_engine) as session:

        def n(model, *where) -> int:
            statement = select(model.id)
            for clause in where:
                statement = statement.where(clause)
            return len(session.exec(statement).all())

        return {
            "trials": n(Trial),
            "sites": n(Site),
            "users": n(User),
            "subjects": n(Subject),
            "visits": n(Visit),
            "adverse_events": n(AdverseEvent),
            "audit_logs": n(AuditLog),
            "enrolled": n(Subject, Subject.enrollment_date.is_not(None)),
            "serious": n(AdverseEvent, AdverseEvent.is_serious == True),  # noqa: E712
            "deviations": n(Visit, Visit.is_protocol_deviation == True),  # noqa: E712
        }


LIST_ENDPOINTS = [
    "/api/trials",
    "/api/sites",
    "/api/subjects",
    "/api/visits",
    "/api/adverse-events",
    "/api/audit-log",
    "/api/users",
]


# --------------------------------------------------------------- the envelope


@pytest.mark.parametrize("path", LIST_ENDPOINTS)
def test_list_endpoints_return_the_page_envelope(client, path):
    body = client.get(path).json()
    assert set(body) == {"total", "limit", "offset", "items"}
    assert isinstance(body["items"], list)
    assert body["total"] >= len(body["items"])


@pytest.mark.parametrize("path", LIST_ENDPOINTS)
def test_total_counts_all_matches_not_just_this_page(client, path):
    """`total` must ignore limit - it is what draws "showing 50 of 186"."""
    small = client.get(path, params={"limit": 1}).json()
    large = client.get(path, params={"limit": MAX_PAGE_SIZE}).json()
    assert small["total"] == large["total"]
    assert len(small["items"]) <= 1


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},  # a page of nothing is a bug, not a request
        {"limit": MAX_PAGE_SIZE + 1},  # no dragging the whole table over the wire
        {"offset": -1},
    ],
)
def test_bad_paging_is_rejected(client, params):
    assert client.get("/api/subjects", params=params).status_code == 422


def test_paging_walks_every_row_exactly_once(client, counts):
    """Step through /api/subjects a page at a time and rebuild the whole table."""
    seen: list[int] = []
    offset, page_size = 0, 100
    while True:
        body = client.get(
            "/api/subjects", params={"limit": page_size, "offset": offset}
        ).json()
        if not body["items"]:
            break
        seen.extend(item["id"] for item in body["items"])
        offset += page_size

    assert len(seen) == counts["subjects"]
    assert len(set(seen)) == len(seen), "a row appeared on two different pages"


def test_offset_past_the_end_is_empty_not_an_error(client, counts):
    body = client.get("/api/subjects", params={"offset": counts["subjects"] + 10}).json()
    assert body["items"] == []
    assert body["total"] == counts["subjects"]


# ------------------------------------------------------------------- totals


def test_list_totals_match_the_tables(client, counts):
    for path, key in (
        ("/api/trials", "trials"),
        ("/api/sites", "sites"),
        ("/api/subjects", "subjects"),
        ("/api/visits", "visits"),
        ("/api/adverse-events", "adverse_events"),
        ("/api/audit-log", "audit_logs"),
        ("/api/users", "users"),
    ):
        assert client.get(path).json()["total"] == counts[key], path


# ------------------------------------------------------------------- filters


def test_subject_status_filter_narrows_and_matches(client):
    everything = client.get("/api/subjects", params={"limit": MAX_PAGE_SIZE}).json()
    statuses = {item["status"] for item in everything["items"]}
    assert len(statuses) > 1, "the seed should produce a mix of statuses"

    for status in statuses:
        body = client.get(
            "/api/subjects", params={"status": status, "limit": MAX_PAGE_SIZE}
        ).json()
        assert body["total"] > 0
        assert all(item["status"] == status for item in body["items"])
        assert body["total"] < everything["total"]


def test_subject_arm_and_prakriti_filters(client):
    for field, value in (("arm", "treatment"), ("prakriti", "vata")):
        body = client.get(
            "/api/subjects", params={field: value, "limit": MAX_PAGE_SIZE}
        ).json()
        assert body["total"] > 0, f"no subjects with {field}={value}"
        assert all(item[field] == value for item in body["items"])


def test_only_enrolled_participants_have_a_prakriti(client):
    """The constitutional assessment is a baseline procedure.

    Prakriti is a person's Ayurvedic constitutional type (vata / pitta / kapha) -
    roughly, a body-type classification that guides treatment. It is assessed
    once the participant is actually enrolled, so a screen failure has none, and
    the API must show that as absent rather than guessing a value.
    """
    failures = client.get(
        "/api/subjects", params={"status": "screen_failed", "limit": MAX_PAGE_SIZE}
    ).json()
    assert failures["total"] > 0
    assert all(item["prakriti"] is None for item in failures["items"])
    assert all(item["enrollment_date"] is None for item in failures["items"])


def test_unknown_filter_value_returns_an_empty_page(client):
    body = client.get("/api/subjects", params={"status": "not-a-real-status"}).json()
    assert body["total"] == 0
    assert body["items"] == []


def test_serious_only_filter(client, counts):
    body = client.get(
        "/api/adverse-events", params={"serious_only": "true", "limit": MAX_PAGE_SIZE}
    ).json()
    assert body["total"] == counts["serious"]
    assert all(item["is_serious"] for item in body["items"])
    # A serious event must say *why* it is serious - that is the regulatory
    # category (hospitalisation, life-threatening...) which starts the clock.
    assert all(item["seriousness_criteria"] for item in body["items"])


def test_serious_is_a_subset_of_all_events(client, counts):
    assert counts["serious"] < counts["adverse_events"]


def test_severity_filter(client):
    total = 0
    for severity in ("mild", "moderate", "severe"):
        body = client.get(
            "/api/adverse-events",
            params={"severity": severity, "limit": MAX_PAGE_SIZE},
        ).json()
        assert all(item["severity"] == severity for item in body["items"])
        total += body["total"]
    # Every event has one of the three severities, so the parts must sum.
    assert total == client.get("/api/adverse-events").json()["total"]


def test_causality_filter(client):
    body = client.get(
        "/api/adverse-events", params={"causality": "probable", "limit": MAX_PAGE_SIZE}
    ).json()
    assert body["total"] > 0
    assert all(item["causality"] == "probable" for item in body["items"])


def test_everything_is_still_awaiting_meddra_coding(client, counts):
    """Phase 4's work queue starts full: the seed deliberately codes nothing."""
    body = client.get(
        "/api/adverse-events", params={"uncoded_only": "true", "limit": MAX_PAGE_SIZE}
    ).json()
    assert body["total"] == counts["adverse_events"]
    assert all(item["meddra_pt_code"] is None for item in body["items"])


def test_deviations_only_filter(client, counts):
    body = client.get(
        "/api/visits", params={"deviations_only": "true", "limit": MAX_PAGE_SIZE}
    ).json()
    assert body["total"] == counts["deviations"]
    assert all(item["is_protocol_deviation"] for item in body["items"])


def test_visit_status_filter(client):
    body = client.get(
        "/api/visits", params={"status": "completed", "limit": MAX_PAGE_SIZE}
    ).json()
    assert body["total"] > 0
    assert all(item["status"] == "completed" for item in body["items"])


def test_site_filter_partitions_the_subjects(client, counts):
    """Every subject belongs to exactly one site, so the per-site counts sum."""
    sites = client.get("/api/sites").json()["items"]
    assert len(sites) > 1
    per_site = [
        client.get("/api/subjects", params={"site_id": site["id"]}).json()["total"]
        for site in sites
    ]
    assert sum(per_site) == counts["subjects"]
    assert all(count > 0 for count in per_site), "every site should have participants"


def test_audit_log_filters(client):
    body = client.get("/api/audit-log", params={"limit": MAX_PAGE_SIZE}).json()
    actions = {item["action"] for item in body["items"]}
    for action in actions:
        filtered = client.get("/api/audit-log", params={"action": action}).json()
        assert filtered["total"] > 0
        assert all(item["action"] == action for item in filtered["items"])

    subjects_only = client.get(
        "/api/audit-log", params={"entity_type": "subjects", "limit": MAX_PAGE_SIZE}
    ).json()
    assert subjects_only["total"] > 0
    assert all(item["entity_type"] == "subjects" for item in subjects_only["items"])


# ------------------------------------------------------------------ ordering


def test_audit_log_is_newest_first(client):
    """An audit view is always read from the top."""
    items = client.get("/api/audit-log", params={"limit": MAX_PAGE_SIZE}).json()["items"]
    stamps = [item["timestamp"] for item in items]
    assert stamps == sorted(stamps, reverse=True)


def test_adverse_events_are_newest_first(client):
    items = client.get(
        "/api/adverse-events", params={"limit": MAX_PAGE_SIZE}
    ).json()["items"]
    onsets = [item["onset_date"] for item in items]
    assert onsets == sorted(onsets, reverse=True)


# -------------------------------------------------------------- nested reads


def test_subject_visits_are_in_protocol_order_and_belong_to_the_subject(client):
    subject = client.get("/api/subjects", params={"limit": 1}).json()["items"][0]
    visits = client.get(f"/api/subjects/{subject['id']}/visits").json()
    assert visits, "every participant should have a visit schedule"
    assert all(visit["subject_id"] == subject["id"] for visit in visits)
    numbers = [visit["visit_number"] for visit in visits]
    assert numbers == sorted(numbers)


def test_every_subject_has_the_same_visit_schedule_length(client):
    """The protocol defines one fixed schedule, so the count cannot vary."""
    sample = client.get("/api/subjects", params={"limit": 8}).json()["items"]
    lengths = {
        len(client.get(f"/api/subjects/{s['id']}/visits").json()) for s in sample
    }
    assert len(lengths) == 1, f"visit schedules differ in length: {lengths}"


def test_subject_adverse_events_belong_to_the_subject(client):
    # Find someone who actually had an event.
    events = client.get("/api/adverse-events", params={"limit": 1}).json()["items"]
    subject_id = events[0]["subject_id"]
    mine = client.get(f"/api/subjects/{subject_id}/adverse-events").json()
    assert mine
    assert all(event["subject_id"] == subject_id for event in mine)
    onsets = [event["onset_date"] for event in mine]
    assert onsets == sorted(onsets), "a participant's events should read oldest first"


def test_site_subjects_match_the_site_filter(client):
    site = client.get("/api/sites").json()["items"][0]
    nested = client.get(f"/api/sites/{site['id']}/subjects").json()
    flat = client.get("/api/subjects", params={"site_id": site["id"]}).json()
    assert nested["total"] == flat["total"]
    assert all(item["site_id"] == site["id"] for item in nested["items"])


# ---------------------------------------------------------------------- 404s


@pytest.mark.parametrize(
    "path",
    [
        "/api/trials/9999",
        "/api/sites/9999",
        "/api/sites/9999/subjects",
        "/api/subjects/9999",
        "/api/subjects/9999/visits",
        "/api/subjects/9999/adverse-events",
        "/api/visits/999999",
        "/api/adverse-events/9999",
        "/api/users/9999",
    ],
)
def test_missing_ids_return_404_with_a_readable_message(client, path):
    response = client.get(path)
    assert response.status_code == 404, path
    assert "9999" in response.json()["detail"]


# ------------------------------------------------------------------ users


def test_users_never_expose_a_password(client):
    """`User` is both the table and the API shape, so this needs a real guard.

    Phase 2 fills `hashed_password` in. If someone widens the response model to
    the raw table, this test is what stops a credential hash from being served
    to the browser.
    """
    body = client.get("/api/users", params={"limit": MAX_PAGE_SIZE}).json()
    assert body["items"]
    for user in body["items"]:
        leaked = [key for key in user if "password" in key.lower()]
        assert not leaked, f"{user['email']} leaked {leaked}"

    one = client.get(f"/api/users/{body['items'][0]['id']}").json()
    assert not [key for key in one if "password" in key.lower()]
    # And the fields the UI does need are present.
    assert {"id", "email", "full_name", "role"} <= set(one)


def test_users_cover_the_five_personas(client):
    body = client.get("/api/users", params={"limit": MAX_PAGE_SIZE}).json()
    roles = {user["role"] for user in body["items"]}
    for role in ("principal_investigator", "sponsor", "ethics_committee", "regulator"):
        assert role in roles, f"no seeded user with role {role}"


def test_user_role_filter(client):
    body = client.get("/api/users", params={"role": "principal_investigator"}).json()
    assert body["total"] > 0
    assert all(user["role"] == "principal_investigator" for user in body["items"])


# ------------------------------------------------------------------- stats


def test_stats_reconcile_with_the_tables(client, counts):
    body = client.get("/api/stats").json()
    assert body["seeded"] is True
    assert body["enrollment"]["screened"] == counts["subjects"]
    assert body["enrollment"]["enrolled"] == counts["enrolled"]
    assert body["visits"]["total"] == counts["visits"]
    assert body["visits"]["protocol_deviations"] == counts["deviations"]
    assert body["safety"]["adverse_events"] == counts["adverse_events"]
    assert body["safety"]["serious"] == counts["serious"]
    assert body["audit"]["entries"] == counts["audit_logs"]
    assert body["sites"]["total"] == counts["sites"]


def test_stats_groupings_sum_to_their_totals(client, counts):
    body = client.get("/api/stats").json()
    assert sum(body["enrollment"]["by_status"].values()) == counts["subjects"]
    assert sum(body["by_arm"].values()) == counts["subjects"]
    # Prakriti (the Ayurvedic constitutional type) is assessed at enrolment, so
    # someone who failed screening never has one - this sums to enrolled, not
    # screened. The grouping drops nulls rather than inventing an "unknown" bar.
    assert sum(body["by_prakriti"].values()) == counts["enrolled"]
    assert sum(body["visits"]["by_status"].values()) == counts["visits"]
    assert sum(body["safety"]["by_severity"].values()) == counts["adverse_events"]
    assert sum(body["safety"]["by_causality"].values()) == counts["adverse_events"]
    assert sum(body["audit"]["by_action"].values()) == counts["audit_logs"]


def test_stats_per_site_numbers_sum_to_the_headline(client, counts):
    body = client.get("/api/stats").json()
    detail = body["sites"]["detail"]
    assert len(detail) == counts["sites"]
    assert sum(site["screened"] for site in detail) == counts["subjects"]
    assert sum(site["enrolled"] for site in detail) == counts["enrolled"]
    # A site cannot enrol someone it never screened.
    assert all(site["enrolled"] <= site["screened"] for site in detail)


def test_stats_percentages_are_consistent(client):
    body = client.get("/api/stats").json()
    enrollment = body["enrollment"]
    expected = round(enrollment["enrolled"] * 100 / enrollment["target"], 1)
    assert enrollment["percent_of_target"] == expected
    # Not everyone screened enrols, so this cannot be 100%.
    assert 0 < enrollment["screening_success_rate"] < 100


def test_deviation_rate_is_measured_against_visits_actually_due(client):
    """A visit still in the future cannot have deviated from anything."""
    visits = client.get("/api/stats").json()["visits"]
    assert visits["due_so_far"] < visits["total"]
    assert visits["deviation_rate"] == round(
        visits["protocol_deviations"] * 100 / visits["due_so_far"], 1
    )


def test_stats_trial_block_carries_the_regulatory_identifiers(client):
    trial = client.get("/api/stats").json()["trial"]
    # CTRI is India's trial registry; a trial must be registered there before it
    # enrols anyone, so the number belongs on every dashboard.
    assert trial["ctri_number"].startswith("CTRI/")
    assert trial["protocol_number"]
    assert trial["indication_ayurveda"], "the Ayurvedic diagnosis should be shown too"


def test_stats_carries_the_synthetic_data_notice(client):
    assert "synthetic" in client.get("/api/stats").json()["data_notice"].lower()


def test_stats_scoped_to_a_missing_trial_is_not_seeded(client):
    body = client.get("/api/stats", params={"trial_id": 9999}).json()
    assert body["seeded"] is False


def test_enrollment_timeline_builds_a_rising_curve(client, counts):
    body = client.get("/api/stats/enrollment-timeline").json()
    points = body["points"]
    assert points
    months = [point["month"] for point in points]
    assert months == sorted(months)

    running = 0
    for point in points:
        running += point["enrolled"]
        assert point["cumulative"] == running
        assert point["target"] == body["target"]
    # The curve has to end on the same number the headline reports.
    assert points[-1]["cumulative"] == counts["enrolled"]


# -------------------------------------------------- the un-seeded database


def test_stats_on_an_empty_database_explains_what_to_do(empty_client):
    """An empty database is a normal state, not a 500."""
    response = empty_client.get("/api/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["seeded"] is False
    assert "seed.py" in body["message"]


@pytest.mark.parametrize("path", LIST_ENDPOINTS)
def test_list_endpoints_on_an_empty_database_return_empty_pages(empty_client, path):
    body = empty_client.get(path).json()
    assert body == {"total": 0, "limit": 50, "offset": 0, "items": []}


def test_enrollment_timeline_on_an_empty_database_is_a_404(empty_client):
    response = empty_client.get("/api/stats/enrollment-timeline")
    assert response.status_code == 404
    assert "seed" in response.json()["detail"]
