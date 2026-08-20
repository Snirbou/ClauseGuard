"""Authentication — Argon2 password hashing + server-side cookie sessions.

Design (AC-A01–A04):

- Passwords are hashed with Argon2id (argon2-cffi defaults) and never
  stored or logged in any other form.
- A session is a 256-bit random token delivered in an httpOnly cookie.
  Only the token's sha256 lands in the database, so a leaked database
  cannot be replayed as live sessions. Logout revokes server-side.
- The frontend talks to the API through a same-origin Next.js rewrite, so
  the cookie works with SameSite=Lax over plain http in development; set
  SESSION_COOKIE_SECURE=true behind HTTPS.
- Auth endpoints are rate-limited per client address with a small in-memory
  sliding window — enough to blunt credential stuffing on a single-process
  deployment without new infrastructure.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from logger import get_logger
from models import Session, User

logger = get_logger(__name__)

SESSION_COOKIE = "cg_session"
SESSION_TTL = timedelta(days=30)

_hasher = PasswordHasher()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, candidate: str) -> bool:
    try:
        return _hasher.verify(password_hash, candidate)
    except VerifyMismatchError:
        return False
    except Exception:
        logger.exception("Password verification errored (treating as mismatch).")
        return False


def validate_credentials_format(email: str, password: str) -> str | None:
    """Return a human-readable problem, or None when the format is fine."""
    if not _EMAIL_RE.match(email or ""):
        return "Enter a valid email address."
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return None


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_session(db: AsyncSession, user_id) -> str:
    """Create a session row; returns the raw token for the cookie."""
    token = secrets.token_urlsafe(32)
    db.add(
        Session(
            user_id=user_id,
            token_hash=_token_hash(token),
            expires_at=datetime.now(UTC) + SESSION_TTL,
        )
    )
    await db.commit()
    return token


async def revoke_session(db: AsyncSession, token: str) -> None:
    row = (
        await db.execute(select(Session).where(Session.token_hash == _token_hash(token)))
    ).scalars().first()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        await db.commit()


async def resolve_session(db: AsyncSession, token: str) -> User | None:
    """Return the session's user when the token is live, else None."""
    row = (
        await db.execute(select(Session).where(Session.token_hash == _token_hash(token)))
    ).scalars().first()
    if row is None or row.revoked_at is not None:
        return None
    if row.expires_at < datetime.now(UTC):
        return None
    return await db.get(User, row.user_id)


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.SESSION_COOKIE_SECURE,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, path="/")


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require a live session. 401 with the standard error envelope otherwise."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    user = await resolve_session(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Your session has expired. Sign in again.")
    return user


# ---------------------------------------------------------------------------
# Rate limiting (auth endpoints only)
# ---------------------------------------------------------------------------

_WINDOW_SECONDS = 60
_MAX_ATTEMPTS = 10
_attempts: dict[str, deque[float]] = defaultdict(deque)


def enforce_auth_rate_limit(request: Request) -> None:
    """At most _MAX_ATTEMPTS auth calls per client address per minute."""
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _attempts[client]
    while window and now - window[0] > _WINDOW_SECONDS:
        window.popleft()
    if len(window) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Wait a minute and try again.",
        )
    window.append(now)
