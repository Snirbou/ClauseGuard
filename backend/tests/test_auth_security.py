"""Unit tests for the auth hardening from the adversarial review.

Covers the pure/near-pure pieces of auth.py: password hashing round-trip and
mismatch, the timing-equalizer dummy verify, and the generalized rate limiter
(per-bucket isolation, X-Forwarded-For keying, and the 429 threshold).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import auth


def _request(headers: dict[str, str] | None = None, host: str = "10.0.0.1"):
    """Minimal stand-in for a Starlette Request for the limiter/keying code."""
    lowered = {k.lower(): v for k, v in (headers or {}).items()}
    return SimpleNamespace(
        headers=SimpleNamespace(get=lambda name, default=None: lowered.get(name.lower(), default)),
        client=SimpleNamespace(host=host),
    )


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

def test_password_hash_roundtrip() -> None:
    h = auth.hash_password("correct-horse-battery")
    assert h != "correct-horse-battery"          # never stored in the clear
    assert auth.verify_password(h, "correct-horse-battery") is True
    assert auth.verify_password(h, "wrong") is False


def test_dummy_verify_exists_and_is_safe() -> None:
    # The timing equalizer must run without raising, for any input.
    auth.dummy_verify("anything")
    auth.dummy_verify("")


def test_credential_format_validation() -> None:
    assert auth.validate_credentials_format("a@b.co", "longenough") is None
    assert auth.validate_credentials_format("not-an-email", "longenough") is not None
    assert auth.validate_credentials_format("a@b.co", "short") is not None


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

def test_rate_limit_threshold() -> None:
    auth._attempts.clear()
    req = _request(host="203.0.113.5")
    for _ in range(5):
        auth.enforce_rate_limit(req, bucket="t", max_attempts=5)
    with pytest.raises(HTTPException) as excinfo:
        auth.enforce_rate_limit(req, bucket="t", max_attempts=5)
    assert excinfo.value.status_code == 429


def test_rate_limit_buckets_are_isolated() -> None:
    auth._attempts.clear()
    req = _request(host="203.0.113.6")
    for _ in range(5):
        auth.enforce_rate_limit(req, bucket="auth", max_attempts=5)
    # A different bucket for the same client still has its full budget.
    auth.enforce_rate_limit(req, bucket="disclaimer", max_attempts=5)


def test_rate_limit_keys_on_forwarded_for() -> None:
    auth._attempts.clear()
    # Same proxy host, different real clients via X-Forwarded-For: each gets
    # its own window, so the proxy does not collapse them into one bucket.
    a = _request(headers={"X-Forwarded-For": "1.1.1.1, 10.0.0.1"}, host="10.0.0.1")
    b = _request(headers={"X-Forwarded-For": "2.2.2.2, 10.0.0.1"}, host="10.0.0.1")
    for _ in range(5):
        auth.enforce_rate_limit(a, bucket="auth", max_attempts=5)
    # b is a distinct client; it must not be rate-limited by a's usage.
    auth.enforce_rate_limit(b, bucket="auth", max_attempts=5)


def test_client_key_prefers_forwarded_for() -> None:
    keyed = auth._client_key(_request(headers={"X-Forwarded-For": "9.9.9.9, 10.0.0.1"}, host="10.0.0.1"))
    assert keyed == "9.9.9.9"
    assert auth._client_key(_request(host="10.0.0.1")) == "10.0.0.1"
