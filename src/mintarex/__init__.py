"""Mintarex — Official Python SDK for the Mintarex Corporate OTC API.

Quick start::

    from mintarex import Mintarex
    mx = Mintarex(api_key="mxn_test_...", api_secret="...")
    quote = mx.rfq.quote({
        "base": "BTC", "quote": "USD", "side": "buy",
        "amount": "0.5", "amount_type": "base",
    })
"""

from __future__ import annotations

from .client import MintarexClient
from .errors import (
    AuthenticationError,
    ConfigurationError,
    ConflictError,
    InsufficientBalanceError,
    MintarexAPIError,
    MintarexError,
    NetworkError,
    NotFoundError,
    QuoteExpiredError,
    RateLimitError,
    RateLimitInfo,
    ServerError,
    ServiceUnavailableError,
    ValidationError,
    WebhookSignatureError,
    error_from_response,
)
from .errors import (
    PermissionError_ as PermissionError,
)
from .mintarex import Mintarex
from .signing import (
    EMPTY_BODY_SHA256,
    build_canonical_string,
    hmac_sign,
    sha256_hex,
    sign,
)
from .streams import Stream, StreamMessage, StreamsResource
from .types import (
    AmountType,
    Balance,
    BalancesResponse,
    CryptoDeposit,
    CryptoDepositStatus,
    CryptoWithdrawal,
    CryptoWithdrawalStatus,
    CurrencyType,
    DepositAddress,
    Environment,
    Instrument,
    LimitBucket,
    LimitsBuckets,
    LimitsResponse,
    Network,
    PaginatedResponse,
    Pagination,
    PublicFees,
    PublicFeeTier,
    Quote,
    QuoteRequest,
    ResponseMeta,
    Side,
    SingleBalanceResponse,
    StreamToken,
    Trade,
    TradeExecution,
    TradeStatus,
    WalletTypeBalance,
    Webhook,
    WebhookCreateResponse,
    WebhookEvent,
    WithdrawalAddress,
)
from .webhooks import DEFAULT_TOLERANCE_SECONDS, verify_webhook

__version__ = "0.0.3"

__all__ = [
    # Core
    "DEFAULT_TOLERANCE_SECONDS",
    "EMPTY_BODY_SHA256",
    # Types (TypedDicts / Literals)
    "AmountType",
    # Errors
    "AuthenticationError",
    "Balance",
    "BalancesResponse",
    "ConfigurationError",
    "ConflictError",
    "CryptoDeposit",
    "CryptoDepositStatus",
    "CryptoWithdrawal",
    "CryptoWithdrawalStatus",
    "CurrencyType",
    "DepositAddress",
    "Environment",
    "Instrument",
    "InsufficientBalanceError",
    "LimitBucket",
    "LimitsBuckets",
    "LimitsResponse",
    "Mintarex",
    "MintarexAPIError",
    "MintarexClient",
    "MintarexError",
    "Network",
    "NetworkError",
    "NotFoundError",
    "PaginatedResponse",
    "Pagination",
    "PermissionError",
    "PublicFeeTier",
    "PublicFees",
    "Quote",
    "QuoteExpiredError",
    "QuoteRequest",
    "RateLimitError",
    "RateLimitInfo",
    "ResponseMeta",
    "ServerError",
    "ServiceUnavailableError",
    "Side",
    "SingleBalanceResponse",
    # Streaming
    "Stream",
    "StreamMessage",
    "StreamToken",
    "StreamsResource",
    "Trade",
    "TradeExecution",
    "TradeStatus",
    "ValidationError",
    "WalletTypeBalance",
    "Webhook",
    "WebhookCreateResponse",
    "WebhookEvent",
    "WebhookSignatureError",
    "WithdrawalAddress",
    "__version__",
    # Signing + verification
    "build_canonical_string",
    "error_from_response",
    "hmac_sign",
    "sha256_hex",
    "sign",
    "verify_webhook",
]
