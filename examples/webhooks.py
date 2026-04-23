"""Verify an inbound webhook delivery.

This example uses Flask. Adapt to any framework — the key is to pass the
exact raw bytes of the request body (NOT parsed JSON) to verify_webhook.
"""

from __future__ import annotations

import os

from flask import Flask, Response, request

from mintarex import WebhookSignatureError, verify_webhook

app = Flask(__name__)

SECRET = os.environ["MINTAREX_WEBHOOK_SECRET"]


@app.post("/hook")
def hook() -> Response:
    try:
        event = verify_webhook(
            body=request.get_data(),
            headers=dict(request.headers),
            secret=SECRET,
        )
    except WebhookSignatureError as err:
        return Response(str(err), status=400)

    if event["event_type"] == "trade.executed":
        print("trade:", event["data"])
    elif event["event_type"].startswith("deposit."):
        print("deposit:", event["data"])
    elif event["event_type"].startswith("withdrawal."):
        print("withdrawal:", event["data"])

    return Response("", status=204)


if __name__ == "__main__":
    app.run(port=8000)
