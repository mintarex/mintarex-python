"""Client-side validators that mirror the server regexes.

Failing fast here saves a round-trip and gives a clearer error than a 400
from the API.
"""

from __future__ import annotations

import re
from typing import Literal, NoReturn
from urllib.parse import urlparse

from .errors import ValidationError

_AMOUNT_RE = re.compile(r"^(?:0|[1-9]\d{0,29})(?:\.\d{1,18})?$")
_ADDRESS_TAG_RE = re.compile(r"^[\x20-\x7E]{1,100}$")
# Accepts 2-10 uppercase alphanumeric; digit-leading tickers exist (1INCH, 2Z).
_COIN_RE = re.compile(r"^[A-Z0-9]{2,10}$")
_CURRENCY_FIAT_RE = re.compile(r"^[A-Z]{3,10}$")
_CURRENCY_CODE_RE = re.compile(r"^[A-Z0-9]{2,10}$")
_NETWORK_RE = re.compile(r"^[a-z0-9_-]{1,40}$")
_ADDRESS_RE = re.compile(r"^[a-zA-Z0-9:._-]{10,255}$")
_IDEMPOTENCY_RE = re.compile(r"^[\x20-\x7E]{1,64}$")
_LABEL_RE = re.compile(r"^[\x20-\x7E]{1,100}$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_EVENT_RE = re.compile(r"^[a-z]+\.[a-z_]+$")


def _reject(message: str) -> NoReturn:
    raise ValidationError(
        message,
        status=0,
        code="client_validation",
        request_id=None,
        retry_after=None,
        rate_limit=None,
        response_body=None,
    )


def assert_amount(value: object, field: str = "amount") -> str:
    """Decimal with ≤30 integer digits and ≤18 decimal places; no sign, no scientific notation."""
    if not isinstance(value, str):
        _reject(f"{field} must be a decimal string (not {type(value).__name__})")
    if not _AMOUNT_RE.match(value):
        _reject(
            f"{field} must be a decimal with ≤30 integer digits and ≤18 decimal "
            "places, no sign, no scientific notation"
        )
    return value


def assert_address_tag(value: object, field: str = "address_tag") -> str:
    if not isinstance(value, str) or not _ADDRESS_TAG_RE.match(value):
        _reject(f"{field} must be 1-100 printable ASCII characters")
    return value


def assert_coin(value: object, field: str = "coin") -> str:
    if not isinstance(value, str) or not _COIN_RE.match(value):
        _reject(f"{field} must be 2-10 uppercase letters or digits")
    return value


def assert_fiat_currency(value: object, field: str = "currency") -> str:
    if not isinstance(value, str) or not _CURRENCY_FIAT_RE.match(value):
        _reject(f"{field} must be 3-10 uppercase letters")
    return value


def assert_currency_code(value: object, field: str = "currency") -> str:
    """Any currency code — fiat or crypto. Server handles routing."""
    if not isinstance(value, str) or not _CURRENCY_CODE_RE.match(value):
        _reject(f"{field} must be 2-10 uppercase letters or digits")
    return value


def assert_network(value: object, field: str = "network") -> str:
    if not isinstance(value, str) or not _NETWORK_RE.match(value):
        _reject(f"{field} must be 1-40 lowercase [a-z0-9_-]")
    return value


def assert_address(value: object, field: str = "address") -> str:
    if not isinstance(value, str) or not _ADDRESS_RE.match(value):
        _reject(f"{field} must be 10-255 chars, alphanumeric + : . _ -")
    return value


def assert_idempotency_key(value: object, field: str = "idempotency_key") -> str:
    if not isinstance(value, str) or not _IDEMPOTENCY_RE.match(value):
        _reject(f"{field} must be 1-64 printable ASCII characters")
    return value


def assert_label(value: object, field: str = "label") -> str:
    if not isinstance(value, str) or not _LABEL_RE.match(value):
        _reject(f"{field} must be 1-100 printable ASCII characters")
    return value


def assert_side(value: object, field: str = "side") -> Literal["buy", "sell"]:
    if value != "buy" and value != "sell":
        _reject(f'{field} must be "buy" or "sell"')
    return value


def assert_amount_type(value: object, field: str = "amount_type") -> Literal["base", "quote"]:
    if value != "base" and value != "quote":
        _reject(f'{field} must be "base" or "quote"')
    return value


def assert_uuid(value: object, field: str = "uuid") -> str:
    if not isinstance(value, str) or not _UUID_RE.match(value):
        _reject(f"{field} must be a valid UUID")
    return value.lower()


def assert_https_url(value: object, field: str = "url") -> str:
    if not isinstance(value, str):
        _reject(f"{field} must be a string")
    if len(value) > 2048:
        _reject(f"{field} too long (max 2048)")
    try:
        parsed = urlparse(value)
    except (ValueError, TypeError):
        _reject(f"{field} is not a valid URL")
    if not parsed.scheme or not parsed.netloc:
        _reject(f"{field} is not a valid URL")
    if parsed.scheme != "https":
        _reject(f"{field} must use https://")
    if parsed.username or parsed.password:
        _reject(f"{field} must not contain credentials")
    return value


def assert_events(value: object, field: str = "events") -> list[str]:
    if not isinstance(value, list) or len(value) == 0:
        _reject(f"{field} must be a non-empty array")
    out: list[str] = []
    seen: set[str] = set()
    for ev in value:
        if not isinstance(ev, str) or not _EVENT_RE.match(ev):
            _reject(f'{field} entries must look like "domain.action" (lowercase)')
        if ev not in seen:
            seen.add(ev)
            out.append(ev)
    return out


def assert_positive_int(value: object, field: str, max_value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > max_value:
        _reject(f"{field} must be a non-negative integer ≤ {max_value}")
    return value
