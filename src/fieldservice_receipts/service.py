from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException

from .receipt_sender import (
    InfraiEmailClient,
    InfraiError,
    ReceiptNotReady,
    WorkOrderReceipt,
    send_work_order_receipt,
)

app = FastAPI(title="Field-service receipt service")


@app.post("/receipts", status_code=202)
def create_receipt(order: WorkOrderReceipt) -> dict[str, str]:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="INFRAI_API_KEY is not configured")

    try:
        result = send_work_order_receipt(order, InfraiEmailClient(api_key))
    except ReceiptNotReady as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InfraiError as exc:
        caller_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=caller_status,
            detail={"code": exc.code, "message": exc.detail.get("message", exc.code)},
        ) from exc
    return {"message_id": result.message_id, "work_order_id": order.work_order_id}
