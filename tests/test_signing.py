"""Unit tests for HMAC signing (mirrors Node's test/signing.test.js)."""

from __future__ import annotations

import re

from mintarex import (
    EMPTY_BODY_SHA256,
    build_canonical_string,
    hmac_sign,
    sha256_hex,
    sign,
)


def test_empty_body_sha256_matches_sha_of_empty_string() -> None:
    assert sha256_hex("") == EMPTY_BODY_SHA256


def test_canonical_string_format_matches_spec() -> None:
    s = build_canonical_string(
        method="GET",
        path="/v1/account/balances",
        timestamp="1712582345",
        nonce="550e8400-e29b-41d4-a716-446655440000",
        body_hash=EMPTY_BODY_SHA256,
    )
    assert s == (
        "GET\n/v1/account/balances\n1712582345\n"
        "550e8400-e29b-41d4-a716-446655440000\n" + EMPTY_BODY_SHA256
    )


def test_canonical_string_uppercases_method() -> None:
    s = build_canonical_string(
        method="post",
        path="/v1/rfq",
        timestamp="1",
        nonce="n",
        body_hash="h",
    )
    assert s.startswith("POST\n")


def test_hmac_sign_returns_64_char_lowercase_hex() -> None:
    sig = hmac_sign("secret", "hello")
    assert re.match(r"^[0-9a-f]{64}$", sig)


def test_sign_produces_all_four_required_headers() -> None:
    h = sign(
        api_key="mxn_live_abc",
        api_secret="deadbeef",
        method="GET",
        path="/v1/account/fees",
        timestamp="1712582345",
        nonce="550e8400-e29b-41d4-a716-446655440000",
    )
    assert h["MX-API-KEY"] == "mxn_live_abc"
    assert h["MX-TIMESTAMP"] == "1712582345"
    assert h["MX-NONCE"] == "550e8400-e29b-41d4-a716-446655440000"
    assert re.match(r"^[0-9a-f]{64}$", h["MX-SIGNATURE"])


def test_sign_deterministic_for_same_inputs() -> None:
    kwargs = {
        "api_key": "mxn_live_abc",
        "api_secret": "secret",
        "method": "POST",
        "path": "/v1/rfq",
        "body": '{"base":"BTC","quote":"USD"}',
        "timestamp": "1000",
        "nonce": "nnn",
    }
    assert sign(**kwargs)["MX-SIGNATURE"] == sign(**kwargs)["MX-SIGNATURE"]


def test_sign_differs_when_any_signed_input_changes() -> None:
    base = {
        "api_key": "mxn_live_abc",
        "api_secret": "s",
        "method": "POST",
        "path": "/v1/rfq",
        "body": "x",
        "timestamp": "1",
        "nonce": "n",
    }
    variants = [
        base,
        {**base, "method": "GET"},
        {**base, "path": "/v1/other"},
        {**base, "timestamp": "2"},
        {**base, "nonce": "n2"},
        {**base, "body": "y"},
        {**base, "api_secret": "s2"},
    ]
    sigs = {sign(**v)["MX-SIGNATURE"] for v in variants}
    assert len(sigs) == 7


def test_sign_handles_bytes_body() -> None:
    from_str = sign(
        api_key="k",
        api_secret="s",
        method="POST",
        path="/p",
        body="hello",
        timestamp="1",
        nonce="n",
    )
    from_bytes = sign(
        api_key="k",
        api_secret="s",
        method="POST",
        path="/p",
        body=b"hello",
        timestamp="1",
        nonce="n",
    )
    assert from_str["MX-SIGNATURE"] == from_bytes["MX-SIGNATURE"]


def test_sign_with_empty_body_uses_empty_body_sha256() -> None:
    canonical = build_canonical_string(
        method="GET",
        path="/v1/account/fees",
        timestamp="1",
        nonce="n",
        body_hash=EMPTY_BODY_SHA256,
    )
    expected = hmac_sign("secret", canonical)
    actual = sign(
        api_key="k",
        api_secret="secret",
        method="GET",
        path="/v1/account/fees",
        timestamp="1",
        nonce="n",
    )
    assert actual["MX-SIGNATURE"] == expected
