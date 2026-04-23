"""Webhook signature verification.

Usage::

    from flask import Flask, request
    from mintarex import verify_webhook, WebhookSignatureError

    app = Flask(__name__)

    @app.post("/hook")
    def hook() -> tuple[str, int]:
        try:
            event = verify_webhook(
                body=request.get_data(),           # exact bytes, NOT parsed JSON
                headers=dict(request.headers),
                secret=os.environ["MINTAREX_WEBHOOK_SECRET"],
            )
        except WebhookSignatureError:
            return "", 400
        # handle event
        return "", 204
"""

from __future__ import annotations

import hmac
import json
import time
from collections.abc import Iterable, Mapping
from typing import Any

from .errors import WebhookSignatureError
from .signing import hmac_sign

DEFAULT_TOLERANCE_SECONDS = 300
"""Default tolerance for webhook timestamp skew, in seconds."""

_SIGNATURE_PREFIX = "v1="
_EXPECTED_SIG_HEX_LEN = 64

HeadersInput = Mapping[str, Any] | Iterable[tuple[str, str]]


def verify_webhook(
    *,
    body: str | bytes | bytearray,
    headers: HeadersInput,
    secret: str,
    tolerance_seconds: int | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Verify a webhook signature and return the parsed event.

    Parameters
    ----------
    body : str | bytes
        The raw request body (exact bytes — NOT parsed JSON).
    headers : Mapping or iterable of (name, value) tuples
        Request headers. Lookups are case-insensitive.
    secret : str
        The endpoint's signing secret (``whsec_...``).
    tolerance_seconds : int, optional
        Max allowed clock skew. Default: 300.
    now : float, optional
        Inject current time (for testing).

    Returns
    -------
    dict
        Structured event with keys:
        ``event_type``, ``event_id``, ``delivery_uuid``, ``timestamp``,
        ``sandbox``, ``data``.

    Raises
    ------
    WebhookSignatureError
        On any verification failure (missing headers, bad signature, stale
        timestamp, invalid JSON).
    """
    if not isinstance(secret, str) or not secret:
        raise WebhookSignatureError("secret is required")

    sig_header = _read_header(headers, "x-mintarex-signature")
    ts_header = _read_header(headers, "x-mintarex-timestamp")
    event_type_header = _read_header(headers, "x-mintarex-event-type")
    event_id_header = _read_header(headers, "x-mintarex-event-id")
    delivery_id_header = _read_header(headers, "x-mintarex-delivery-id")

    if not sig_header:
        raise WebhookSignatureError("Missing X-Mintarex-Signature header")
    if not ts_header:
        raise WebhookSignatureError("Missing X-Mintarex-Timestamp header")
    if not event_type_header:
        raise WebhookSignatureError("Missing X-Mintarex-Event-Type header")
    if not event_id_header:
        raise WebhookSignatureError("Missing X-Mintarex-Event-Id header")
    if not delivery_id_header:
        raise WebhookSignatureError("Missing X-Mintarex-Delivery-Id header")

    signature = _parse_signature(sig_header)
    timestamp = _parse_timestamp(ts_header)
    tolerance = tolerance_seconds if tolerance_seconds is not None else DEFAULT_TOLERANCE_SECONDS
    now_sec = int(now if now is not None else time.time())

    if abs(now_sec - timestamp) > tolerance:
        raise WebhookSignatureError(f"Timestamp outside tolerance window (±{tolerance}s)")

    body_str = _body_to_string(body)
    expected = hmac_sign(secret, f"{ts_header}.{body_str}")

    if not _constant_time_hex_equal(expected, signature):
        raise WebhookSignatureError("Signature mismatch")

    try:
        parsed = json.loads(body_str)
    except json.JSONDecodeError as err:
        raise WebhookSignatureError("Body is not valid JSON") from err
    if not isinstance(parsed, dict):
        raise WebhookSignatureError("Body is not a JSON object")

    # Wire shape is `{...event_data, timestamp, sandbox?}`. Lift timestamp
    # and sandbox into structured fields; the rest is the event payload.
    body_timestamp = parsed.pop("timestamp", None)
    sandbox_flag = parsed.pop("sandbox", False)

    return {
        "event_type": event_type_header,
        "event_id": event_id_header,
        "delivery_uuid": delivery_id_header,
        "timestamp": body_timestamp if isinstance(body_timestamp, str) else "",
        "sandbox": sandbox_flag is True,
        "data": parsed,
    }


# ---------------------------------------------------------------- helpers


def _parse_signature(header: str) -> str:
    trimmed = header.strip()
    if not trimmed.startswith(_SIGNATURE_PREFIX):
        raise WebhookSignatureError('Signature must start with "v1="')
    hex_part = trimmed[len(_SIGNATURE_PREFIX) :]
    if len(hex_part) != _EXPECTED_SIG_HEX_LEN or not all(
        c in "0123456789abcdefABCDEF" for c in hex_part
    ):
        raise WebhookSignatureError("Signature is not a 64-char hex string")
    return hex_part.lower()


def _parse_timestamp(header: str) -> int:
    try:
        t = int(header)
    except ValueError as err:
        raise WebhookSignatureError("Timestamp header is not a valid Unix seconds integer") from err
    if t < 0:
        raise WebhookSignatureError("Timestamp header is not a valid Unix seconds integer")
    return t


def _body_to_string(body: object) -> str:
    if isinstance(body, str):
        return body
    if isinstance(body, bytes | bytearray):
        return bytes(body).decode("utf-8")
    raise WebhookSignatureError(
        "body must be a string or bytes (raw request body, NOT parsed JSON)"
    )


def _constant_time_hex_equal(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    try:
        a_bytes = bytes.fromhex(a)
        b_bytes = bytes.fromhex(b)
    except ValueError:
        return False
    return hmac.compare_digest(a_bytes, b_bytes)


def _read_header(headers: HeadersInput, name: str) -> str | None:
    lower = name.lower()
    if isinstance(headers, Mapping):
        for k, v in headers.items():
            if not isinstance(k, str):
                continue
            if k.lower() == lower:
                if isinstance(v, list):
                    return v[0] if v else None
                return v if isinstance(v, str) else None
        return None
    # Iterable of (name, value) tuples
    for item in headers:
        if not isinstance(item, tuple) or len(item) != 2:
            continue
        k, v = item
        if isinstance(k, str) and k.lower() == lower and isinstance(v, str):
            return v
    return None
