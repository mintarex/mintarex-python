"""Top-level Mintarex SDK client."""

from __future__ import annotations

from typing import Any

from .client import MintarexClient
from .resources.account import AccountResource
from .resources.crypto import CryptoResource
from .resources.public import PublicResource
from .resources.rfq import RFQResource
from .resources.trades import TradesResource
from .resources.webhooks import WebhooksResource
from .streams import StreamsResource
from .types import Environment


class Mintarex:
    """Main entry point for the Mintarex SDK.

    Construct once per API key and reuse across requests. Thread-safe.

    Example
    -------
    >>> import os
    >>> from mintarex import Mintarex
    >>> mx = Mintarex(
    ...     api_key=os.environ["MX_KEY"],
    ...     api_secret=os.environ["MX_SECRET"],
    ... )
    >>> balances = mx.account.balances()  # doctest: +SKIP
    """

    def __init__(self, **options: Any) -> None:
        self.client = MintarexClient(**options)
        self.account = AccountResource(self.client)
        self.rfq = RFQResource(self.client)
        self.trades = TradesResource(self.client)
        self.crypto = CryptoResource(self.client)
        self.webhooks = WebhooksResource(self.client)
        self.streams = StreamsResource(self.client)
        self.public = PublicResource(self.client)

    @property
    def environment(self) -> Environment:
        """Alias for the current environment (``"live"`` or ``"sandbox"``)."""
        return self.client.environment

    def close(self) -> None:
        """Release the underlying HTTP pool."""
        self.client.close()

    def __enter__(self) -> Mintarex:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
