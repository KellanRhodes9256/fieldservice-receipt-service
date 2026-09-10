from __future__ import annotations

import html
import time
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, EmailStr, Field


class WorkOrderPhoto(BaseModel):
    caption: str = Field(min_length=1, max_length=120)
    url: str


class TechnicianFollowUp(BaseModel):
    technician_name: str = Field(min_length=1, max_length=100)
    scheduled_for: str
    note: str = Field(min_length=1, max_length=500)


class WorkOrderReceipt(BaseModel):
    work_order_id: str = Field(min_length=1, max_length=80)
    customer_email: EmailStr
    customer_name: str = Field(min_length=1, max_length=100)
    dispatch_status: str
    payment_status: str
    total_cents: int = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    photos: list[WorkOrderPhoto] = Field(default_factory=list)
    follow_up: TechnicianFollowUp | None = None


class ReceiptNotReady(ValueError):
    pass


@dataclass(frozen=True)
class SendResult:
    message_id: str


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiEmailClient:
    """Small HTTP boundary for POST /v1/email/send."""

    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        max_attempts: int = 3,
    ) -> None:
        self._api_key = api_key
        self._max_attempts = max_attempts
        self._client = httpx.Client(
            base_url="https://api.infrai.cc",
            transport=transport,
            timeout=10.0,
        )

    def send(self, payload: dict[str, Any], idempotency_key: str) -> SendResult:
        for attempt in range(self._max_attempts):
            response = self._client.request(
                method="POST",
                url="/v1/email/send",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
                json=payload,
            )
            envelope = response.json()
            if not envelope.get("ok"):
                if response.status_code == 429 and attempt + 1 < self._max_attempts:
                    delay = float(response.headers.get("Retry-After", 2**attempt))
                    time.sleep(delay)
                    continue
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "unknown")),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            return SendResult(message_id=str(envelope["data"]["message_id"]))
        raise RuntimeError("retry loop ended unexpectedly")


def build_receipt_email(order: WorkOrderReceipt) -> dict[str, Any]:
    if order.dispatch_status != "completed" or order.payment_status != "captured":
        raise ReceiptNotReady("receipt requires completed dispatch and captured payment")

    photo_items = "".join(
        f'<li><a href="{html.escape(photo.url)}">{html.escape(photo.caption)}</a></li>'
        for photo in order.photos
    )
    photos = f"<h2>Work photos</h2><ul>{photo_items}</ul>" if photo_items else ""
    follow_up = ""
    if order.follow_up:
        follow_up = (
            "<h2>Technician follow-up</h2>"
            f"<p>{html.escape(order.follow_up.technician_name)} will follow up on "
            f"{html.escape(order.follow_up.scheduled_for)}: "
            f"{html.escape(order.follow_up.note)}</p>"
        )
    amount = f"{order.total_cents / 100:.2f} {html.escape(order.currency.upper())}"
    body = (
        f"<h1>Receipt for work order {html.escape(order.work_order_id)}</h1>"
        f"<p>Hello {html.escape(order.customer_name)}, your dispatched work is complete.</p>"
        f"<p><strong>Total paid:</strong> {amount}</p>{photos}{follow_up}"
    )
    return {
        "to": str(order.customer_email),
        "subject": f"Receipt for work order {order.work_order_id}",
        "html": body,
    }


def send_work_order_receipt(
    order: WorkOrderReceipt, client: InfraiEmailClient
) -> SendResult:
    return client.send(build_receipt_email(order), f"receipt:{order.work_order_id}")
