"""Request-for-quote lifecycle: quote, then accept with idempotency."""

from __future__ import annotations

import os

from mintarex import Mintarex, QuoteExpiredError


def main() -> None:
    mx = Mintarex(
        api_key=os.environ["MX_KEY"],
        api_secret=os.environ["MX_SECRET"],
    )
    quote = mx.rfq.quote(
        {
            "base": "BTC",
            "quote": "USD",
            "side": "buy",
            "amount": "0.001",
            "amount_type": "base",
        }
    )
    print(
        f"quote_id={quote['quote_id']} price={quote['price']} "
        f"expires_in_ms={quote['expires_in_ms']}"
    )

    try:
        trade = mx.rfq.accept(quote["quote_id"])
        print("filled:", trade["trade_id"], trade["status"])
    except QuoteExpiredError:
        print("quote expired before accept — re-quote and retry")


if __name__ == "__main__":
    main()
