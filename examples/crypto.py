"""Crypto deposits + withdrawals."""

from __future__ import annotations

import os

from mintarex import Mintarex


def main() -> None:
    mx = Mintarex(
        api_key=os.environ["MX_KEY"],
        api_secret=os.environ["MX_SECRET"],
    )

    # Get a BTC deposit address
    addr = mx.crypto.deposit_address(coin="BTC", network="btc")
    print(f"deposit to: {addr['address']} (min {addr['min_deposit']})")

    # List recent deposits
    deposits = mx.crypto.deposits({"coin": "BTC", "limit": 10})
    print(f"recent deposits: {len(deposits.get('data', []))}")

    # Submit a withdrawal — idempotency_key auto-generated
    # (address must be on the whitelist; this example will fail without one)
    # withdrawal = mx.crypto.withdraw({
    #     "coin": "BTC",
    #     "network": "btc",
    #     "amount": "0.0001",
    #     "address": "bc1qxxx...",
    # })
    # print("withdrawal:", withdrawal["withdrawal_id"], withdrawal["status"])


if __name__ == "__main__":
    main()
