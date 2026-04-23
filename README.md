# mintarex

Official Python SDK for the **Mintarex Corporate OTC API**.

- API docs: <https://developers.mintarex.com>
- Issues / support: <https://github.com/mintarex/mintarex-python/issues>

## Install

```bash
pip install mintarex
# or
uv add mintarex
```

Python 3.11+ required.

## Quick start

```python
import os

from mintarex import Mintarex

mx = Mintarex(
    api_key=os.environ["MX_KEY"],      # mxn_live_... or mxn_test_...
    api_secret=os.environ["MX_SECRET"],
)

# Account
balances = mx.account.balances()
print(balances["balances"])

# Request a quote
quote = mx.rfq.quote({
    "base": "BTC",
    "quote": "USD",
    "side": "buy",
    "amount": "0.5",
    "amount_type": "base",
})
print("quote_id:", quote["quote_id"], "price:", quote["price"])

# Accept — idempotency_key auto-generated if omitted
trade = mx.rfq.accept(quote["quote_id"])
print("filled:", trade)
```

## Features

| Area | Support |
|------|---------|
| HMAC-SHA256 request signing | Built-in, auto-generated nonces + timestamps |
| Typed errors | 13 exception classes mapping HTTP status + API error codes |
| Automatic retries | 429 / 503 / network errors (with Retry-After honored) |
| Rate-limit headers | IETF RFC 9331 `RateLimit-*` (legacy `X-RateLimit-*` fallback) |
| SSE streaming | `mx.streams.prices()` / `mx.streams.account()` with auto-reconnect + watchdog |
| Webhook verification | Constant-time HMAC check + timestamp tolerance |
| Environments | `live` or `sandbox` (inferred from key prefix) |
| Type hints | Full `py.typed`, mypy-strict clean |

## Environments

The environment is inferred from the key prefix:

| Key prefix | Environment |
|-----------|-------------|
| `mxn_live_...` | `live` |
| `mxn_test_...` | `sandbox` |

You can also set it explicitly:

```python
mx = Mintarex(api_key=..., api_secret=..., environment="sandbox")
```

## Error handling

All SDK errors inherit from `MintarexError`.

```python
from mintarex import (
    InsufficientBalanceError,
    QuoteExpiredError,
    RateLimitError,
    ValidationError,
)

try:
    trade = mx.rfq.accept(quote_id)
except QuoteExpiredError:
    quote = mx.rfq.quote({...})  # re-quote
    trade = mx.rfq.accept(quote["quote_id"])
except InsufficientBalanceError as e:
    print("top up:", e.message)
except RateLimitError as e:
    print("retry after ms:", e.retry_after, "remaining:", e.rate_limit.remaining)
except ValidationError as e:
    print("bad input:", e.message)
```

## Streaming (SSE)

```python
with mx.streams.prices() as stream:
    for msg in stream:
        print(msg.event, msg.data)
```

Reconnect on transient errors is automatic; a watchdog fires if no data
arrives within 2× the heartbeat interval. Call `stream.close()` to stop.

## Webhook verification

```python
from flask import Flask, request
from mintarex import verify_webhook, WebhookSignatureError

app = Flask(__name__)

@app.post("/hook")
def hook():
    try:
        event = verify_webhook(
            body=request.get_data(),      # exact raw bytes, NOT parsed JSON
            headers=dict(request.headers),
            secret=os.environ["MINTAREX_WEBHOOK_SECRET"],
        )
    except WebhookSignatureError:
        return "", 400

    if event["event_type"] == "trade.executed":
        handle_trade(event["data"])
    return "", 204
```

## Configuration

```python
mx = Mintarex(
    api_key=...,
    api_secret=...,
    environment="sandbox",          # optional — inferred from key prefix
    base_url="https://institutional.mintarex.com/v1",   # optional override
    stream_base_url="https://institutional.mintarex.com/v1/stream",
    timeout=30.0,                   # per-request timeout (seconds)
    max_retries=3,                  # for 429/503 and network errors
    user_agent="my-app/1.0",        # appended to the default UA
)
```

`http://` URLs are permitted only for `localhost` / `127.0.0.1` / `::1`
(dev and test scenarios). Public hosts must use HTTPS.

## Resources

| Namespace | Methods |
|-----------|---------|
| `mx.account` | `balances()`, `balance(currency)`, `fees()`, `limits()` |
| `mx.rfq` | `quote(...)`, `accept(quote_id, idempotency_key=...)` |
| `mx.trades` | `list(...)`, `get(trade_uuid)` |
| `mx.crypto` | `deposit_address(...)`, `deposits(...)`, `withdraw(...)`, `withdrawals(...)`, `get_withdrawal(...)`, `addresses.list/add/remove` |
| `mx.webhooks` | `create(...)`, `list()`, `remove(endpoint_uuid)` |
| `mx.streams` | `prices()`, `account()` |
| `mx.public` | `instruments()`, `networks(...)`, `fees()` |

## License

MIT
