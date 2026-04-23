"""``/rfq`` resource — request-for-quote + accept."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, NotRequired, TypedDict
from urllib.parse import quote as urlquote

from ..validate import (
    assert_amount,
    assert_amount_type,
    assert_coin,
    assert_currency_code,
    assert_idempotency_key,
    assert_network,
    assert_side,
    assert_uuid,
)

if TYPE_CHECKING:
    from ..client import MintarexClient


class QuoteInput(TypedDict):
    base: str
    quote: str
    side: str
    amount: str
    amount_type: str
    network: NotRequired[str]
    from_network: NotRequired[str]
    to_network: NotRequired[str]


class RFQResource:
    """Request-for-quote endpoints."""

    def __init__(self, client: MintarexClient) -> None:
        self._client = client

    def quote(self, input: QuoteInput) -> dict[str, object]:
        """Request a short-lived quote (30s validity).

        ``quote`` can be fiat (crypto-fiat trade) or crypto (crypto-crypto swap).
        The SDK only validates the code format; the server classifies the pair
        and rejects unsupported combinations with a specific error.
        """
        body: dict[str, object] = {
            "base": assert_coin(input["base"], "base"),
            "quote": assert_currency_code(input["quote"], "quote"),
            "side": assert_side(input["side"], "side"),
            "amount": assert_amount(input["amount"], "amount"),
            "amount_type": assert_amount_type(input["amount_type"], "amount_type"),
        }
        if "network" in input:
            body["network"] = assert_network(input["network"], "network")
        if "from_network" in input:
            body["from_network"] = assert_network(input["from_network"], "from_network")
        if "to_network" in input:
            body["to_network"] = assert_network(input["to_network"], "to_network")
        return self._client.request(method="POST", path="/rfq", body=body)

    def accept(
        self,
        quote_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, object]:
        """Accept an RFQ quote.

        ``idempotency_key`` is required by the API; if omitted, a UUIDv4 is
        generated so callers get safe retry semantics on network errors.
        """
        qid = assert_uuid(quote_id, "quote_id")
        key = (
            assert_idempotency_key(idempotency_key)
            if idempotency_key is not None
            else str(uuid.uuid4())
        )
        return self._client.request(
            method="POST",
            path=f"/rfq/{urlquote(qid, safe='')}/accept",
            body={"idempotency_key": key},
        )
