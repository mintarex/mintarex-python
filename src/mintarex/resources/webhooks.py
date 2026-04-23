"""``/webhooks`` resource — webhook endpoint CRUD."""

from __future__ import annotations

from typing import TYPE_CHECKING, NotRequired, TypedDict
from urllib.parse import quote as urlquote

from ..validate import assert_events, assert_https_url, assert_label, assert_uuid

if TYPE_CHECKING:
    from ..client import MintarexClient


class WebhookCreateRequest(TypedDict):
    url: str
    events: list[str]
    label: NotRequired[str]


class WebhooksResource:
    """Webhook endpoint management."""

    def __init__(self, client: MintarexClient) -> None:
        self._client = client

    def create(self, input: WebhookCreateRequest) -> dict[str, object]:
        """Register a new webhook endpoint."""
        body: dict[str, object] = {
            "url": assert_https_url(input["url"], "url"),
            "events": assert_events(input["events"], "events"),
        }
        if "label" in input:
            body["label"] = assert_label(input["label"], "label")
        return self._client.request(method="POST", path="/webhooks", body=body)

    def list(self) -> dict[str, object]:
        """List registered webhook endpoints."""
        return self._client.request(method="GET", path="/webhooks")

    def remove(self, endpoint_uuid: str) -> dict[str, object]:
        """Delete a webhook endpoint (may require email confirmation)."""
        eid = assert_uuid(endpoint_uuid, "endpoint_uuid")
        return self._client.request(
            method="DELETE",
            path=f"/webhooks/{urlquote(eid, safe='')}",
        )
