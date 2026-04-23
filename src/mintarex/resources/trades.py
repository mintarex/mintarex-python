"""``/trades`` resource — trade history."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict
from urllib.parse import quote as urlquote

from ..validate import assert_currency_code, assert_side, assert_uuid

if TYPE_CHECKING:
    from ..client import MintarexClient


class TradeListParams(TypedDict, total=False):
    limit: int
    offset: int
    sort: Literal["asc", "desc"]
    base: str
    quote: str
    side: Literal["buy", "sell"]
    status: Literal["filled", "pending", "cancelled", "failed", "expired"]
    from_: str
    to: str


class TradesResource:
    """Trade history endpoints."""

    def __init__(self, client: MintarexClient) -> None:
        self._client = client

    def list(self, params: TradeListParams | None = None) -> dict[str, object]:
        """List historical trades."""
        query: dict[str, str | int | bool | None] = {}
        p = params or {}
        if "limit" in p:
            query["limit"] = _clamp_int(p["limit"], 1, 200)
        if "offset" in p:
            query["offset"] = _clamp_int(p["offset"], 0, 2_000_000)
        if "sort" in p:
            query["sort"] = "asc" if p["sort"] == "asc" else "desc"
        if "base" in p:
            query["base"] = assert_currency_code(p["base"], "base")
        if "quote" in p:
            query["quote"] = assert_currency_code(p["quote"], "quote")
        if "side" in p:
            query["side"] = assert_side(p["side"], "side")
        if "status" in p:
            query["status"] = p["status"]
        # `from` is a Python reserved word; accept it via `from_` and map.
        if "from_" in p:
            query["from"] = str(p["from_"])
        if "to" in p:
            query["to"] = str(p["to"])
        return self._client.request(method="GET", path="/trades", query=query)

    def get(self, trade_uuid: str) -> dict[str, object]:
        """Fetch a single trade by its UUID."""
        tid = assert_uuid(trade_uuid, "trade_uuid")
        return self._client.request(
            method="GET",
            path=f"/trades/{urlquote(tid, safe='')}",
        )


def _clamp_int(v: object, lo: int, hi: int) -> int:
    if not isinstance(v, int) or isinstance(v, bool):
        return lo
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v
