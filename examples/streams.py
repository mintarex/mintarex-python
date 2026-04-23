"""Listen to price and account SSE streams."""

from __future__ import annotations

import os

from mintarex import Mintarex


def main() -> None:
    mx = Mintarex(
        api_key=os.environ["MX_KEY"],
        api_secret=os.environ["MX_SECRET"],
    )

    print("Listening for price updates (Ctrl-C to stop)...")
    with mx.streams.prices() as stream:
        for msg in stream:
            print(f"{msg.event}: {msg.data}")


if __name__ == "__main__":
    main()
