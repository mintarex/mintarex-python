"""Unit tests for the HTTP client (mirrors Node's test/client.test.js)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable

import httpx
import pytest

from mintarex import (
    AuthenticationError,
    ConfigurationError,
    ConflictError,
    InsufficientBalanceError,
    Mintarex,
    NetworkError,
    NotFoundError,
    PermissionError,
    QuoteExpiredError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError,
)


def _seq_transport(
    responses: list[dict[str, object]],
) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        i = min(len(calls) - 1, len(responses) - 1)
        r = responses[i]
        status = int(r.get("status", 200))  # type: ignore[arg-type]
        body = r.get("body", {})
        body_str = body if isinstance(body, str) else json.dumps(body)
        headers = dict(r.get("headers", {}))  # type: ignore[arg-type]
        headers.setdefault("content-type", "application/json")
        return httpx.Response(status_code=status, content=body_str, headers=headers)

    return httpx.MockTransport(handler), calls


def _client(
    transport: httpx.BaseTransport,
    *,
    max_retries: int = 3,
    timeout: float | None = None,
) -> Mintarex:
    return Mintarex(
        api_key="mxn_test_abc123",
        api_secret="secret",
        transport=transport,
        max_retries=max_retries,
        timeout=timeout,
    )


# ------------------------------------------------------------------ basics


def test_get_signs_with_empty_body_hash_and_correct_headers() -> None:
    t, calls = _seq_transport([{"status": 200, "body": {"balances": [], "timestamp": "t"}}])
    mx = _client(t)
    mx.account.balances()
    assert len(calls) == 1
    req = calls[0]
    h = req.headers
    assert h.get("mx-api-key")
    assert h.get("mx-signature")
    assert h.get("mx-timestamp")
    assert h.get("mx-nonce")
    assert req.method == "GET"
    assert req.content == b""


def test_post_signs_with_body_and_sets_content_type() -> None:
    t, calls = _seq_transport(
        [
            {
                "status": 200,
                "body": {
                    "quote_id": "550e8400-e29b-41d4-a716-446655440000",
                    "base": "BTC",
                    "quote": "USD",
                    "side": "buy",
                    "network": "btc",
                    "price": "1",
                    "base_amount": "1",
                    "quote_amount": "1",
                    "expires_at": "t",
                    "expires_in_ms": 30000,
                },
            }
        ]
    )
    mx = _client(t)
    mx.rfq.quote(
        {"base": "BTC", "quote": "USD", "side": "buy", "amount": "0.1", "amount_type": "base"}
    )
    assert calls[0].method == "POST"
    assert calls[0].headers["content-type"] == "application/json"
    assert b'"base":"BTC"' in calls[0].content


# ------------------------------------------------------------------ retries


def test_retries_on_429_then_succeeds() -> None:
    t, calls = _seq_transport(
        [
            {
                "status": 429,
                "body": {"error": "rate_limited", "message": "slow down"},
                "headers": {"retry-after": "0"},
            },
            {"status": 200, "body": {"balances": [], "timestamp": "t"}},
        ]
    )
    mx = _client(t)
    mx.account.balances()
    assert len(calls) == 2


def test_retries_on_503_then_succeeds() -> None:
    t, calls = _seq_transport(
        [
            {
                "status": 503,
                "body": {"error": "service_unavailable", "message": "try again"},
                "headers": {"retry-after": "0"},
            },
            {"status": 200, "body": {"balances": [], "timestamp": "t"}},
        ]
    )
    mx = _client(t, max_retries=2)
    mx.account.balances()
    assert len(calls) == 2


def test_does_not_retry_on_400() -> None:
    t, calls = _seq_transport(
        [{"status": 400, "body": {"error": "invalid_parameter", "message": "bad"}}]
    )
    mx = _client(t)
    with pytest.raises(ValidationError):
        mx.account.balances()
    assert len(calls) == 1


def test_gives_up_after_max_retries_on_429() -> None:
    t, calls = _seq_transport(
        [
            {
                "status": 429,
                "body": {"error": "r", "message": "x"},
                "headers": {"retry-after": "0"},
            }
        ]
    )
    mx = _client(t, max_retries=2)
    with pytest.raises(RateLimitError):
        mx.account.balances()
    assert len(calls) == 3  # initial + 2 retries


# ---------------------------------------------------------------- error map


@pytest.mark.parametrize(
    ("status", "code", "err"),
    [
        (400, "x", ValidationError),
        (400, "insufficient_balance", InsufficientBalanceError),
        (401, "x", AuthenticationError),
        (403, "x", PermissionError),
        (404, "x", NotFoundError),
        (409, "x", ConflictError),
        (410, "quote_expired_or_not_found", QuoteExpiredError),
        (429, "x", RateLimitError),
        (503, "x", ServiceUnavailableError),
    ],
)
def test_maps_each_http_status_to_correct_error_class(
    status: int, code: str, err: type[Exception]
) -> None:
    t, _ = _seq_transport([{"status": status, "body": {"error": code, "message": "x"}}])
    mx = _client(t, max_retries=0)
    with pytest.raises(err):
        mx.account.balances()


# ------------------------------------------------------------------ rate-limit


def test_parses_ietf_rate_limit_headers_on_success() -> None:
    t, _ = _seq_transport(
        [
            {
                "status": 200,
                "body": {"balances": [], "timestamp": "t"},
                "headers": {
                    "ratelimit-limit": "100",
                    "ratelimit-remaining": "99",
                    "ratelimit-reset": "60",
                    "x-request-id": "req_abc",
                },
            }
        ]
    )
    mx = _client(t)
    r = mx.account.balances()
    meta = r["_meta"]  # type: ignore[index]
    assert meta["rate_limit"].limit == 100
    assert meta["rate_limit"].remaining == 99
    assert meta["rate_limit"].reset == 60
    assert meta["request_id"] == "req_abc"


def test_parses_legacy_x_rate_limit_headers_as_fallback() -> None:
    t, _ = _seq_transport(
        [
            {
                "status": 200,
                "body": {"balances": [], "timestamp": "t"},
                "headers": {
                    "x-ratelimit-limit": "50",
                    "x-ratelimit-remaining": "40",
                    "x-ratelimit-reset": "30",
                },
            }
        ]
    )
    mx = _client(t)
    r = mx.account.balances()
    meta = r["_meta"]  # type: ignore[index]
    assert meta["rate_limit"].limit == 50
    assert meta["rate_limit"].remaining == 40
    assert meta["rate_limit"].reset == 30


def test_parses_rate_limit_info_into_error_on_429() -> None:
    t, _ = _seq_transport(
        [
            {
                "status": 429,
                "body": {"error": "rate_limited", "message": "x"},
                "headers": {"x-ratelimit-remaining": "0", "retry-after": "10"},
            }
        ]
    )
    mx = _client(t, max_retries=0)
    with pytest.raises(RateLimitError) as excinfo:
        mx.account.balances()
    assert excinfo.value.retry_after == 10_000
    assert excinfo.value.rate_limit is not None
    assert excinfo.value.rate_limit.remaining == 0


def test_honors_retry_after_over_default_backoff() -> None:
    t, _ = _seq_transport(
        [
            {
                "status": 429,
                "body": {"error": "r", "message": "x"},
                "headers": {"retry-after": "1"},
            },
            {"status": 200, "body": {"balances": [], "timestamp": "t"}},
        ]
    )
    mx = _client(t, max_retries=1)
    start = time.monotonic()
    mx.account.balances()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.85, f"expected ≥900ms wait, got {elapsed:.3f}s"


def test_retry_after_clamped_to_60s_on_error() -> None:
    t, _ = _seq_transport(
        [
            {
                "status": 429,
                "body": {"error": "x", "message": "x"},
                "headers": {"retry-after": "3600"},  # 1 hour should be clamped
            }
        ]
    )
    mx = _client(t, max_retries=0)
    with pytest.raises(RateLimitError) as excinfo:
        mx.account.balances()
    assert excinfo.value.retry_after is not None
    assert excinfo.value.retry_after <= 60_000


# ------------------------------------------------------------------ network


def _callable_transport(fn: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    return httpx.MockTransport(fn)


def test_network_error_retry_for_get() -> None:
    calls = {"n": 0}

    def handler(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ConnectError("fetch failed")
        return httpx.Response(
            200,
            content=json.dumps({"balances": [], "timestamp": "t"}),
            headers={"content-type": "application/json"},
        )

    mx = _client(_callable_transport(handler), max_retries=1)
    mx.account.balances()
    assert calls["n"] == 2


def test_network_error_no_retry_for_post_without_idempotency_key() -> None:
    calls = {"n": 0}

    def handler(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("fetch failed")

    mx = _client(_callable_transport(handler), max_retries=3)
    with pytest.raises(NetworkError):
        mx.webhooks.create(
            {"url": "https://example.com", "events": ["trade.executed"], "label": "x"}
        )
    assert calls["n"] == 1


def test_network_error_retries_for_post_with_idempotency_key() -> None:
    calls = {"n": 0}

    def handler(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ConnectError("fetch failed")
        return httpx.Response(
            200,
            content=json.dumps(
                {
                    "trade_id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "filled",
                    "base": "BTC",
                    "quote": "USD",
                    "side": "buy",
                    "network": "btc",
                    "price": "1",
                    "base_amount": "1",
                    "quote_amount": "1",
                    "filled_at": "t",
                }
            ),
            headers={"content-type": "application/json"},
        )

    mx = _client(_callable_transport(handler), max_retries=2)
    mx.rfq.accept("550e8400-e29b-41d4-a716-446655440000", idempotency_key="my-key")
    assert calls["n"] == 2


def test_timeout_throws_network_error() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    mx = _client(_callable_transport(handler), max_retries=0, timeout=0.1)
    with pytest.raises(NetworkError):
        mx.account.balances()


def test_non_json_response_body_handled_gracefully() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content="not json <html>", headers={"content-type": "text/html"})

    mx = _client(_callable_transport(handler), max_retries=0)
    with pytest.raises(Exception) as excinfo:
        mx.account.balances()
    assert getattr(excinfo.value, "status", None) == 500


def test_query_string_included_in_signed_path() -> None:
    t, calls = _seq_transport([{"status": 200, "body": {"balances": [], "timestamp": "t"}}])
    mx = _client(t)
    mx.account.balances(currency_type="crypto", include_empty=True)
    url_str = str(calls[0].url)
    assert "currency_type=crypto" in url_str
    # Must be lowercase for cross-SDK parity with Node (which emits "true"/"false").
    assert "include_empty=true" in url_str
    assert "include_empty=True" not in url_str


def test_bool_query_params_use_lowercase() -> None:
    t, calls = _seq_transport([{"status": 200, "body": {"balances": [], "timestamp": "t"}}])
    mx = _client(t)
    mx.account.balances(include_empty=False)
    assert "include_empty=false" in str(calls[0].url)


def test_timeout_rejects_bool() -> None:
    # isinstance(True, int | float) is True, so the constructor must explicitly
    # reject bool to fall back to DEFAULT_TIMEOUT rather than setting timeout=1.
    mx = Mintarex(api_key="mxn_test_x", api_secret="s", timeout=True)  # type: ignore[arg-type]
    # Default is 30s; bool would have set 1s.
    assert mx.client._timeout == 30.0  # type: ignore[attr-defined]


# ------------------------------------------------------------ environment


def test_inferred_environment_test_key_is_sandbox() -> None:
    mx = Mintarex(api_key="mxn_test_abc", api_secret="s")
    assert mx.environment == "sandbox"


def test_inferred_environment_live_key_is_live() -> None:
    mx = Mintarex(api_key="mxn_live_abc", api_secret="s")
    assert mx.environment == "live"


def test_live_env_with_test_key_throws() -> None:
    with pytest.raises(ConfigurationError, match="prefix does not match"):
        Mintarex(
            api_key="mxn_test_abc",
            api_secret="s",
            environment="live",
        )


def test_path_traversal_in_uuid_args_rejected_before_request() -> None:
    t, calls = _seq_transport([{"status": 200, "body": {}}])
    mx = _client(t)
    with pytest.raises(ValidationError):
        mx.trades.get("../../admin")
    assert len(calls) == 0


def test_custom_base_url_rejects_non_http_schemes() -> None:
    with pytest.raises(ConfigurationError, match="Invalid base_url"):
        Mintarex(api_key="mxn_test_x", api_secret="s", base_url="file:///etc/passwd")


def test_http_base_url_rejected_for_public_host() -> None:
    with pytest.raises(ConfigurationError, match="Invalid base_url"):
        Mintarex(
            api_key="mxn_test_x",
            api_secret="s",
            base_url="http://evil.example.com/v1",
        )


def test_http_base_url_allowed_for_localhost() -> None:
    mx = Mintarex(
        api_key="mxn_test_x",
        api_secret="s",
        base_url="http://localhost:5001/v1",
    )
    assert mx.client.base_url.host == "localhost"


def test_http_base_url_allowed_for_127_0_0_1() -> None:
    mx = Mintarex(
        api_key="mxn_test_x",
        api_secret="s",
        base_url="http://127.0.0.1:5001/v1",
    )
    assert mx.client.base_url.host == "127.0.0.1"


def test_address_tag_must_pass_validation() -> None:
    t, _ = _seq_transport([{"status": 200, "body": {}}])
    mx = _client(t)
    with pytest.raises(ValidationError):
        mx.crypto.withdraw(
            {
                "coin": "BTC",
                "network": "btc",
                "amount": "0.1",
                "address": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
                "address_tag": "x" * 200,
                "idempotency_key": "k1",
            }
        )


def test_non_json_serializable_body_throws_configuration_error() -> None:
    t, _ = _seq_transport([{"status": 200, "body": {}}])
    mx = _client(t)

    class NotSerializable:
        pass

    with pytest.raises(ConfigurationError, match="JSON-serializable"):
        mx.client.request(method="POST", path="/x", body={"obj": NotSerializable()})


def test_amount_regex_caps_integer_digits_at_30() -> None:
    t, _ = _seq_transport([{"status": 200, "body": {}}])
    mx = _client(t)
    with pytest.raises(ValidationError):
        mx.rfq.quote(
            {
                "base": "BTC",
                "quote": "USD",
                "side": "buy",
                "amount": "1" + "0" * 31,
                "amount_type": "base",
            }
        )
