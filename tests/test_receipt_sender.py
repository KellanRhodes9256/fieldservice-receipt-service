import pytest

from fieldservice_receipts.receipt_sender import (
    ReceiptNotReady,
    WorkOrderReceipt,
    build_receipt_email,
)


def order(**changes: object) -> WorkOrderReceipt:
    values: dict[str, object] = {
        "work_order_id": "WO-88",
        "customer_email": "customer@example.com",
        "customer_name": "Avery",
        "dispatch_status": "completed",
        "payment_status": "captured",
        "total_cents": 12550,
    }
    values.update(changes)
    return WorkOrderReceipt.model_validate(values)


def test_completed_paid_work_order_becomes_receipt_request() -> None:
    payload = build_receipt_email(order())

    assert payload == {
        "to": "customer@example.com",
        "subject": "Receipt for work order WO-88",
        "html": (
            "<h1>Receipt for work order WO-88</h1>"
            "<p>Hello Avery, your dispatched work is complete.</p>"
            "<p><strong>Total paid:</strong> 125.50 USD</p>"
        ),
    }


@pytest.mark.parametrize(
    ("dispatch_status", "payment_status"),
    [("en_route", "captured"), ("completed", "pending")],
)
def test_receipt_waits_for_completed_and_paid_work(
    dispatch_status: str, payment_status: str
) -> None:
    with pytest.raises(ReceiptNotReady):
        build_receipt_email(
            order(dispatch_status=dispatch_status, payment_status=payment_status)
        )
