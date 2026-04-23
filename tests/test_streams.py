"""Unit tests for the SSE chunk parser (streams internals)."""

from __future__ import annotations

from mintarex.streams import _find_event_boundary, _parse_sse_chunk


def test_find_event_boundary_lf_lf() -> None:
    assert _find_event_boundary("data: x\n\nmore") == 7


def test_find_event_boundary_crlf_crlf() -> None:
    assert _find_event_boundary("data: x\r\n\r\nmore") == 7


def test_find_event_boundary_cr_cr() -> None:
    assert _find_event_boundary("data: x\r\rmore") == 7


def test_find_event_boundary_none_found() -> None:
    assert _find_event_boundary("data: x\ndata: y\n") == -1


def test_find_event_boundary_prefers_earliest_terminator() -> None:
    # LF-LF at pos 7, CRLF-CRLF at pos 20 → earliest wins
    assert _find_event_boundary("data: x\n\ndata: y\r\n\r\n") == 7


def test_parse_sse_chunk_default_event_name() -> None:
    msg = _parse_sse_chunk("data: hello")
    assert msg is not None
    assert msg.event == "message"
    assert msg.data == "hello"
    assert msg.id is None


def test_parse_sse_chunk_json_payload() -> None:
    msg = _parse_sse_chunk('event: trade.executed\ndata: {"x":1}')
    assert msg is not None
    assert msg.event == "trade.executed"
    assert msg.data == {"x": 1}


def test_parse_sse_chunk_invalid_json_stays_string() -> None:
    msg = _parse_sse_chunk("data: not json {{")
    assert msg is not None
    assert msg.data == "not json {{"


def test_parse_sse_chunk_multiline_data() -> None:
    msg = _parse_sse_chunk("data: line1\ndata: line2")
    assert msg is not None
    assert msg.raw == "line1\nline2"


def test_parse_sse_chunk_with_id() -> None:
    msg = _parse_sse_chunk("id: 42\ndata: hi")
    assert msg is not None
    assert msg.id == "42"


def test_parse_sse_chunk_heartbeat_only_returns_none() -> None:
    # Lines starting with `:` are comments / heartbeats.
    assert _parse_sse_chunk(":heartbeat") is None
    assert _parse_sse_chunk("") is None


def test_parse_sse_chunk_field_without_colon() -> None:
    # "data" alone is treated as data field with empty value.
    msg = _parse_sse_chunk("data")
    assert msg is not None
    assert msg.raw == ""


def test_parse_sse_chunk_space_after_colon_stripped() -> None:
    # Per SSE spec, exactly one leading space is stripped.
    msg1 = _parse_sse_chunk("data: hello")
    msg2 = _parse_sse_chunk("data:hello")
    assert msg1 is not None and msg2 is not None
    assert msg1.data == msg2.data == "hello"


def test_parse_sse_chunk_ignores_retry_field() -> None:
    msg = _parse_sse_chunk("retry: 5000\ndata: hi")
    assert msg is not None
    assert msg.data == "hi"
