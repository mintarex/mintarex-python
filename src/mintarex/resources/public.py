"""``/instruments``, ``/networks``, ``/fees`` — public (unsigned GET accepted but we sign)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..validate import assert_coin

if TYPE_CHECKING:
    from ..client import MintarexClient


class PublicResource:
    """Public reference data: tradable instruments, supported networks, fee tiers."""

    def __init__(self, client: MintarexClient) -> None:
        self._client = client

    def instruments(self) -> dict[str, object]:
        """List all tradable instruments."""
        return self._client.request(method="GET", path="/instruments")

    def networks(self, *, coin: str | None = None) -> dict[str, object]:
        """List supported networks, optionally filtered to a single coin."""
        query: dict[str, str | int | bool | None] = {}
        if coin is not None:
            query["coin"] = assert_coin(coin, "coin")
        return self._client.request(method="GET", path="/networks", query=query)

    def fees(self) -> dict[str, object]:
        """Return the public fee schedule (not account-specific)."""
        return self._client.request(method="GET", path="/fees")
