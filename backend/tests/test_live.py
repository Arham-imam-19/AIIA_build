"""Phase 2: the live dashboard, end to end.

The claim this file has to prove is the one the demo makes out loud: *nobody
refreshes anything*. A coordinator enrols a participant in one tab and the
sponsor's total moves in another, on its own, because a real row was written and
an event was broadcast.

Three pieces have to line up for that, so all three are exercised together:

1. `POST /api/simulate/...` writes a real row and an audit entry, then publishes.
2. The **event bus** fans that event out to every open connection. Redis is not
   installed here, so this runs on the in-process fallback - which is the same
   code path a single backend container uses in the demo.
3. The **WebSocket** recomputes *that viewer's* dashboard and pushes it, applying
   the same permission and site rules the HTTP API applies.

Two things about the test client that are easy to get wrong and cost hours:

**The client must be entered as a context manager.** `with client:` keeps one
event loop for the whole module, so the loop that runs the POST is the loop the
socket is waiting on. Without it each request gets a throwaway loop, the bus's
`put_nowait` wakes a future belonging to a loop nobody is running, and the push
simply never arrives.

**Every socket must be closed.** A socket left open keeps its app task alive, and
the client's own shutdown waits for that task - so the suite hangs instead of
failing. Hence `open_dashboard()`: it is a context manager, and it is the only
way this file opens a socket.

Assertions here are *deltas*, never absolute counts: these tests write rows into
the module's database copy, so "enrolled == 186" would only be true for whichever
test ran first.
"""

from __future__ import annotations

import contextlib

import pytest
from sqlmodel import Session, select
from starlette.websockets import WebSocketDisconnect

from app.enums import UserRole
from app.main import app
from app.models import AuditLog, Subject, User
from tests.conftest import client_for, token_for, token_for_user, users_by_role

# 1008 is "policy violation". A WebSocket handshake has already succeeded by the
# time we know who is asking, so there is no 401 to send - this is the standard
# way to say "you are not allowed in" on a socket.
CLOSE_NOT_ALLOWED = 1008


# --------------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def live(seeded_engine):
    """One client for the whole module, sockets and writes sharing an event loop.

    Signed in as an Administrator, who holds every permission and is not tied to a
    site - so the simulate calls can name *which* site to write to, which is what
    lets these tests prove that another site's investigator is left alone.
    """
    client = client_for(seeded_engine, UserRole.ADMIN.value)
    with client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def tokens(seeded_engine) -> dict[str, str]:
    """One access token per role, for opening sockets as each persona."""
    return {
        role.value: token_for(seeded_engine, role.value)
        for role in (
            UserRole.PRINCIPAL_INVESTIGATOR,
            UserRole.COORDINATOR,
            UserRole.SPONSOR,
            UserRole.ETHICS_COMMITTEE,
            UserRole.REGULATOR,
            UserRole.ADMIN,
        )
    }


@pytest.fixture(scope="module")
def investigators(seeded_engine) -> list[User]:
    """One Principal Investigator per hospital, so two scopes are available."""
    people = users_by_role(seeded_engine, UserRole.PRINCIPAL_INVESTIGATOR.value)
    assert len(people) >= 2, "the seed should staff more than one site"
    return people


@pytest.fixture(scope="module")
def administrator(seeded_engine) -> User:
    return users_by_role(seeded_engine, UserRole.ADMIN.value)[0]


# ---------------------------------------------------------------------- helpers


@contextlib.contextmanager
def open_dashboard(client, token: str):
    """Open the live socket, consume `hello`, and always close it on the way out.

    The caller reads the first snapshot itself - it is the "before" picture for
    almost every test here.
    """
    with client.websocket_connect(f"/ws/dashboard?token={token}") as socket:
        hello = socket.receive_json()
        assert hello["type"] == "hello", hello
        yield socket


def tiles(message: dict) -> dict:
    """The tiles of a snapshot message, as {key: value}."""
    return {tile["key"]: tile["value"] for tile in message["dashboard"]["tiles"]}


def refresh(socket) -> dict:
    """Ask for a fresh snapshot. Any inbound message means "resend"."""
    socket.send_text("refresh")
    return socket.receive_json()


def enrol(client, site_id: int) -> dict:
    response = client.post("/api/simulate/enrollment", json={"site_id": site_id})
    assert response.status_code == 201, response.text
    return response.json()


def report_ae(client, site_id: int, *, serious: bool = False) -> dict:
    response = client.post(
        "/api/simulate/adverse-event", json={"site_id": site_id, "serious": serious}
    )
    assert response.status_code == 201, response.text
    return response.json()


def log_deviation(client, site_id: int) -> dict:
    response = client.post("/api/simulate/deviation", json={"site_id": site_id})
    assert response.status_code == 201, response.text
    return response.json()


# ------------------------------------------------------------ getting connected


def test_a_socket_without_a_token_is_told_how_to_get_one(live):
    """Closed with a readable reason, not dropped at the handshake.

    A handshake failure gives the browser nothing but "connection failed", so the
    socket is accepted first and the explanation is sent before closing.
    """
    with live.websocket_connect("/ws/dashboard") as socket:
        error = socket.receive_json()
        assert error["type"] == "error"
        assert "no token" in error["detail"]
        assert "?token=" in error["detail"], "say how to fix it"
        with pytest.raises(WebSocketDisconnect) as refusal:
            socket.receive_json()
    assert refusal.value.code == CLOSE_NOT_ALLOWED


def test_a_bad_token_on_the_socket_is_refused_the_same_way_as_on_http(live):
    with live.websocket_connect("/ws/dashboard?token=not-a-token") as socket:
        error = socket.receive_json()
        assert error["type"] == "error"
        assert "invalid token" in error["detail"]
        with pytest.raises(WebSocketDisconnect) as refusal:
            socket.receive_json()
    assert refusal.value.code == CLOSE_NOT_ALLOWED


def test_a_role_with_no_dashboard_access_is_closed_out(live, seeded_engine):
    """`User.role` is a plain string, so an unrecognised one is insertable.

    It must fail closed: an unknown role holds no permissions at all, so it gets
    no dashboard rather than an empty one or a traceback.
    """
    with Session(seeded_engine) as session:
        template = session.exec(select(User).order_by(User.id)).first()
        stranger = User(
            email="data.auditor@example.test",
            full_name="Unknown Job Title",
            role="data_auditor",
            site_id=None,
            hashed_password=template.hashed_password,
        )
        session.add(stranger)
        session.commit()
        session.refresh(stranger)
        stranger_id = stranger.id
        token = token_for_user(stranger)

    try:
        with live.websocket_connect(f"/ws/dashboard?token={token}") as socket:
            error = socket.receive_json()
            assert error["detail"] == "Data Auditor has no dashboard access"
            with pytest.raises(WebSocketDisconnect) as refusal:
                socket.receive_json()
        assert refusal.value.code == CLOSE_NOT_ALLOWED
    finally:
        with Session(seeded_engine) as session:
            session.delete(session.get(User, stranger_id))
            session.commit()


def test_the_handshake_says_who_you_are_and_how_the_bus_is_running(live, tokens):
    """`hello` first, then the dashboard. The UI shows both to the demo audience."""
    token = tokens[UserRole.SPONSOR.value]
    with live.websocket_connect(f"/ws/dashboard?token={token}") as socket:
        hello = socket.receive_json()
        assert hello["type"] == "hello"
        assert hello["user"]["role"] == UserRole.SPONSOR.value
        assert hello["user"]["role_label"] == "Sponsor"
        assert hello["user"]["email"]
        # Which fan-out is live. Redis crosses containers; in-process does not, and
        # a demo should never be left guessing which one it got.
        assert hello["backend"] in {"redis", "in-process"}
        assert hello["detail"]
        assert isinstance(hello["heartbeat_seconds"], int)
        assert hello["heartbeat_seconds"] > 0

        first = socket.receive_json()
        assert first["type"] == "snapshot"
        assert first["reason"] == "connected"
        assert first["event"] is None, "nothing happened; this is just the state"
        assert first["dashboard"]["role"] == UserRole.SPONSOR.value


def test_the_socket_and_the_endpoint_serve_the_same_numbers(live, tokens):
    """They call the same function, and this is what proves it.

    If the live figure and the figure you get by reloading the page could
    disagree, every number on the screen would be suspect.
    """
    token = tokens[UserRole.REGULATOR.value]
    with open_dashboard(live, token) as socket:
        pushed = socket.receive_json()
    fetched = live.get(
        "/api/dashboard", headers={"Authorization": f"Bearer {token}"}
    ).json()

    assert tiles(pushed) == {t["key"]: t["value"] for t in fetched["tiles"]}
    assert [b["key"] for b in pushed["dashboard"]["blocks"]] == [
        b["key"] for b in fetched["blocks"]
    ]


def test_asking_again_resends_the_whole_dashboard(live, tokens):
    """The refresh button, and the reason there are no deltas on the wire.

    A delta has to be applied to whatever the browser already had; miss one
    message and the numbers drift with nobody noticing. Resending a few kilobytes
    cannot be wrong.
    """
    with open_dashboard(live, tokens[UserRole.COORDINATOR.value]) as socket:
        connected = socket.receive_json()
        again = refresh(socket)

    assert again["reason"] == "refresh"
    assert again["event"] is None
    assert tiles(again) == tiles(connected), "nothing changed in between"


# ------------------------------------------------- something happens, live


def test_an_enrolment_moves_the_investigators_numbers_with_no_refresh(
    live, investigators
):
    """The headline of the demo."""
    person = investigators[0]
    with open_dashboard(live, token_for_user(person)) as socket:
        before = tiles(socket.receive_json())

        created = enrol(live, person.site_id)

        pushed = socket.receive_json()
        after = tiles(pushed)

    assert pushed["reason"] == "event", pushed
    assert after["screened"] == before["screened"] + 1
    assert after["enrolled"] == before["enrolled"] + 1
    # The new participant arrives with the protocol's whole visit schedule, so the
    # coordinator's workload moves too rather than a lone orphan row appearing.
    assert after["due_soon"] >= before["due_soon"]

    event = pushed["event"]
    assert event["type"] == "subject.enrolled"
    assert event["label"] == created["subject"]["subject_code"]
    assert event["site_id"] == person.site_id
    # Who did it, shown in the UI's notification. An anonymous change is not a
    # change anybody can act on.
    assert event["actor"]["role_label"] in ("Administrator", "Primary Administrator")
    assert created["subject"]["subject_code"] in event["message"]


def test_an_adverse_event_moves_the_safety_tiles(live, investigators):
    person = investigators[0]
    with open_dashboard(live, token_for_user(person)) as socket:
        before = tiles(socket.receive_json())
        created = report_ae(live, person.site_id)
        pushed = socket.receive_json()
        after = tiles(pushed)

    assert pushed["event"]["type"] == "adverse_event.reported"
    assert after["open_aes"] + after["uncoded"] > before["open_aes"] + before["uncoded"]
    # It lands in Phase 4's coding queue like every other row - no MedDRA code yet.
    assert after["uncoded"] == before["uncoded"] + 1
    assert created["adverse_event"]["is_serious"] is False


def test_a_serious_event_reaches_the_ethics_committee_and_the_regulator(
    live, tokens, investigators
):
    """A serious event starts a regulatory reporting clock, so it is *their* signal.

    Both oversight screens are open at once here, because that is the situation the
    broadcast exists for: one event, several watchers, each recomputed for
    themselves.
    """
    site_id = investigators[0].site_id
    with open_dashboard(live, tokens[UserRole.ETHICS_COMMITTEE.value]) as ethics, \
         open_dashboard(live, tokens[UserRole.REGULATOR.value]) as regulator:
        ethics_before = tiles(ethics.receive_json())
        regulator_before = tiles(regulator.receive_json())

        created = report_ae(live, site_id, serious=True)
        assert created["adverse_event"]["is_serious"] is True

        ethics_after = tiles(ethics.receive_json())
        regulator_message = regulator.receive_json()
        regulator_after = tiles(regulator_message)

    assert ethics_after["serious"] == ethics_before["serious"] + 1
    assert ethics_after["all_aes"] == ethics_before["all_aes"] + 1
    # The regulator's screen is mostly compliance percentages, which can move
    # either way. The audit trail only ever grows - and it grew because of this.
    assert regulator_after["audit"] > regulator_before["audit"]
    assert regulator_message["event"]["type"] == "adverse_event.serious"


def test_a_deviation_moves_the_deviation_counters(live, investigators):
    """Recording a deviation is not an admission of failure; hiding one is."""
    person = investigators[0]
    with open_dashboard(live, token_for_user(person)) as socket:
        before = tiles(socket.receive_json())
        created = log_deviation(live, person.site_id)
        pushed = socket.receive_json()
        after = tiles(pushed)

    assert pushed["event"]["type"] == "visit.deviation"
    assert after["deviations"] == before["deviations"] + 1
    assert created["visit"]["days_late"] > 0
    assert "outside the protocol window" in created["visit"]["deviation_description"]


# ------------------------------------------------- who is told, and how much


def test_another_sites_activity_does_not_disturb_this_investigator(live, investigators):
    """Hard site scoping applies to the live channel too.

    Their numbers would not move, and the nudge itself would leak that something
    happened somewhere they cannot see.

    Two refreshes, not one, on purpose: if a snapshot for the other site's event
    *had* been sent, it would be sitting in the queue between them, and the second
    read would return `reason == "event"` instead of `"refresh"`.
    """
    mine, elsewhere = investigators[1], investigators[0].site_id
    assert mine.site_id != elsewhere

    with open_dashboard(live, token_for_user(mine)) as socket:
        before = tiles(socket.receive_json())

        enrol(live, elsewhere)

        first, second = refresh(socket), refresh(socket)

    assert [first["reason"], second["reason"]] == ["refresh", "refresh"]
    assert tiles(second) == before, "another site's enrolment changed my screen"


def test_an_ethics_reviewer_hears_that_something_changed_not_who(
    live, tokens, investigators
):
    """The snapshot always goes out; the notification is trimmed to fit the role.

    An Ethics Committee member reviews safety and cannot list participants, so
    naming the new participant to them in a live notification would hand over
    exactly what the permission check refuses on `/api/subjects`.
    """
    with open_dashboard(live, tokens[UserRole.ETHICS_COMMITTEE.value]) as socket:
        before = tiles(socket.receive_json())
        created = enrol(live, investigators[0].site_id)
        pushed = socket.receive_json()

    code = created["subject"]["subject_code"]
    event = pushed["event"]
    assert event["detail_withheld"] is True
    assert event["type"] == "subject.enrolled"
    assert event["message"] == "Trial data changed; your figures have been recalculated."
    # Nothing else survives the trim - no participant code, no site, no actor.
    assert set(event) == {"type", "at", "message", "detail_withheld"}
    assert code not in str(event), f"{code} was named to somebody who cannot open it"

    # Their own figures still moved - being told less is not being told wrong.
    assert tiles(pushed)["all_aes"] == before["all_aes"]
    assert pushed["dashboard"]["role"] == UserRole.ETHICS_COMMITTEE.value


def test_a_sponsor_watching_cannot_touch_anything(live, tokens, investigators):
    """The most honest version of the live demo.

    The Sponsor has no write permission - a monitor who could edit the data would
    undermine the data - so their total moving on its own is the whole point:
    somebody else did the work, in another tab.
    """
    token = tokens[UserRole.SPONSOR.value]
    assert live.post(
        "/api/simulate/enrollment",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 403

    with open_dashboard(live, token) as socket:
        before = tiles(socket.receive_json())
        enrol(live, investigators[0].site_id)
        after = tiles(socket.receive_json())

    assert after["enrolled"] == before["enrolled"] + 1
    # A sponsor watches the whole study, so a single site's enrolment still counts.
    assert after["percent"] >= before["percent"]


# ------------------------------------------------- the rows are real


def test_a_simulated_event_writes_a_real_row_and_says_who_did_it(
    live, seeded_engine, investigators, administrator
):
    """Not a number nudged for the demo: a participant, a visit schedule, an audit
    entry. `seed.py --reset` is what puts it back."""
    created = enrol(live, investigators[0].site_id)
    code = created["subject"]["subject_code"]
    assert created["audited"] is True

    with Session(seeded_engine) as session:
        subject = session.exec(
            select(Subject).where(Subject.subject_code == code)
        ).first()
        entry = session.exec(
            select(AuditLog)
            .where(AuditLog.entity_label == code)
            .order_by(AuditLog.id.desc())
        ).first()

    assert subject is not None, "the dashboard moved but no row was written"
    assert subject.site_id == investigators[0].site_id
    # Prakriti (Ayurvedic constitutional type) is assessed once, at enrolment - so a
    # simulated enrolment has one, exactly like a seeded one.
    assert subject.prakriti
    assert subject.enrollment_date is not None

    assert entry is not None, "a write with no audit entry is not 21 CFR Part 11"
    assert entry.action == "create"
    assert entry.entity_type == "subjects"
    assert entry.user_email == administrator.email
    assert "simulated" in entry.reason


def test_a_site_scoped_writer_cannot_choose_someone_elses_site(
    live, seeded_engine, investigators
):
    """The request body is not a way around the scope, any more than the URL is."""
    mine, theirs = investigators[0], investigators[1]
    response = live.post(
        "/api/simulate/enrollment",
        json={"site_id": theirs.site_id},
        headers={"Authorization": f"Bearer {token_for_user(mine)}"},
    )
    assert response.status_code == 201
    assert response.json()["event"]["site_id"] == mine.site_id


def test_simulating_against_an_empty_database_says_what_to_run(empty_client):
    """Before the seed script has run. A 409 that names the command, not a 500."""
    response = empty_client.post("/api/simulate/enrollment", json={})
    assert response.status_code == 409
    assert "seed.py" in response.json()["detail"]
