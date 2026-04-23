"""Unit tests for client-side validation (mirrors Node's test/validate.test.js)."""

from __future__ import annotations

import httpx
import pytest

from mintarex import (
    ConfigurationError,
    Mintarex,
    ValidationError,
)


def _mock_transport() -> httpx.MockTransport:
    def _handler(_req: httpx.Request) -> httpx.Response:
        raise AssertionError("network should not be reached")

    return httpx.MockTransport(_handler)


def _make_client() -> Mintarex:
    return Mintarex(
        api_key="mxn_test_abc123",
        api_secret="secret",
        transport=_mock_transport(),
    )


@pytest.mark.parametrize(
    "bad",
    ["-1", "+1", "1e3", "1.1234567890123456789", "abc", "", "01"],
)
def test_amount_regex_rejects_bad_inputs(bad: str) -> None:
    mx = _make_client()
    with pytest.raises(ValidationError):
        mx.rfq.quote(
            {"base": "BTC", "quote": "USD", "side": "buy", "amount": bad, "amount_type": "base"}
        )


@pytest.mark.parametrize(
    "good",
    ["0", "1", "0.5", "1.123456789012345678", "1000000"],
)
def test_amount_regex_accepts_canonical_decimals(good: str) -> None:
    mx = _make_client()
    with pytest.raises(AssertionError, match="network should not be reached"):
        mx.rfq.quote(
            {"base": "BTC", "quote": "USD", "side": "buy", "amount": good, "amount_type": "base"}
        )


@pytest.mark.parametrize("bad", ["btc", "B", "TOOLONGCOIN123", "", "BT-C", "BTC_ETH"])
def test_coin_regex_rejects_bad_inputs(bad: str) -> None:
    mx = _make_client()
    with pytest.raises(ValidationError):
        mx.crypto.deposit_address(coin=bad)


@pytest.mark.parametrize("good", ["1INCH", "2Z", "BTC", "USDT", "WBTC"])
def test_coin_regex_accepts_digit_leading_tickers(good: str) -> None:
    mx = _make_client()
    with pytest.raises(AssertionError, match="network should not be reached"):
        mx.crypto.deposit_address(coin=good)


@pytest.mark.parametrize("bad", ["BTC", "btc/eth", "a" * 41, ""])
def test_network_regex_rejects_bad_inputs(bad: str) -> None:
    mx = _make_client()
    with pytest.raises(ValidationError):
        mx.crypto.deposit_address(coin="BTC", network=bad)


@pytest.mark.parametrize(
    "bad",
    ["abc", "a" * 256, "has space", "has\n", ""],
)
def test_address_regex_rejects_bad_inputs(bad: str) -> None:
    mx = _make_client()
    with pytest.raises(ValidationError):
        mx.crypto.withdraw(
            {
                "coin": "BTC",
                "network": "btc",
                "amount": "0.1",
                "address": bad,
                "idempotency_key": "k1",
            }
        )


@pytest.mark.parametrize(
    "bad",
    [
        "not-a-uuid",
        "12345678-1234-1234-1234-123456789012x",
        "",
        "../../etc/passwd",
    ],
)
def test_uuid_regex_rejects_non_uuid(bad: str) -> None:
    mx = _make_client()
    with pytest.raises(ValidationError):
        mx.rfq.accept(bad)


def test_idempotency_key_accepts_generated_uuid_when_omitted() -> None:
    mx = _make_client()
    with pytest.raises(AssertionError, match="network should not be reached"):
        mx.rfq.accept("550e8400-e29b-41d4-a716-446655440000")


@pytest.mark.parametrize(
    "bad",
    [
        "http://example.com",
        "https://user:pass@example.com/hook",
        "not a url",
        "https://" + "a" * 3000,
    ],
)
def test_webhook_url_rejects_http_and_credentials(bad: str) -> None:
    mx = _make_client()
    with pytest.raises(ValidationError):
        mx.webhooks.create({"url": bad, "events": ["trade.executed"], "label": "x"})


def test_webhook_events_validation() -> None:
    mx = _make_client()
    with pytest.raises(ValidationError):
        mx.webhooks.create({"url": "https://example.com", "events": [], "label": "x"})
    with pytest.raises(ValidationError):
        mx.webhooks.create({"url": "https://example.com", "events": ["BAD"], "label": "x"})


def test_mintarex_constructor_rejects_missing_keys() -> None:
    with pytest.raises(ConfigurationError, match="api_key is required"):
        Mintarex(api_key="", api_secret="s")
    with pytest.raises(ConfigurationError, match="must start with"):
        Mintarex(api_key="k", api_secret="s")
    with pytest.raises(ConfigurationError, match="prefix does not match"):
        Mintarex(api_key="mxn_live_abc", api_secret="s", environment="sandbox")
