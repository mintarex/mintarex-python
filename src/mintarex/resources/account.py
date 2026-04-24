"""``/account/*`` resource — balances, limits."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal
from urllib.parse import quote as urlquote

from ..validate import assert_coin, assert_fiat_currency

if TYPE_CHECKING:
    from ..client import MintarexClient

_FIAT_RE = re.compile(r"^[A-Z]{3,10}$")


class AccountResource:
    """Account-level data: balances, limits."""

    def __init__(self, client: MintarexClient) -> None:
        self._client = client

    def balances(
        self,
        *,
        currency_type: Literal["fiat", "crypto"] | None = None,
        include_empty: bool | None = None,
    ) -> dict[str, object]:
        """List balances across all currencies the account holds."""
        query: dict[str, str | int | bool | None] = {}
        if currency_type is not None:
            query["currency_type"] = currency_type
        if include_empty is not None:
            query["include_empty"] = include_empty
        return self._client.request(method="GET", path="/account/balances", query=query)

    def balance(self, currency: str) -> dict[str, object]:
        """Return aggregated balance for a single currency (fiat or crypto)."""
        c = (
            assert_fiat_currency(currency)
            if _FIAT_RE.match(currency or "")
            else assert_coin(currency)
        )
        return self._client.request(
            method="GET",
            path=f"/account/balance/{urlquote(c, safe='')}",
        )

    def limits(self) -> dict[str, object]:
        """Return daily/monthly deposit + withdrawal limits for this account."""
        return self._client.request(method="GET", path="/account/limits")
