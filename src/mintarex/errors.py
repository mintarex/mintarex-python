"""Typed exceptions raised by the Mintarex SDK.

The hierarchy mirrors the Node SDK:

- :class:`MintarexError` — base class for all SDK errors.
- :class:`MintarexAPIError` — HTTP response from the API was non-2xx.
- Subclasses of :class:`MintarexAPIError` narrow by status + API error code.
- :class:`NetworkError` — no HTTP response (DNS, TCP, TLS, timeout).
- :class:`WebhookSignatureError` — webhook verification failed.
- :class:`ConfigurationError` — SDK misconfigured (bad apiKey/baseURL/etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RateLimitInfo:
    """Parsed IETF ``RateLimit-*`` response headers (RFC 9331)."""

    limit: int | None
    remaining: int | None
    reset: int | None


class MintarexError(Exception):
    """Base class for all SDK errors."""


class MintarexAPIError(MintarexError):
    """Non-2xx HTTP response from the API."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        code: str,
        request_id: str | None = None,
        retry_after: int | None = None,
        rate_limit: RateLimitInfo | None = None,
        response_body: Any = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.request_id = request_id
        self.retry_after = retry_after
        self.rate_limit = rate_limit
        self.response_body = response_body


class AuthenticationError(MintarexAPIError):
    """401 — API key not recognized or signature invalid."""


class PermissionError_(MintarexAPIError):
    """403 — API key is valid but lacks the required scope or permission.

    Named ``PermissionError_`` to avoid colliding with the built-in.
    Exposed as ``PermissionError`` via ``mintarex.__init__``.
    """


class ValidationError(MintarexAPIError):
    """400 — request validation failed (malformed params, bad amount, etc.)."""


class InsufficientBalanceError(MintarexAPIError):
    """400 with code ``insufficient_balance`` — wallet balance too low."""


class NotFoundError(MintarexAPIError):
    """404 — resource not found."""


class ConflictError(MintarexAPIError):
    """409 — idempotency-key conflict, quote already consumed, duplicate address, etc."""


class QuoteExpiredError(MintarexAPIError):
    """410 — RFQ quote expired (issued more than 30 seconds ago)."""


class RateLimitError(MintarexAPIError):
    """429 — rate limit or concurrency cap exceeded."""


class ServerError(MintarexAPIError):
    """500 — server-side error."""


class ServiceUnavailableError(MintarexAPIError):
    """503 — service temporarily unavailable; inspect ``retry_after``."""


class NetworkError(MintarexError):
    """Network-layer failure (DNS, TCP reset, TLS, timeout). No HTTP response received."""


class WebhookSignatureError(MintarexError):
    """Webhook verification failed — bad signature, missing headers, or stale timestamp."""


class ConfigurationError(MintarexError):
    """SDK mis-configuration (missing apiKey/apiSecret, invalid baseURL, etc.)."""


def error_from_response(
    *,
    status: int,
    code: str,
    message: str,
    request_id: str | None,
    retry_after: int | None,
    rate_limit: RateLimitInfo | None,
    response_body: Any,
) -> MintarexAPIError:
    """Map HTTP status + API error code to the most specific typed error class.

    Prefers the API's ``error`` code over the HTTP status when the code pinpoints
    a narrower case (e.g. ``insufficient_balance`` within a 400).
    """
    kwargs: dict[str, Any] = {
        "status": status,
        "code": code,
        "request_id": request_id,
        "retry_after": retry_after,
        "rate_limit": rate_limit,
        "response_body": response_body,
    }

    if code == "insufficient_balance":
        return InsufficientBalanceError(message, **kwargs)
    if code == "quote_expired_or_not_found":
        return QuoteExpiredError(message, **kwargs)

    if status == 400:
        return ValidationError(message, **kwargs)
    if status == 401:
        return AuthenticationError(message, **kwargs)
    if status == 403:
        return PermissionError_(message, **kwargs)
    if status == 404:
        return NotFoundError(message, **kwargs)
    if status == 409:
        return ConflictError(message, **kwargs)
    if status == 410:
        return QuoteExpiredError(message, **kwargs)
    if status == 429:
        return RateLimitError(message, **kwargs)
    if status == 503:
        return ServiceUnavailableError(message, **kwargs)
    if status >= 500:
        return ServerError(message, **kwargs)

    return MintarexAPIError(message, **kwargs)
