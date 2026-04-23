"""Basic account queries: balances, fees, limits."""

from __future__ import annotations

import os

from mintarex import Mintarex


def main() -> None:
    mx = Mintarex(
        api_key=os.environ["MX_KEY"],
        api_secret=os.environ["MX_SECRET"],
    )
    balances = mx.account.balances()
    print("balances:")
    for b in balances["balances"]:
        print(f"  {b['currency']}: available={b['available']} locked={b['locked']}")

    print("\nfees:", mx.account.fees())
    print("\nlimits:", mx.account.limits())


if __name__ == "__main__":
    main()
