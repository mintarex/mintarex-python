"""Server-Sent Events streaming client.

Blocking iteration over live price or account events::

    with mx.streams.prices() as stream:
        for msg in stream:
            print(msg.event, msg.data)

The stream reconnects automatically on transient errors. A watchdog fires
if no heartbeat or data arrives within 2x the heartbeat interval, forcing
a reconnect.
"""

from __future__ import annotations

import contextlib
import json
import random
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import httpx

from .errors import NetworkError

if TYPE_CHECKING:
    from .client import MintarexClient


@dataclass
class StreamMessage:
    """One parsed SSE event."""

    event: str
    data: Any
    id: str | None
    raw: str


class Stream:
    """Long-running SSE stream.

    Iterate with ``for msg in stream:`` or use ``with`` as a context manager
    to guarantee connection cleanup on exit.
    """

    def __init__(
        self,
        client: MintarexClient,
        endpoint: Literal["prices", "account"],
        *,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int | None = None,
        max_reconnect_delay_s: float = 30.0,
        heartbeat_interval_s: float = 15.0,
    ) -> None:
        if not (heartbeat_interval_s >= 1.0):
            raise ValueError("heartbeat_interval_s must be ≥ 1.0")
        if max_reconnect_delay_s < 0:
            raise ValueError("max_reconnect_delay_s must be ≥ 0")
        self._client = client
        self._endpoint = endpoint
        self._auto_reconnect = auto_reconnect
        self._max_reconnect_attempts = max_reconnect_attempts
        self._max_reconnect_delay_s = max_reconnect_delay_s
        self._heartbeat_interval_s = heartbeat_interval_s
        self._closed = False
        self._reconnect_attempts = 0
        self._response: httpx.Response | None = None
        self._watchdog_deadline: float = 0.0
        self._lock = threading.Lock()

    # ----------------------------------------------------- context manager
    def __enter__(self) -> Stream:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Terminate the stream and release the HTTP connection."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            resp = self._response
            self._response = None
        if resp is not None:
            # Best-effort close — connection may already be torn down.
            with contextlib.suppress(Exception):
                resp.close()

    # ------------------------------------------------------------ iterator
    def __iter__(self) -> Iterator[StreamMessage]:
        while not self._closed:
            try:
                yield from self._open_once()
                if not self._auto_reconnect or self._closed:
                    return
            except NetworkError:
                if self._closed or not self._auto_reconnect:
                    raise
            except httpx.HTTPError as err:
                if self._closed or not self._auto_reconnect:
                    raise NetworkError(str(err) or "Stream HTTP error") from err

            if (
                self._max_reconnect_attempts is not None
                and self._reconnect_attempts >= self._max_reconnect_attempts
            ):
                raise NetworkError(
                    f"Stream reconnect limit reached ({self._max_reconnect_attempts})"
                )
            self._reconnect_attempts += 1
            delay = min(
                0.5 * (2 ** (self._reconnect_attempts - 1)) + random.random() * 0.5,  # noqa: S311
                self._max_reconnect_delay_s,
            )
            time.sleep(delay)

    # ------------------------------------------------------------ internals
    def _fetch_token(self) -> str:
        token_response = self._client.request(method="POST", path="/stream/token", body={})
        token = token_response.get("token")
        if not isinstance(token, str) or not token:
            raise NetworkError("Stream token response missing token field")
        return token

    def _open_once(self) -> Iterator[StreamMessage]:
        token = self._fetch_token()
        url = self._client.stream_base_url.copy_with(
            path=self._client.stream_base_url.path.rstrip("/") + "/" + self._endpoint
        )
        url = url.copy_merge_params([("token", token)])

        headers = {"Accept": "text/event-stream"}
        http = self._client.http_client

        # Open with an explicit read timeout = 2x heartbeat; once connected
        # we rely on the watchdog in _iter_sse for liveness, and httpx will
        # raise ReadTimeout if the upstream goes silent.
        timeout = httpx.Timeout(
            connect=self._heartbeat_interval_s * 2,
            read=self._heartbeat_interval_s * 2,
            write=5.0,
            pool=5.0,
        )
        try:
            with http.stream(
                "GET",
                url,
                headers=headers,
                timeout=timeout,
            ) as response:
                with self._lock:
                    if self._closed:
                        return
                    self._response = response

                try:
                    if response.status_code != 200:
                        raise NetworkError(f"Stream open failed: HTTP {response.status_code}")
                    content_type = response.headers.get("content-type", "")
                    if "text/event-stream" not in content_type:
                        raise NetworkError(f"Unexpected content-type: {content_type}")

                    self._reconnect_attempts = 0
                    self._arm_watchdog()
                    yield from self._iter_sse(response)
                finally:
                    with self._lock:
                        self._response = None
        except httpx.TimeoutException as err:
            raise NetworkError(
                f"No data for {int(self._heartbeat_interval_s * 2)}s; forcing reconnect"
            ) from err

    def _iter_sse(self, response: httpx.Response) -> Iterator[StreamMessage]:
        buffer = ""
        for chunk in response.iter_text():
            if self._closed:
                return
            self._arm_watchdog()
            buffer += chunk
            while True:
                idx = _find_event_boundary(buffer)
                if idx < 0:
                    break
                event_chunk = buffer[:idx]
                # Strip whichever terminator matched (\n\n, \r\n\r\n, \r\r).
                rest = buffer[idx:]
                for term in ("\r\n\r\n", "\n\n", "\r\r"):
                    if rest.startswith(term):
                        rest = rest[len(term) :]
                        break
                buffer = rest
                msg = _parse_sse_chunk(event_chunk)
                if msg is not None:
                    yield msg

    def _arm_watchdog(self) -> None:
        self._watchdog_deadline = time.monotonic() + self._heartbeat_interval_s * 2


def _find_event_boundary(s: str) -> int:
    candidates = [s.find("\n\n"), s.find("\r\n\r\n"), s.find("\r\r")]
    valid = [i for i in candidates if i >= 0]
    if not valid:
        return -1
    return min(valid)


def _parse_sse_chunk(chunk: str) -> StreamMessage | None:
    lines = chunk.splitlines()
    event_name = "message"
    data_lines: list[str] = []
    msg_id: str | None = None
    has_data = False

    for line in lines:
        if not line or line.startswith(":"):
            continue  # empty line or comment (heartbeat)
        colon = line.find(":")
        if colon == -1:
            field, value = line, ""
        else:
            field = line[:colon]
            value = line[colon + 1 :]
            if value.startswith(" "):
                value = value[1:]
        if field == "event":
            event_name = value or "message"
        elif field == "data":
            data_lines.append(value)
            has_data = True
        elif field == "id":
            msg_id = value
        # "retry" is advisory; SDK uses its own backoff.

    if not has_data:
        return None
    raw = "\n".join(data_lines)
    parsed: Any = raw
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
    return StreamMessage(event=event_name, data=parsed, id=msg_id, raw=raw)


class StreamsResource:
    """Factory for :class:`Stream` instances."""

    def __init__(self, client: MintarexClient) -> None:
        self._client = client

    def prices(self, **kwargs: Any) -> Stream:
        """Open the price-update stream."""
        return Stream(self._client, "prices", **kwargs)

    def account(self, **kwargs: Any) -> Stream:
        """Open the account-event stream."""
        return Stream(self._client, "account", **kwargs)
