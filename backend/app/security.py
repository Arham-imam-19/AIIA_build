"""Passwords and login tokens. No database access, no FastAPI - just the crypto.

Two ideas, both worth a plain sentence:

**Password hash.** We never store what someone typed. `bcrypt` scrambles it
one-way and deliberately slowly, so checking one password takes a fraction of a
second but guessing millions takes centuries. Verifying means scrambling the
attempt the same way and comparing the scrambles.

**JWT (JSON Web Token).** A signed ID card the server hands you at login. It
says "user 7, sponsor, expires at 6pm" and carries a signature only this server
can produce. The browser presents it with every request; the server checks the
signature instead of looking anything up. Like a festival wristband: the staff
trust the hologram, they don't phone the box office.

Because the token is *signed* and not *encrypted*, anyone can read its contents.
So it holds an id and a role, never a password and nothing confidential.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app import config

# bcrypt only looks at the first 72 bytes of a password. Older versions
# truncated silently, bcrypt 5 raises instead - so we truncate explicitly and get
# the same behaviour on every version.
BCRYPT_MAX_BYTES = 72


class TokenError(Exception):
    """The token was missing, malformed, expired or signed with another key."""


# ------------------------------------------------------------------- passwords


def hash_password(plain: str) -> str:
    """Turn a password into a storable hash. The salt is generated per call, so
    two users with the same password get different hashes."""
    if not plain:
        raise ValueError("password must not be empty")
    encoded = plain.encode("utf-8")[:BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    """True if `plain` is the password behind `hashed`.

    Returns False rather than raising for a user who has no password set yet, or
    for a hash this bcrypt cannot parse - a failed login, not a server error.
    """
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8")[:BCRYPT_MAX_BYTES], hashed.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------- tokens


def create_access_token(
    *,
    user_id: int,
    email: str,
    role: str,
    site_id: int | None,
    ttl_minutes: int | None = None,
) -> tuple[str, datetime, str]:
    """Mint a signed token. Returns (token, expires_at, jti).

    `jti` ("JWT ID") is a random id for this one token. Logout adds it to a deny
    list, which is how you revoke a token that is otherwise self-contained.
    """
    now = datetime.now(timezone.utc)
    ttl = timedelta(minutes=ttl_minutes or config.ACCESS_TOKEN_TTL_MINUTES)
    expires_at = now + ttl
    jti = uuid.uuid4().hex

    payload = {
        # "sub" (subject) is the standard place for who the token is about.
        # Stringified because the JWT spec says sub is a string.
        "sub": str(user_id),
        "email": email,
        "role": role,
        # Carried in the token so the API can scope a site user's queries
        # without a database round trip on every request.
        "site_id": site_id,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)
    # PyJWT 1.x returned bytes; 2.x returns str. Normalise so callers need not care.
    if isinstance(token, bytes):  # pragma: no cover - PyJWT 2.x is pinned
        token = token.decode("utf-8")
    return token, expires_at, jti


def decode_access_token(token: str) -> dict:
    """Verify the signature and expiry, and return the claims.

    Every failure becomes one `TokenError` with a human-readable message, so the
    caller can turn it into a single 401 without a pile of except branches.
    """
    if not token:
        raise TokenError("no token supplied")
    try:
        claims = jwt.decode(
            token,
            config.JWT_SECRET,
            algorithms=[config.JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token has expired; log in again") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError(f"invalid token: {exc}") from exc

    try:
        claims["user_id"] = int(claims["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenError("token subject is not a user id") from exc
    return claims


def seconds_until(expiry: datetime | int | float) -> int:
    """How long until `expiry`, floored at zero.

    Used to give a deny-listed token a Redis TTL: once the token would have
    expired on its own there is nothing left to revoke, so the entry can go.
    """
    if isinstance(expiry, datetime):
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        remaining = (expiry - datetime.now(timezone.utc)).total_seconds()
    else:
        remaining = expiry - datetime.now(timezone.utc).timestamp()
    return max(0, int(remaining))
