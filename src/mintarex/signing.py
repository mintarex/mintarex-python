"""HMAC-SHA256 request signing for Mintarex API.

The canonical string format matches the Mintarex gateway verifier exactly:

    METHOD\\nPATH\\nTIMESTAMP\\nNONCE\\nSHA256_HEX(body)

`path` MUST include the query string if any (e.g. ``/v1/trades?limit=10``).
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from typing import TypedDict

EMPTY_BODY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
"""SHA-256 of the empty string. Used for GET / DELETE and body-less POSTs."""


class SignedHeaders(TypedDict):
    """The four auth headers required by the Mintarex API."""

    MX_API_KEY: str
    MX_SIGNATURE: str
    MX_TIMESTAMP: str
    MX_NONCE: str


def build_canonical_string(
    *,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body_hash: str,
) -> str:
    """Build the canonical string fed into the HMAC."""
    return f"{method.upper()}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"


def sha256_hex(body: str | bytes) -> str:
    """SHA-256 hex digest of a body.

    For JSON, pass the serialized ``str``; for empty requests, use
    :data:`EMPTY_BODY_SHA256`.
    """
    if isinstance(body, str):
        body = body.encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def hmac_sign(secret: str, canonical: str) -> str:
    """HMAC-SHA256 signature of ``canonical`` under ``secret`` as lowercase hex."""
    return hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def sign(
    *,
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    body: str | bytes | None = None,
    timestamp: str | None = None,
    nonce: str | None = None,
    now: float | None = None,
) -> dict[str, str]:
    """Produce the four auth headers for a request.

    ``timestamp`` and ``nonce`` are injectable for testing; in production
    leave them unset and they are generated (Unix seconds, UUID v4).

    Caller is responsible for ensuring ``path`` includes any query string
    and ``body`` matches the exact bytes being sent.
    """
    ts = timestamp if timestamp is not None else str(int(now if now is not None else time.time()))
    n = nonce if nonce is not None else str(uuid.uuid4())

    body_hash = EMPTY_BODY_SHA256 if body is None or body in ("", b"") else sha256_hex(body)

    canonical = build_canonical_string(
        method=method,
        path=path,
        timestamp=ts,
        nonce=n,
        body_hash=body_hash,
    )
    signature = hmac_sign(api_secret, canonical)

    return {
        "MX-API-KEY": api_key,
        "MX-SIGNATURE": signature,
        "MX-TIMESTAMP": ts,
        "MX-NONCE": n,
    }
