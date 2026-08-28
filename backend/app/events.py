"""The live-update bus: how a change in the database reaches an open browser.

**pub/sub (publish / subscribe)** is a radio station. The API *publishes* a short
message like "an enrolment happened at site 2" on a channel; every WebSocket
connection currently *subscribed* to that channel hears it and refreshes its own
numbers. The publisher never needs to know who is listening.

Two backends, chosen automatically at startup:

* **Redis** - the real thing. Redis holds the channel, so several backend
  processes (or a scaled-out deployment) all hear each other's events.
* **in-process** - a plain set of `asyncio.Queue`s inside this one process. Used
  when Redis is missing or unreachable.

The fallback matters because the demo must never die on a missing dependency: one
backend container behaves identically either way, and `/api/health` reports which
backend is live so it is never a mystery.

Token revocation lives here too, in the same class. That looks like two jobs in
one file, and it is - but both need exactly one Redis connection with exactly one
"what if Redis isn't there" answer, and splitting them would duplicate all of
that. A logged-out token's id is remembered until the moment the token would have
expired anyway; after that there is nothing left to revoke.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import datetime, timezone
from typing import AsyncIterator

from app import config

# The one channel everything is broadcast on. A per-role or per-site channel
# would be a premature optimisation: events are tiny and rare, and each
# connection already filters what it cares about.
CHANNEL = "aiia:events"

# Key prefix for logged-out token ids.
REVOKED_PREFIX = "aiia:revoked:"

# Per-connection buffer. If a browser tab is suspended and stops reading, its
# queue fills and further events are dropped for that tab only - the next event
# it does receive triggers a full refresh anyway, so nothing is lost permanently.
QUEUE_SIZE = 64


def now_iso() -> str:
    """Current UTC time as an ISO-8601 string, for stamping events."""
    return datetime.now(timezone.utc).isoformat()


class EventBus:
    """Fan events out to every open WebSocket, and remember revoked tokens."""

    def __init__(self) -> None:
        self._redis = None
        self._pubsub = None
        self._listener: asyncio.Task | None = None
        self._queues: set[asyncio.Queue] = set()
        # Mirrors the Redis deny list. With a single backend process this is all
        # you need; with several, Redis is what makes them agree.
        self._revoked_local: set[str] = set()
        self.backend = "in-process"
        self.detail = "not started"

    # ------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        """Try to attach to Redis. Never raises: failure just means fallback."""
        try:
            import redis.asyncio as aioredis
        except ModuleNotFoundError:
            self.detail = "redis client not installed - using in-process fan-out"
            return

        try:
            client = aioredis.from_url(config.REDIS_URL, decode_responses=True)
            await client.ping()
            pubsub = client.pubsub()
            await pubsub.subscribe(CHANNEL)
        except Exception as exc:  # noqa: BLE001 - any failure means fallback
            self.detail = (
                f"redis unreachable ({type(exc).__name__}) - using in-process fan-out"
            )
            return

        self._redis = client
        self._pubsub = pubsub
        self._listener = asyncio.create_task(self._listen())
        self.backend = "redis"
        self.detail = f"redis pub/sub on {CHANNEL}"

    async def stop(self) -> None:
        if self._listener is not None:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener
            self._listener = None
        if self._pubsub is not None:
            with contextlib.suppress(Exception):
                await self._pubsub.unsubscribe(CHANNEL)
                await self._pubsub.close()
            self._pubsub = None
        if self._redis is not None:
            with contextlib.suppress(Exception):
                await self._redis.close()
            self._redis = None
        self.backend = "in-process"
        self.detail = "stopped"

    # -------------------------------------------------------------- publish

    async def publish(self, event: dict) -> dict:
        """Broadcast one event. Returns the event as it was sent, timestamp added."""
        payload = dict(event)
        payload.setdefault("at", now_iso())

        if self._redis is not None:
            try:
                await self._redis.publish(CHANNEL, json.dumps(payload, default=str))
                # The listener task will fan it out to local queues when Redis
                # echoes it back, so do NOT also deliver it here or every browser
                # would see the same event twice.
                return payload
            except Exception:  # noqa: BLE001 - Redis died mid-demo; keep going
                self._degrade("publish failed")

        self._fanout(payload)
        return payload

    def _fanout(self, event: dict) -> None:
        for queue in list(self._queues):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow consumer; see QUEUE_SIZE

    async def _listen(self) -> None:
        assert self._pubsub is not None
        try:
            async for message in self._pubsub.listen():
                if message.get("type") != "message":
                    continue  # subscribe/unsubscribe confirmations
                try:
                    self._fanout(json.loads(message["data"]))
                except (TypeError, ValueError, KeyError):
                    continue  # something else is publishing junk on our channel
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            self._degrade("subscriber connection lost")

    def _degrade(self, why: str) -> None:
        """Drop to the in-process backend after a Redis failure at runtime."""
        self._redis = None
        self._pubsub = None
        self.backend = "in-process"
        self.detail = f"redis {why} - fell back to in-process fan-out"

    # ------------------------------------------------------------ subscribe

    @contextlib.asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue]:
        """Hand out a queue that receives every event while the block is open."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._queues.add(queue)
        try:
            yield queue
        finally:
            self._queues.discard(queue)

    @property
    def subscriber_count(self) -> int:
        """How many WebSocket connections this process is currently serving."""
        return len(self._queues)

    async def revoke_token(
        self, jti: str, ttl_seconds: int = config.ACCESS_TOKEN_TTL_MINUTES * 60
    ) -> None:
        """Remember that this token was logged out."""
        self._revoked_local.add(jti)
        if self._redis is not None:
            with contextlib.suppress(Exception):
                # SETEX so Redis forgets it exactly when the token would expire.
                await self._redis.setex(REVOKED_PREFIX + jti, max(1, ttl_seconds), "1")

    async def is_token_revoked(self, jti: str | None) -> bool:
        if not jti:
            # A token with no id cannot be revoked individually. Our own tokens
            # always carry one, so this only happens for a hand-rolled token.
            return False
        if jti in self._revoked_local:
            return True
        if self._redis is not None:
            try:
                return bool(await self._redis.exists(REVOKED_PREFIX + jti))
            except Exception:  # noqa: BLE001 - can't check, don't lock people out
                return False
        return False

    def forget_all_revocations(self) -> None:
        """Clear the local deny list. Tests only - never called by the app."""
        self._revoked_local.clear()


# One bus for the whole process, started and stopped by the FastAPI lifespan.
bus = EventBus()
