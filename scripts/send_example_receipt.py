from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fieldservice_receipts.receipt_sender import (
    InfraiEmailClient,
    TechnicianFollowUp,
    WorkOrderPhoto,
    WorkOrderReceipt,
    send_work_order_receipt,
)


def main() -> None:
    api_key = os.environ["INFRAI_API_KEY"]
    recipient = os.environ["RECEIPT_EMAIL_TO"]
    order = WorkOrderReceipt(
        work_order_id="WO-1042",
        customer_email=recipient,
        customer_name="Morgan Lee",
        dispatch_status="completed",
        payment_status="captured",
        total_cents=18900,
        photos=[
            WorkOrderPhoto(
                caption="Installed control panel",
                url="https://example.com/work-orders/WO-1042/panel.jpg",
            )
        ],
        follow_up=TechnicianFollowUp(
            technician_name="Casey",
            scheduled_for="2026-08-20",
            note="Confirm the new thermostat schedule.",
        ),
    )
    result = send_work_order_receipt(order, InfraiEmailClient(api_key))
    print(f"Receipt accepted with message_id={result.message_id}")


if __name__ == "__main__":
    main()
