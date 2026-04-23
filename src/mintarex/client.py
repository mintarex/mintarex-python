"""HTTP client for the Mintarex Corporate API.

Handles request signing, JSON serialization, retry backoff, IETF ``RateLimit-*``
parsing, and typed-error mapping. Built on :mod:`httpx` for HTTP/2 support and
consistent behaviour across platforms.
"""

from __future__ import annotations

import json
import random
import time
from typing import Any, Literal, cast

import httpx

from .errors import (
    ConfigurationError,
    NetworkError,
    RateLimitInfo,
    error_from_response,
)
from .signing import sign
from .types import Environment, ResponseMeta

SDK_VERSION = "0.0.1"

DEFAULT_BASE_URL = "https://institutional.mintarex.com/v1"
DEFAULT_STREAM_BASE_URL = "https://institutional.mintarex.com/v1/stream"
DEFAULT_TIMEOUT_S = 30.0
DEFAULT_MAX_RETRIES = 3
MAX_RETRY_AFTER_MS = 60_000

LIVE_KEY_PREFIX = "mxn_live_"
TEST_KEY_PREFIX = "mxn_test_"

HttpMethod = Literal["GET", "POST", "DELETE", "PUT", "PATCH"]


class MintarexClient:
    """Signed HTTP client for the Mintarex API.

    Construct once per API key and reuse across requests. Safe to share
    between threads.

    Parameters
    ----------
    api_key : str
        The public part of the API credential (``mxn_live_...`` or ``mxn_test_...``).
    api_secret : str
        The secret part used to sign requests.
    environment : {"live", "sandbox"}, optional
        Inferred from the key prefix if omitted. Must match the prefix.
    base_url : str, optional
        Override the API base URL. HTTPS required (loopback may use HTTP).
    stream_base_url : str, optional
        Override the SSE base URL. Same scheme rules as ``base_url``.
    timeout : float, optional
        Per-request timeout in seconds. Default: 30.
    max_retries : int, optional
        Max retries for 429/503 and network errors. Clamped to ``[0, 10]``.
        Default: 3.
    transport : httpx.BaseTransport, optional
        Inject a custom transport (tests, mocking).
    user_agent : str, optional
        Extra text appended to the default User-Agent.
    """

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: Environment | None = None,
        base_url: str | None = None,
        stream_base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        transport: httpx.BaseTransport | None = None,
        user_agent: str | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key:
            raise ConfigurationError("api_key is required")
        if not isinstance(api_secret, str) or not api_secret:
            raise ConfigurationError("api_secret is required")

        env = environment if environment is not None else _infer_environment(api_key)
        if env not in ("live", "sandbox"):
            raise ConfigurationError(f"Invalid environment: {env!r}")
        if (env == "live" and not api_key.startswith(LIVE_KEY_PREFIX)) or (
            env == "sandbox" and not api_key.startswith(TEST_KEY_PREFIX)
        ):
            raise ConfigurationError(
                f'api_key prefix does not match environment "{env}". '
                "Live keys start with mxn_live_, sandbox keys with mxn_test_."
            )

        self._api_key = api_key
        self._api_secret = api_secret
        self.environment: Environment = env
        self.base_url = _parse_base_url(base_url or DEFAULT_BASE_URL, "base_url")
        self.stream_base_url = _parse_base_url(
            stream_base_url or DEFAULT_STREAM_BASE_URL, "stream_base_url"
        )

        # Bool check is first because isinstance(True, int | float) is True.
        self._timeout = (
            timeout
            if isinstance(timeout, int | float) and not isinstance(timeout, bool) and timeout > 0
            else DEFAULT_TIMEOUT_S
        )
        self._max_retries = (
            min(max_retries, 10)
            if isinstance(max_retries, int)
            and not isinstance(max_retries, bool)
            and max_retries >= 0
            else DEFAULT_MAX_RETRIES
        )
        self._user_agent_extra = (
            f" {user_agent}" if isinstance(user_agent, str) and user_agent else ""
        )

        # httpx client reused for connection pooling. `redirects` disabled so
        # we never follow a 3xx away from the configured base URL.
        self._http = httpx.Client(
            timeout=self._timeout,
            follow_redirects=False,
            transport=transport,
        )

    def close(self) -> None:
        """Release HTTP pool resources."""
        self._http.close()

    def __enter__(self) -> MintarexClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    # ------------------------------------------------------------------ request
    def request(
        self,
        *,
        method: HttpMethod,
        path: str,
        query: dict[str, str | int | bool | None] | None = None,
        body: object | None = None,
        max_retries: int | None = None,
        retry_on_network_error: bool | None = None,
    ) -> dict[str, Any]:
        """Execute a signed request.

        Returns the parsed JSON body (a ``dict`` for object responses).
        Response metadata (request-id, rate-limit) is attached as the
        special key ``"_meta"`` when the body is a JSON object.
        """
        normalized = self._normalize_request(method=method, path=path, query=query, body=body)
        retries = max_retries if max_retries is not None else self._max_retries
        retry_net = (
            retry_on_network_error
            if retry_on_network_error is not None
            else _default_retry_on_network_error(normalized["method"], body)
        )

        attempt = 0
        last_error: Exception | None = None

        while attempt <= retries:
            try:
                resp = self._execute_once(normalized)
                if resp["ok"]:
                    result = resp["body"] if isinstance(resp["body"], dict) else {}
                    # Attach meta non-destructively when response is an object.
                    if isinstance(resp["body"], dict):
                        result = dict(resp["body"])
                        result["_meta"] = resp["meta"]
                    return result

                api_error = error_from_response(
                    status=resp["meta"]["status"],
                    code=resp["error_code"],
                    message=resp["error_message"],
                    request_id=resp["meta"]["request_id"],
                    retry_after=resp["retry_after"],
                    rate_limit=resp["meta"]["rate_limit"],
                    response_body=resp["body"],
                )
                if _should_retry_status(resp["meta"]["status"]) and attempt < retries:
                    time.sleep(_backoff_seconds(attempt, resp["retry_after"]))
                    attempt += 1
                    continue
                raise api_error

            except NetworkError as err:
                if retry_net and attempt < retries:
                    last_error = err
                    time.sleep(_backoff_seconds(attempt, None))
                    attempt += 1
                    continue
                raise

        raise last_error if last_error is not None else NetworkError("Retry limit exceeded")

    # ------------------------------------------------------------- signForStream
    def sign_for_stream_token(self) -> dict[str, Any]:
        """Produce the signed request for POST /stream/token.

        Returned as a plain dict so a streaming consumer can issue the request
        directly without going through :meth:`request` (avoids mismatched
        timeout semantics with SSE).
        """
        path = _join_path(self.base_url.path, "/stream/token")
        body_bytes = ""
        headers = sign(
            api_key=self._api_key,
            api_secret=self._api_secret,
            method="POST",
            path=path,
            body=body_bytes,
        )
        headers.update(
            {
                "Accept": "application/json",
                "User-Agent": self._user_agent(),
            }
        )
        return {
            "method": "POST",
            "url": str(self.base_url.copy_with(path=path)),
            "headers": headers,
            "body": body_bytes,
        }

    # ---------------------------------------------------------------- internals
    @property
    def http_client(self) -> httpx.Client:
        """Expose the underlying httpx client for SSE streaming."""
        return self._http

    def _user_agent(self) -> str:
        import platform

        py = platform.python_version()
        return f"mintarex-python/{SDK_VERSION} (python {py}){self._user_agent_extra}"

    def _normalize_request(
        self,
        *,
        method: HttpMethod,
        path: str,
        query: dict[str, str | int | bool | None] | None,
        body: object | None,
    ) -> dict[str, Any]:
        m = method.upper()
        if not m.isalpha():
            raise ConfigurationError(f"Invalid HTTP method: {method!r}")
        if not isinstance(path, str) or not path.startswith("/"):
            raise ConfigurationError(
                f'path must be a string starting with "/" (got {type(path).__name__})'
            )

        url = self.base_url.copy_with(path=_join_path(self.base_url.path, path), fragment="")
        if query:
            # httpx expects the tuple form (invariant list would be rejected by mypy).
            # Bools are lowercased for cross-SDK parity with Node's `String(true) === "true"`
            # — Python's str(True) returns "True", which the server would treat as a
            # different literal if it does a strict string compare.
            params = tuple((k, _encode_query_value(v)) for k, v in query.items() if v is not None)
            url = url.copy_merge_params(params)

        canonical_path = url.raw_path.decode("ascii") if url.raw_path else url.path

        body_bytes: str | None = None
        if body is not None and m not in ("GET", "DELETE"):
            try:
                body_bytes = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
            except (TypeError, ValueError) as err:
                raise ConfigurationError(f"Request body is not JSON-serializable: {err}") from err

        return {
            "url": url,
            "method": m,
            "canonical_path": canonical_path,
            "body_bytes": body_bytes,
        }

    def _execute_once(self, req: dict[str, Any]) -> dict[str, Any]:
        headers = sign(
            api_key=self._api_key,
            api_secret=self._api_secret,
            method=req["method"],
            path=req["canonical_path"],
            body=req["body_bytes"],
        )
        headers.update(
            {
                "Accept": "application/json",
                "User-Agent": self._user_agent(),
            }
        )
        body_bytes: str | None = req["body_bytes"]
        if body_bytes is not None:
            headers["Content-Type"] = "application/json"

        try:
            response = self._http.request(
                method=req["method"],
                url=req["url"],
                headers=headers,
                content=body_bytes,
            )
        except httpx.TimeoutException as err:
            raise NetworkError(f"Request timed out after {self._timeout}s") from err
        except httpx.HTTPError as err:
            raise NetworkError(str(err) or "Network error") from err

        content_type = response.headers.get("content-type", "").lower()
        raw_text = response.text
        body: Any = None
        if raw_text:
            if "application/json" in content_type:
                try:
                    body = json.loads(raw_text)
                except json.JSONDecodeError:
                    body = {"error": "invalid_json", "message": raw_text[:500]}
            else:
                body = {"error": "non_json_response", "message": raw_text[:500]}

        rate_limit = _read_rate_limit_headers(response)
        meta: ResponseMeta = {
            "request_id": response.headers.get("x-request-id"),
            "rate_limit": rate_limit,
            "status": response.status_code,
        }
        retry_after = _parse_retry_after(response.headers.get("retry-after"))

        error_code = "unknown_error"
        error_message = f"HTTP {response.status_code}"
        if not response.is_success and isinstance(body, dict):
            if isinstance(body.get("error"), str):
                error_code = cast(str, body["error"])
            if isinstance(body.get("message"), str):
                error_message = cast(str, body["message"])

        return {
            "ok": response.is_success,
            "body": body,
            "error_code": error_code,
            "error_message": error_message,
            "retry_after": retry_after,
            "meta": meta,
        }


# ------------------------------------------------------------------ helpers


def _infer_environment(api_key: str) -> Environment:
    if api_key.startswith(LIVE_KEY_PREFIX):
        return "live"
    if api_key.startswith(TEST_KEY_PREFIX):
        return "sandbox"
    raise ConfigurationError(
        "api_key must start with mxn_live_ or mxn_test_ (or set environment explicitly)."
    )


def _parse_base_url(input_url: str, name: str) -> httpx.URL:
    try:
        u = httpx.URL(input_url)
    except (httpx.InvalidURL, TypeError, ValueError) as err:
        raise ConfigurationError(f"Invalid {name}: {input_url} ({err})") from err
    if u.scheme == "https":
        return u
    if u.scheme == "http" and _is_loopback(u.host):
        return u
    raise ConfigurationError(
        f"Invalid {name}: {input_url} ("
        + (
            "http:// is only permitted for loopback (localhost / 127.x / ::1)"
            if u.scheme == "http"
            else "protocol must be https://"
        )
        + ")"
    )


def _is_loopback(host: str) -> bool:
    return host == "localhost" or host in ("::1", "[::1]") or host.startswith("127.")


def _encode_query_value(v: str | int | bool | float) -> str:
    # bool check MUST come before int because `isinstance(True, int)` is True.
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _join_path(a: str, b: str) -> str:
    left = a[:-1] if a.endswith("/") else a
    right = b if b.startswith("/") else "/" + b
    return left + right


def _read_rate_limit_headers(response: httpx.Response) -> RateLimitInfo:
    # IETF RFC 9331 (`RateLimit-*` without prefix) preferred; legacy
    # `X-RateLimit-*` falls through. httpx headers are case-insensitive.
    def get_one(name: str) -> int | None:
        v = response.headers.get(name) or response.headers.get(f"x-{name}")
        if v is None:
            return None
        try:
            return int(float(v))
        except (ValueError, TypeError):
            return None

    return RateLimitInfo(
        limit=get_one("ratelimit-limit"),
        remaining=get_one("ratelimit-remaining"),
        reset=get_one("ratelimit-reset"),
    )


def _parse_retry_after(value: str | None) -> int | None:
    """Parse ``Retry-After`` header into milliseconds, clamped to [0, 60000]."""
    if value is None:
        return None
    try:
        n = float(value)
        return max(0, min(MAX_RETRY_AFTER_MS, int(n * 1000)))
    except ValueError:
        pass
    # HTTP-date form
    from email.utils import parsedate_to_datetime

    try:
        ts = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if ts is None:
        return None
    delta_ms = int(ts.timestamp() * 1000 - time.time() * 1000)
    return max(0, min(MAX_RETRY_AFTER_MS, delta_ms))


def _should_retry_status(status: int) -> bool:
    return status == 429 or status == 503


def _default_retry_on_network_error(method: str, body: object | None) -> bool:
    return method in ("GET", "DELETE") or (isinstance(body, dict) and "idempotency_key" in body)


def _backoff_seconds(attempt: int, retry_after_ms: int | None) -> float:
    if retry_after_ms is not None and retry_after_ms > 0:
        capped = min(retry_after_ms, MAX_RETRY_AFTER_MS)
        max_jitter = min(capped * 0.1, 5000)
        jitter = int((random.random() * 2 - 1) * max_jitter)  # noqa: S311
        return max(0.0, (capped + jitter) / 1000.0)
    base_ms = 500 * (2**attempt)
    jitter_ms: int = random.randint(0, 250)  # noqa: S311
    return float(min(base_ms + jitter_ms, 15_000)) / 1000.0
