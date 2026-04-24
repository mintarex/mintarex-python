"""Public types surfaced by the SDK.

Response shapes are modeled as :class:`typing.TypedDict` so they remain
transparently usable as plain ``dict`` instances (matching how the JSON
deserializes) while still giving IDEs and type checkers full introspection.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from .errors import RateLimitInfo

Environment = Literal["live", "sandbox"]
Side = Literal["buy", "sell"]
AmountType = Literal["base", "quote"]
CurrencyType = Literal["fiat", "crypto"]


class Pagination(TypedDict):
    total: int
    limit: int
    offset: int
    has_more: bool


class PaginatedResponse(TypedDict):
    data: list[dict[str, object]]
    pagination: Pagination


class Balance(TypedDict, total=False):
    currency: str
    currency_type: CurrencyType
    available: str
    locked: str
    pending_in: str
    pending_out: str
    total: str
    usd_value: str | None
    usd_price: str | None


class BalancesResponse(TypedDict):
    balances: list[Balance]
    timestamp: str


class WalletTypeBalance(TypedDict):
    wallet_type: str
    available: str
    locked: str
    pending_in: str
    pending_out: str


class SingleBalanceResponse(TypedDict):
    currency: str
    currency_type: CurrencyType
    total_available: str
    total_locked: str
    total_pending_in: str
    total_pending_out: str
    total: str
    by_wallet_type: list[WalletTypeBalance]
    timestamp: str


class LimitBucket(TypedDict):
    daily_limit: str | None
    daily_used: str | None
    monthly_limit: str | None
    monthly_used: str | None
    remaining_daily: str | None
    remaining_monthly: str | None


class LimitsBuckets(TypedDict):
    crypto_deposit: LimitBucket | None
    crypto_withdrawal: LimitBucket | None


class LimitsResponse(TypedDict):
    account_type: Literal["individual", "corporate"]
    limits: LimitsBuckets
    timestamp: str


class Quote(TypedDict):
    quote_id: str
    base: str
    quote: str
    side: Side
    network: str
    price: str
    base_amount: str
    quote_amount: str
    expires_at: str
    expires_in_ms: int


class QuoteRequest(TypedDict, total=False):
    base: str
    quote: str
    side: Side
    amount: str
    amount_type: AmountType
    network: str
    from_network: str
    to_network: str


TradeStatus = Literal["filled", "pending", "cancelled", "failed", "expired"]


class TradeExecution(TypedDict, total=False):
    trade_id: str
    status: TradeStatus
    base: str
    quote: str
    side: Side
    network: str
    price: str
    base_amount: str
    quote_amount: str
    filled_at: str
    is_swap: bool
    from_network: str
    to_network: str
    sandbox: bool
    idempotent: bool


class Trade(TypedDict, total=False):
    trade_id: str
    base: str
    quote: str
    side: Side
    status: TradeStatus
    price: str
    base_amount: str
    quote_amount: str
    fee_amount: str
    fee_currency: str
    order_type: str
    created_at: str
    updated_at: str
    sandbox: bool


class DepositAddress(TypedDict):
    address: str
    coin: str
    network: str
    memo_required: bool
    min_deposit: str
    required_confirmations: int
    timestamp: str


CryptoDepositStatus = Literal[
    "detected",
    "pending_confirmations",
    "confirming",
    "crediting",
    "completed",
    "failed",
]


class CryptoDeposit(TypedDict, total=False):
    deposit_id: str
    coin: str
    network: str
    amount: str
    tx_hash: str
    from_address: str | None
    confirmations: int
    required_confirmations: int
    status: CryptoDepositStatus
    detected_at: str
    updated_at: str
    sandbox: bool


CryptoWithdrawalStatus = Literal[
    "pending_review",
    "approved",
    "processing",
    "broadcasting",
    "completed",
    "rejected",
    "failed",
    "cancelled",
]


class CryptoWithdrawal(TypedDict, total=False):
    withdrawal_id: str
    reference: str | None
    coin: str
    network: str
    amount: str
    fee: str
    total_deducted: str
    amount_usd: str | None
    to_address: str
    memo: str | None
    tx_hash: str | None
    explorer_url: str | None
    status: CryptoWithdrawalStatus
    reject_reason: str | None
    reviewed_at: str | None
    broadcast_at: str | None
    completed_at: str | None
    created_at: str
    updated_at: str
    idempotent: bool
    message: str
    sandbox: bool


class WithdrawalAddress(TypedDict, total=False):
    address_uuid: str
    currency: str
    network: str
    address: str
    address_tag: str | None
    label: str
    status: Literal["pending", "active", "disabled", "revoked"]
    cooling_until: str | None
    is_usable: bool
    withdrawal_count: int
    total_withdrawn_amount: str
    last_withdrawal_at: str | None
    created_at: str


class Webhook(TypedDict):
    endpoint_uuid: str
    url: str
    label: str
    events: list[str]
    status: Literal["active", "disabled"]
    disabled_reason: str | None
    created_at: str


class WebhookCreateResponse(TypedDict, total=False):
    endpoint_uuid: str
    status: Literal["active", "pending_confirmation"]
    signing_secret: str
    confirmation_id: str
    message: str


class StreamToken(TypedDict):
    token: str
    expires_in: int


class Instrument(TypedDict):
    instrument: str
    base: str
    quote: str
    base_name: str
    type: Literal["crypto_fiat", "crypto_crypto"]


class Network(TypedDict):
    coin: str
    network: str
    name: str
    contract_address: str | None
    decimals: int
    min_deposit: str
    min_withdrawal: str
    withdrawal_fee: str
    required_confirmations: int
    deposit_enabled: bool
    withdrawal_enabled: bool


class PublicFeeTier(TypedDict, total=False):
    individual: str
    corporate: str
    note: str


class PublicFees(TypedDict, total=False):
    trading: PublicFeeTier
    fiat_withdrawal: PublicFeeTier
    crypto_withdrawal: dict[str, str]
    timestamp: str


class ResponseMeta(TypedDict):
    request_id: str | None
    rate_limit: RateLimitInfo
    status: int


class WebhookEvent(TypedDict):
    event_type: str
    event_id: str
    delivery_uuid: str
    timestamp: str
    sandbox: bool
    data: dict[str, object]
