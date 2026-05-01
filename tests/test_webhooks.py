"""Unit tests for webhook verification (mirrors Node's test/webhooks.test.js)."""

from __future__ import annotations

import time
from typing import Any

import pytest

from mintarex import WebhookSignatureError, verify_webhook
from mintarex.signing import hmac_sign

SECRET = "mtxhook_test_fixture_key_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"  # noqa: S105


def _sig(ts: str, body: str, secret: str = SECRET) -> str:
    return "v1=" + hmac_sign(secret, f"{ts}.{body}")


def _real_headers(ts: str, sig: str, **overrides: Any) -> dict[str, str]:
    h = {
        "x-mintarex-signature": sig,
        "x-mintarex-timestamp": ts,
        "x-mintarex-event-type": "trade.executed",
        "x-mintarex-event-id": "evt_abc",
        "x-mintarex-delivery-id": "dlv_xyz",
    }
    h.update(overrides)
    return h


def test_accepts_valid_signature_and_reads_metadata_from_headers() -> None:
    import json

    body = json.dumps(
        {"timestamp": "2026-01-01T00:00:00Z", "trade_id": "t_123", "base": "BTC", "quote": "USD"}
    )
    ts = str(int(time.time()))
    event = verify_webhook(
        body=body,
        headers=_real_headers(ts, _sig(ts, body)),
        secret=SECRET,
    )
    assert event["event_type"] == "trade.executed"
    assert event["event_id"] == "evt_abc"
    assert event["delivery_uuid"] == "dlv_xyz"
    assert event["timestamp"] == "2026-01-01T00:00:00Z"
    assert event["sandbox"] is False
    assert event["data"] == {"trade_id": "t_123", "base": "BTC", "quote": "USD"}


def test_surfaces_sandbox_flag_when_present() -> None:
    import json

    body = json.dumps({"timestamp": "2026-01-01T00:00:00Z", "sandbox": True, "trade_id": "t_999"})
    ts = str(int(time.time()))
    event = verify_webhook(body=body, headers=_real_headers(ts, _sig(ts, body)), secret=SECRET)
    assert event["sandbox"] is True
    assert event["data"] == {"trade_id": "t_999"}


def test_rejects_tampered_body() -> None:
    body = '{"timestamp":"2026-01-01T00:00:00Z","trade_id":"t_1"}'
    ts = str(int(time.time()))
    sig = _sig(ts, body)
    with pytest.raises(WebhookSignatureError):
        verify_webhook(
            body=body.replace("t_1", "t_2"),
            headers=_real_headers(ts, sig),
            secret=SECRET,
        )


def test_rejects_wrong_secret() -> None:
    body = '{"timestamp":"t","trade_id":"x"}'
    ts = str(int(time.time()))
    sig = _sig(ts, body, "mtxhook_test_other_key_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    with pytest.raises(WebhookSignatureError):
        verify_webhook(body=body, headers=_real_headers(ts, sig), secret=SECRET)


def test_rejects_stale_timestamp_beyond_tolerance() -> None:
    body = '{"timestamp":"t"}'
    old = str(int(time.time()) - 600)
    sig = _sig(old, body)
    with pytest.raises(WebhookSignatureError):
        verify_webhook(body=body, headers=_real_headers(old, sig), secret=SECRET)


def test_rejects_future_timestamp_beyond_tolerance() -> None:
    body = '{"timestamp":"t"}'
    future = str(int(time.time()) + 600)
    sig = _sig(future, body)
    with pytest.raises(WebhookSignatureError):
        verify_webhook(body=body, headers=_real_headers(future, sig), secret=SECRET)


def test_respects_custom_tolerance() -> None:
    body = '{"timestamp":"t"}'
    old = str(int(time.time()) - 900)
    sig = _sig(old, body)
    event = verify_webhook(
        body=body,
        headers=_real_headers(old, sig),
        secret=SECRET,
        tolerance_seconds=1000,
    )
    assert event["event_type"] == "trade.executed"


@pytest.mark.parametrize(
    "missing",
    [
        "x-mintarex-signature",
        "x-mintarex-timestamp",
        "x-mintarex-event-type",
        "x-mintarex-event-id",
        "x-mintarex-delivery-id",
    ],
)
def test_rejects_missing_required_header(missing: str) -> None:
    body = "{}"
    ts = str(int(time.time()))
    h = _real_headers(ts, _sig(ts, body))
    h.pop(missing, None)
    with pytest.raises(WebhookSignatureError, match="Missing"):
        verify_webhook(body=body, headers=h, secret=SECRET)


def test_rejects_sig_without_v1_prefix() -> None:
    body = "{}"
    ts = str(int(time.time()))
    with pytest.raises(WebhookSignatureError, match="v1="):
        verify_webhook(body=body, headers=_real_headers(ts, "a" * 64), secret=SECRET)


def test_rejects_non_hex_signature() -> None:
    body = "{}"
    ts = str(int(time.time()))
    with pytest.raises(WebhookSignatureError, match="not a 64-char hex"):
        verify_webhook(body=body, headers=_real_headers(ts, "v1=" + "z" * 64), secret=SECRET)


def test_works_with_case_insensitive_headers() -> None:
    body = '{"timestamp":"t","x":1}'
    ts = str(int(time.time()))
    h = {
        "X-Mintarex-Signature": _sig(ts, body),
        "X-Mintarex-Timestamp": ts,
        "X-Mintarex-Event-Type": "trade.executed",
        "X-Mintarex-Event-Id": "evt_h",
        "X-Mintarex-Delivery-Id": "dlv_h",
    }
    ev = verify_webhook(body=body, headers=h, secret=SECRET)
    assert ev["event_type"] == "trade.executed"


def test_works_with_bytes_body() -> None:
    body_str = '{"timestamp":"t","x":1}'
    body = body_str.encode("utf-8")
    ts = str(int(time.time()))
    ev = verify_webhook(body=body, headers=_real_headers(ts, _sig(ts, body_str)), secret=SECRET)
    assert ev["event_type"] == "trade.executed"


def test_rejects_invalid_json_body_even_with_valid_sig() -> None:
    body_str = "not json"
    ts = str(int(time.time()))
    with pytest.raises(WebhookSignatureError, match="not valid JSON"):
        verify_webhook(body=body_str, headers=_real_headers(ts, _sig(ts, body_str)), secret=SECRET)


def test_rejects_array_body_must_be_object() -> None:
    body_str = "[1,2,3]"
    ts = str(int(time.time()))
    with pytest.raises(WebhookSignatureError):
        verify_webhook(body=body_str, headers=_real_headers(ts, _sig(ts, body_str)), secret=SECRET)


def test_rejects_empty_secret() -> None:
    with pytest.raises(WebhookSignatureError, match="secret is required"):
        verify_webhook(body="{}", headers={}, secret="")


def test_constant_time_against_signature_of_different_length() -> None:
    body = "{}"
    ts = str(int(time.time()))
    with pytest.raises(WebhookSignatureError):
        verify_webhook(body=body, headers=_real_headers(ts, "v1=abc"), secret=SECRET)
