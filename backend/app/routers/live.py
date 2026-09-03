"""The live channel: a WebSocket that pushes a fresh dashboard on every change.

**WebSocket** is a phone line the browser holds open, so the server can speak
first. Ordinary HTTP is a letter: the browser has to ask before it hears anything,
which is why "live" dashboards usually end up polling every few seconds.

The flow:

    browser  ──── connect /ws/dashboard?token=... ───▶  this file
             ◀─── snapshot (the whole dashboard) ─────
                        ... somebody enrols a participant ...
             ◀─── snapshot (recomputed) ──────────────

Why the token is in the query string: a browser's built-in WebSocket API cannot set
an `Authorization` header. So the token travels as `?token=...`, is verified by the
same `user_from_token` the HTTP side uses, and an unauthenticated socket is closed
immediately rather than accepted and ignored.

Why we resend the whole snapshot rather than a delta: a delta has to be applied to
whatever the browser already had, and if one message is missed the numbers drift
without anybody noticing. Resending is a few kilobytes and it cannot be wrong. It
is also the *same function* `GET /api/dashboard` calls, so a live number and a
refreshed number can never disagree.
"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from fastapi.encoders import jsonable_encoder
from sqlmodel import Session

from app.db import get_engine, get_session
from app.enums import UserRole
from app.events import bus, now_iso
from app.kpi import build_dashboard
from app.rbac import CurrentUser, Permission, user_from_token

router = APIRouter(tags=["live"])

# If nothing happens for this long, send a ping. Two reasons: it proves the line
# is still up, and it is how we notice a browser tab that was closed without a
# clean disconnect.
HEARTBEAT_SECONDS = 25

# Close codes. 1008 is "policy violation", which is the standard way to say
# "you are not allowed in" on a socket - there is no 401 here.
CLOSE_UNAUTHENTICATED = 1008
CLOSE_FORBIDDEN = 1008

# Which permission a viewer needs before they are told the *details* of an event.
# The snapshot itself always goes out - their aggregate figures may have moved
# either way - but the notification alongside it names a record, and naming a
# record to somebody who cannot open it would undo the access rules. An Ethics
# Committee member reviews safety and deviations and cannot list participants, so
# they hear "trial data changed", not "AIIA-ASH-01-083 enrolled".
EVENT_DETAIL_PERMISSION = {
    "subject.enrolled": Permission.SUBJECT_READ,
    "adverse_event.reported": Permission.AE_READ,
    "adverse_event.serious": Permission.AE_READ,
    "visit.deviation": Permission.VISIT_READ,
    "econsent.signed": Permission.ECONSENT_READ,
    "patient_request.created": Permission.PATIENT_REQUEST_READ,
}


def _for_viewer(user: CurrentUser, event: dict | None) -> dict | None:
    """The event as this viewer is allowed to hear it."""
    if event is None:
        return None
    needed = EVENT_DETAIL_PERMISSION.get(event.get("type", ""))
    if needed is None or user.can(needed):
        return event
    return {
        "type": event["type"],
        "at": event.get("at"),
        "message": "Trial data changed; your figures have been recalculated.",
        "detail_withheld": True,
    }



def _visible_to(user: CurrentUser, event: dict | None) -> bool:
    """Should this user be told about this event at all?

    * A patient viewer must ONLY receive events scoped specifically to their own subject_id.
    * A site-scoped staff viewer must not be nudged by another site's activity.
    * Trial-wide roles receive events across all sites.
    """
    if event is None:
        return True

    # Patient visibility is strictly Subject-scoped
    if user.role == UserRole.PATIENT.value:
        event_subject_id = event.get("subject_id")
        return event_subject_id is not None and event_subject_id == user.subject_id

    scope = user.scope_site_id
    if scope is None:
        return True
    site_id = event.get("site_id")
    return site_id is None or site_id == scope


async def _send(websocket: WebSocket, message: dict) -> None:
    """Send one message, converting anything JSON cannot hold on its own.

    An ordinary HTTP route gets this for free: FastAPI runs `jsonable_encoder` over
    whatever the function returns. A WebSocket does not - `send_json` is a thin
    wrapper around `json.dumps`, which raises on a `date`. Since the dashboard is
    full of dates, every outbound message goes through here.
    """
    await websocket.send_json(jsonable_encoder(message))


async def _send_snapshot(
    websocket: WebSocket,
    user: CurrentUser,
    trial_id: int | None,
    *,
    reason: str,
    event: dict | None = None,
) -> None:
    """Recompute this user's dashboard and send it."""
    with Session(get_engine()) as session:
        payload = build_dashboard(session, user, trial_id)
    await _send(
        websocket,
        {
            "type": "snapshot",
            "reason": reason,
            "at": now_iso(),
            "event": event,
            "dashboard": payload,
        },
    )


@router.websocket("/ws/dashboard")
async def dashboard_socket(
    websocket: WebSocket,
    token: str | None = Query(None, description="the access token from /api/auth/login"),
    trial_id: int | None = Query(None),
) -> None:
    # Accept first, so we can send a readable reason before closing. A socket
    # rejected at the handshake gives the browser nothing but "connection failed".
    await websocket.accept()

    if not token:
        await _send(
            websocket,
            {
                "type": "error",
                "detail": "no token. Connect to /ws/dashboard?token=<your access token>",
            },
        )
        await websocket.close(code=CLOSE_UNAUTHENTICATED)
        return

    try:
        with Session(get_engine()) as auth_session:
            user = await user_from_token(token, auth_session)
    except HTTPException as exc:
        await _send(websocket, {"type": "error", "detail": exc.detail})
        await websocket.close(code=CLOSE_UNAUTHENTICATED)
        return

    if not user.can(Permission.TRIAL_READ):
        await _send(
            websocket,
            {
                "type": "error",
                "detail": f"{user.role_label} has no dashboard access",
            },
        )
        await websocket.close(code=CLOSE_FORBIDDEN)
        return

    async with bus.subscribe() as queue:
        await _send(
            websocket,
            {
                "type": "hello",
                "at": now_iso(),
                "user": {
                    "email": user.email,
                    "name": user.full_name,
                    "role": user.role,
                    "role_label": user.role_label,
                },
                "backend": bus.backend,
                "detail": bus.detail,
                "heartbeat_seconds": HEARTBEAT_SECONDS,
            },
        )
        await _send_snapshot(websocket, user, trial_id, reason="connected")

        # Wait on two things at once: an event from the bus, and anything the
        # browser sends (which includes the disconnect notice). Whichever arrives
        # first is handled, and that one future is re-armed.
        wait_event = asyncio.ensure_future(queue.get())
        wait_client = asyncio.ensure_future(websocket.receive())
        try:
            while True:
                done, _ = await asyncio.wait(
                    {wait_event, wait_client},
                    timeout=HEARTBEAT_SECONDS,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if not done:
                    await _send(websocket, {"type": "ping", "at": now_iso()})
                    continue

                if wait_client in done:
                    message = wait_client.result()
                    if message.get("type") == "websocket.disconnect":
                        break
                    wait_client = asyncio.ensure_future(websocket.receive())
                    # Any inbound message means "send me the numbers again". Used by
                    # the UI's refresh button, and handy for debugging by hand.
                    await _send_snapshot(
                        websocket, user, trial_id, reason="refresh"
                    )

                if wait_event in done:
                    event = wait_event.result()
                    wait_event = asyncio.ensure_future(queue.get())
                    if _visible_to(user, event):
                        await _send_snapshot(
                            websocket,
                            user,
                            trial_id,
                            reason="event",
                            event=_for_viewer(user, event),
                        )
        except Exception:
            # A browser tab closing mid-send is normal, not an error worth a
            # traceback in the log. Anything else has already broken the socket, so
            # there is nowhere to report it to anyway.
            pass
        finally:
            for pending in (wait_event, wait_client):
                pending.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await pending
