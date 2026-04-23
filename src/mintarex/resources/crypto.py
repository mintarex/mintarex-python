"""``/crypto/*`` resource — deposits, withdrawals, withdrawal-address book."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, NotRequired, TypedDict
from urllib.parse import quote as urlquote

from ..validate import (
    assert_address,
    assert_address_tag,
    assert_amount,
    assert_coin,
    assert_idempotency_key,
    assert_label,
    assert_network,
    assert_uuid,
)

if TYPE_CHECKING:
    from ..client import MintarexClient


class DepositListParams(TypedDict, total=False):
    coin: str
    status: str
    from_: str
    to: str
    limit: int
    offset: int


class WithdrawalListParams(TypedDict, total=False):
    coin: str
    status: str
    from_: str
    to: str
    limit: int
    offset: int


class WithdrawRequest(TypedDict):
    coin: str
    network: str
    amount: str
    address: str
    address_tag: NotRequired[str]
    idempotency_key: NotRequired[str]


class AddressAddRequest(TypedDict):
    currency: str
    network: str
    address: str
    label: str
    address_tag: NotRequired[str]


class AddressListParams(TypedDict, total=False):
    currency: str
    network: str
    status: str
    limit: int
    offset: int


class WithdrawalAddressesSubresource:
    """Withdrawal-address book."""

    def __init__(self, client: MintarexClient) -> None:
        self._client = client

    def list(self, params: AddressListParams | None = None) -> dict[str, object]:
        """List withdrawal addresses on file."""
        query: dict[str, str | int | bool | None] = {}
        p = params or {}
        if "currency" in p:
            query["currency"] = assert_coin(p["currency"], "currency")
        if "network" in p:
            query["network"] = assert_network(p["network"], "network")
        if "status" in p:
            query["status"] = p["status"]
        if "limit" in p:
            query["limit"] = _clamp_int(p["limit"], 1, 200)
        if "offset" in p:
            query["offset"] = _clamp_int(p["offset"], 0, 2_000_000)
        return self._client.request(
            method="GET",
            path="/crypto/withdrawal-addresses",
            query=query,
        )

    def add(self, input: AddressAddRequest) -> dict[str, object]:
        """Add a withdrawal address (requires email confirmation)."""
        body: dict[str, object] = {
            "currency": assert_coin(input["currency"], "currency"),
            "network": assert_network(input["network"], "network"),
            "address": assert_address(input["address"], "address"),
            "label": assert_label(input["label"], "label"),
        }
        if "address_tag" in input:
            body["address_tag"] = assert_address_tag(input["address_tag"])
        return self._client.request(
            method="POST",
            path="/crypto/withdrawal-addresses",
            body=body,
        )

    def remove(self, address_uuid: str) -> dict[str, object]:
        """Revoke a withdrawal address by UUID."""
        aid = assert_uuid(address_uuid, "address_uuid")
        return self._client.request(
            method="DELETE",
            path=f"/crypto/withdrawal-addresses/{urlquote(aid, safe='')}",
        )


class CryptoResource:
    """Deposit, withdraw, and address-book endpoints."""

    def __init__(self, client: MintarexClient) -> None:
        self._client = client
        self.addresses = WithdrawalAddressesSubresource(client)

    def deposit_address(
        self,
        *,
        coin: str,
        network: str | None = None,
    ) -> dict[str, object]:
        """Get a deposit address for the given coin (optionally on a specific network)."""
        query: dict[str, str | int | bool | None] = {"coin": assert_coin(coin, "coin")}
        if network is not None:
            query["network"] = assert_network(network, "network")
        return self._client.request(
            method="GET",
            path="/crypto/deposit-address",
            query=query,
        )

    def deposits(self, params: DepositListParams | None = None) -> dict[str, object]:
        """List detected / confirmed crypto deposits."""
        query: dict[str, str | int | bool | None] = {}
        p = params or {}
        if "coin" in p:
            query["coin"] = assert_coin(p["coin"], "coin")
        if "status" in p:
            query["status"] = p["status"]
        if "from_" in p:
            query["from"] = str(p["from_"])
        if "to" in p:
            query["to"] = str(p["to"])
        if "limit" in p:
            query["limit"] = _clamp_int(p["limit"], 1, 200)
        if "offset" in p:
            query["offset"] = _clamp_int(p["offset"], 0, 2_000_000)
        return self._client.request(method="GET", path="/crypto/deposits", query=query)

    def withdraw(self, input: WithdrawRequest) -> dict[str, object]:
        """Submit a crypto withdrawal.

        The destination address must be on the whitelist. ``idempotency_key``
        is auto-generated if omitted so network retries are safe.
        """
        body: dict[str, object] = {
            "coin": assert_coin(input["coin"], "coin"),
            "network": assert_network(input["network"], "network"),
            "amount": assert_amount(input["amount"], "amount"),
            "address": assert_address(input["address"], "address"),
            "idempotency_key": (
                assert_idempotency_key(input["idempotency_key"])
                if "idempotency_key" in input
                else str(uuid.uuid4())
            ),
        }
        if "address_tag" in input:
            body["address_tag"] = assert_address_tag(input["address_tag"])
        return self._client.request(method="POST", path="/crypto/withdraw", body=body)

    def withdrawals(self, params: WithdrawalListParams | None = None) -> dict[str, object]:
        """List crypto withdrawals."""
        query: dict[str, str | int | bool | None] = {}
        p = params or {}
        if "coin" in p:
            query["coin"] = assert_coin(p["coin"], "coin")
        if "status" in p:
            query["status"] = p["status"]
        if "from_" in p:
            query["from"] = str(p["from_"])
        if "to" in p:
            query["to"] = str(p["to"])
        if "limit" in p:
            query["limit"] = _clamp_int(p["limit"], 1, 200)
        if "offset" in p:
            query["offset"] = _clamp_int(p["offset"], 0, 2_000_000)
        return self._client.request(method="GET", path="/crypto/withdrawals", query=query)

    def get_withdrawal(self, withdrawal_uuid: str) -> dict[str, object]:
        """Fetch a single crypto withdrawal by UUID."""
        wid = assert_uuid(withdrawal_uuid, "withdrawal_uuid")
        return self._client.request(
            method="GET",
            path=f"/crypto/withdrawals/{urlquote(wid, safe='')}",
        )


def _clamp_int(v: object, lo: int, hi: int) -> int:
    if not isinstance(v, int) or isinstance(v, bool):
        return lo
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v
