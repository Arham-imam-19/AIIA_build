"""Phase 2: the five role dashboards.

`GET /api/dashboard` has no `?role=` parameter on purpose - the role comes from
the signed token, so a regulator cannot ask for the sponsor's screen by editing a
URL. These tests check three things:

* every role gets its *own* screen, not a filtered copy of one screen;
* the numbers on it reconcile with the tables underneath;
* a site-scoped role's tiles count only their own hospital.

The payload shape is asserted once, generically, because the frontend renders it
generically: it walks `tiles` and `blocks` and dispatches on `kind`. A block with
an unknown kind, or a table whose rows are missing a declared column, would draw
a blank panel in the browser rather than raise anything - so it has to be caught
here.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.enums import UserRole
from app.models import AdverseEvent, Subject, User, Visit
from tests.conftest import client_for_user, users_by_role

ROLES = [
    UserRole.PRINCIPAL_INVESTIGATOR.value,
    UserRole.COORDINATOR.value,
    UserRole.SPONSOR.value,
    UserRole.ETHICS_COMMITTEE.value,
    UserRole.REGULATOR.value,
]

# What each role's screen is *for*. If a tile is renamed, this is where the demo
# script breaks, so it is worth pinning.
EXPECTED_TILES = {
    UserRole.PRINCIPAL_INVESTIGATOR.value: {
        "screened", "enrolled", "active", "open_aes", "serious", "deviations",
        "due_soon", "uncoded",
    },
    UserRole.COORDINATOR.value: {
        "due_soon", "overdue", "completed", "missed", "in_screening", "uncoded",
        "deviations", "enrolled",
    },
    UserRole.SPONSOR.value: {
        "enrolled", "percent", "screening_rate", "sites", "aes", "serious",
        "deviation_rate", "days_left",
    },
    UserRole.ETHICS_COMMITTEE.value: {
        "serious", "reported_late", "unreported", "compliance", "severe", "all_aes",
        "deviations", "approval",
    },
    UserRole.REGULATOR.value: {
        "ctri", "ethics", "status", "audit", "sae_compliance", "deviation_rate",
        "sites", "enrolled",
    },
}

EXPECTED_BLOCKS = {
    UserRole.PRINCIPAL_INVESTIGATOR.value: {"by_status", "recent_aes", "recruitment"},
    UserRole.COORDINATOR.value: {"upcoming", "screening", "visit_status"},
    UserRole.SPONSOR.value: {"site_performance", "recruitment", "by_arm"},
    UserRole.ETHICS_COMMITTEE.value: {
        "sae_reporting", "ethics_snapshot", "by_causality", "deviations",
    },
    UserRole.REGULATOR.value: {"ndct_gates", "audit_tail", "sites", "sae_reporting"},
}

# The four block shapes the frontend knows how to draw, and the keys each needs.
BLOCK_KINDS = {
    "table": {"columns", "rows"},
    "breakdown": {"items", "total"},
    "series": {"points", "x", "lines"},
    "checklist": {"items", "passed", "total"},
}


@pytest.fixture(scope="module")
def dashboards(role_clients) -> dict[str, dict]:
    """Each role's dashboard, fetched once."""
    return {
        role: role_clients[role].get("/api/dashboard").json() for role in ROLES
    }


@pytest.fixture(scope="module")
def totals(seeded_engine) -> dict:
    """Whole-study counts, read straight from the tables."""
    with Session(seeded_engine) as session:

        def n(model, *where):
            statement = select(model.id)
            for clause in where:
                statement = statement.where(clause)
            return len(session.exec(statement).all())

        return {
            "subjects": n(Subject),
            "enrolled": n(Subject, Subject.enrollment_date.is_not(None)),
            "adverse_events": n(AdverseEvent),
            "serious": n(AdverseEvent, AdverseEvent.is_serious == True),  # noqa: E712
            "deviations": n(Visit, Visit.is_protocol_deviation == True),  # noqa: E712
        }


# ------------------------------------------------------------------ the shape


@pytest.mark.parametrize("role", ROLES)
def test_every_dashboard_has_the_frame_the_ui_expects(dashboards, role):
    body = dashboards[role]
    assert body["role"] == role
    assert body["seeded"] is True
    for key in (
        "role_label", "title", "subtitle", "user", "generated_at", "live",
        "data_notice", "scope", "trial", "tiles", "blocks",
    ):
        assert key in body, f"{role} is missing {key}"
    assert "synthetic" in body["data_notice"].lower()
    assert body["live"]["backend"] in {"redis", "in-process"}


@pytest.mark.parametrize("role", ROLES)
def test_every_tile_is_renderable(dashboards, role):
    tiles = dashboards[role]["tiles"]
    assert len(tiles) == 8, f"{role} has {len(tiles)} tiles; the grid expects 8"
    for tile in tiles:
        assert set(tile) == {"key", "label", "value", "hint", "tone"}, tile
        assert tile["label"], tile
        assert tile["value"] is not None, tile
        # The tone drives the colour. An unknown one would render untinted.
        assert tile["tone"] in {"good", "warn", "bad", "neutral"}, tile


@pytest.mark.parametrize("role", ROLES)
def test_every_block_is_renderable(dashboards, role):
    blocks = dashboards[role]["blocks"]
    assert blocks
    for block in blocks:
        assert block["kind"] in BLOCK_KINDS, f"{role}: no renderer for {block['kind']}"
        assert BLOCK_KINDS[block["kind"]] <= set(block), block["key"]
        assert block["title"], block["key"]


@pytest.mark.parametrize("role", ROLES)
def test_table_rows_carry_every_declared_column(dashboards, role):
    """The renderer walks `columns`, so a missing key would draw a blank cell.

    Rows may carry *extra* keys - a row often holds an id the table does not
    show - but never fewer than the columns it declares.
    """
    for block in dashboards[role]["blocks"]:
        if block["kind"] != "table":
            continue
        declared = {column["key"] for column in block["columns"]}
        assert declared, block["key"]
        for row in block["rows"]:
            missing = declared - set(row)
            assert not missing, f"{role}/{block['key']} row is missing {missing}"


@pytest.mark.parametrize("role", ROLES)
def test_an_empty_table_says_so_instead_of_showing_nothing(dashboards, role):
    """A panel with no rows and no explanation reads as a broken screen."""
    for block in dashboards[role]["blocks"]:
        if block["kind"] == "table" and not block["rows"]:
            assert block.get("empty"), f"{role}/{block['key']} is empty and silent"


@pytest.mark.parametrize("role", ROLES)
def test_breakdown_percentages_are_shares_of_the_stated_total(dashboards, role):
    for block in dashboards[role]["blocks"]:
        if block["kind"] != "breakdown":
            continue
        assert sum(item["value"] for item in block["items"]) == block["total"]
        assert all(0 <= item["percent"] <= 100 for item in block["items"])


@pytest.mark.parametrize("role", ROLES)
def test_checklist_counts_match_its_items(dashboards, role):
    for block in dashboards[role]["blocks"]:
        if block["kind"] != "checklist":
            continue
        assert block["total"] == len(block["items"])
        assert block["passed"] == sum(1 for item in block["items"] if item["ok"])
        for item in block["items"]:
            # A failed check with no detail cannot be acted on.
            assert item["detail"], item["label"]


# --------------------------------------------------- one screen per persona


def test_the_five_roles_get_five_different_screens(dashboards):
    """Not one screen with rows hidden - five screens."""
    titles = {role: body["title"] for role, body in dashboards.items()}
    assert len(set(titles.values())) == len(ROLES), titles
    tile_sets = {role: tuple(t["key"] for t in body["tiles"])
                 for role, body in dashboards.items()}
    assert len(set(tile_sets.values())) == len(ROLES), "two roles share a tile set"


@pytest.mark.parametrize("role", ROLES)
def test_each_role_gets_the_tiles_its_job_needs(dashboards, role):
    assert {t["key"] for t in dashboards[role]["tiles"]} == EXPECTED_TILES[role]


@pytest.mark.parametrize("role", ROLES)
def test_each_role_gets_the_panels_its_job_needs(dashboards, role):
    assert {b["key"] for b in dashboards[role]["blocks"]} == EXPECTED_BLOCKS[role]


def test_the_role_comes_from_the_token_not_a_query_parameter(role_clients):
    """Editing the URL must not change whose screen you get."""
    sponsor = role_clients[UserRole.SPONSOR.value]
    plain = sponsor.get("/api/dashboard").json()
    tampered = sponsor.get("/api/dashboard", params={"role": "regulator"}).json()
    assert tampered["role"] == "sponsor"
    assert [t["key"] for t in tampered["tiles"]] == [t["key"] for t in plain["tiles"]]


def test_an_admin_gets_the_regulators_all_seeing_view(role_clients):
    """Rather than a sixth screen nobody demos."""
    admin = role_clients[UserRole.ADMIN.value].get("/api/dashboard").json()
    regulator = role_clients[UserRole.REGULATOR.value].get("/api/dashboard").json()
    assert admin["role"] == "admin"
    assert [t["key"] for t in admin["tiles"]] == [t["key"] for t in regulator["tiles"]]


# ------------------------------------------------------ the numbers reconcile


def test_the_sponsor_sees_the_whole_study(dashboards, totals):
    tiles = {t["key"]: t["value"] for t in dashboards[UserRole.SPONSOR.value]["tiles"]}
    assert tiles["enrolled"] == totals["enrolled"]
    assert tiles["aes"] == totals["adverse_events"]
    assert tiles["serious"] == totals["serious"]


def test_the_ethics_committee_sees_every_sites_safety(dashboards, totals):
    tiles = {t["key"]: t["value"]
             for t in dashboards[UserRole.ETHICS_COMMITTEE.value]["tiles"]}
    assert tiles["all_aes"] == totals["adverse_events"]
    assert tiles["serious"] == totals["serious"]
    assert tiles["deviations"] == totals["deviations"]


def test_the_regulator_reports_the_registration_and_the_audit_trail(dashboards):
    body = dashboards[UserRole.REGULATOR.value]
    tiles = {t["key"]: t["value"] for t in body["tiles"]}
    # CTRI is India's trial registry; registration must precede first enrolment.
    assert str(tiles["ctri"]).startswith("CTRI/")
    assert isinstance(tiles["audit"], int) and tiles["audit"] > 0
    gates = next(b for b in body["blocks"] if b["key"] == "ndct_gates")
    assert gates["total"] >= 4, "NDCT 2019 has more than a couple of gates"


def test_a_site_scoped_dashboard_counts_only_that_site(seeded_engine, totals):
    """The investigator's own numbers, not the study's, and not another site's."""
    investigators = users_by_role(seeded_engine, UserRole.PRINCIPAL_INVESTIGATOR.value)
    assert len(investigators) >= 2

    seen = []
    for person in investigators:
        body = client_for_user(seeded_engine, person).get("/api/dashboard").json()
        assert body["scope"]["all_sites"] is False
        assert body["scope"]["site_id"] == person.site_id
        assert body["scope"]["sites_visible"] == 1

        tiles = {t["key"]: t["value"] for t in body["tiles"]}
        with Session(seeded_engine) as session:
            mine = len(session.exec(
                select(Subject.id).where(Subject.site_id == person.site_id)
            ).all())
        assert tiles["screened"] == mine
        assert tiles["screened"] < totals["subjects"], "a site is not the whole study"
        seen.append(tiles["enrolled"])

    assert sum(seen) <= totals["enrolled"]


def test_the_two_dashboards_of_the_same_role_show_different_numbers(seeded_engine):
    """Same job, different hospital, different screen - which is the point."""
    investigators = users_by_role(seeded_engine, UserRole.PRINCIPAL_INVESTIGATOR.value)
    payloads = [
        client_for_user(seeded_engine, person).get("/api/dashboard").json()
        for person in investigators[:2]
    ]
    first, second = ({t["key"]: t["value"] for t in body["tiles"]} for body in payloads)
    assert first != second
    assert payloads[0]["scope"]["site_id"] != payloads[1]["scope"]["site_id"]


def test_a_site_scoped_recruitment_curve_uses_the_site_target(seeded_engine, role_clients):
    """Comparing one hospital against the whole study's target would look absurd."""
    person = users_by_role(seeded_engine, UserRole.PRINCIPAL_INVESTIGATOR.value)[0]
    body = client_for_user(seeded_engine, person).get("/api/dashboard").json()
    curve = next(b for b in body["blocks"] if b["key"] == "recruitment")
    assert curve["points"]
    months = [point["month"] for point in curve["points"]]
    assert months == sorted(months)
    running = 0
    for point in curve["points"]:
        running += point["enrolled"]
        assert point["cumulative"] == running

    # The sponsor's identical panel is drawn against the whole study's target, so
    # the site's line must sit below it.
    study = next(
        b
        for b in role_clients[UserRole.SPONSOR.value].get("/api/dashboard").json()["blocks"]
        if b["key"] == "recruitment"
    )
    assert curve["points"][-1]["target"] < study["points"][-1]["target"]


# ------------------------------------------------------- the un-seeded database


def test_a_dashboard_with_no_data_explains_what_to_run(empty_client):
    """An empty database is a normal state, not a 500 and not a blank screen."""
    response = empty_client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["seeded"] is False
    assert body["tiles"] == []
    assert body["blocks"] == []
    assert "seed.py" in body["message"]
