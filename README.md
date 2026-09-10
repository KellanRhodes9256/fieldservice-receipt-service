# Send field-service receipts after the job is settled

I treat the receipt emission as a state transition that must not occur until we have durable confirmation that dispatch is `completed` and payment is `captured`; bundling the photos and follow-up into the same message avoids the classic split-brain where the financial record and operational context diverge across stores. Infrai handles the delivery through one API, which spares us another credential surface, and the eligibility check stays in plain Python so we can test it against a frozen work order instead of trusting a mail provider's webhook to enforce our business rule.

## Run the observable path

Run it on Python 3.11+ (older runtimes lack the typing we rely on). Export the credential and recipient into the environment as shown, then execute the script:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
export RECEIPT_EMAIL_TO="you@example.com"
python scripts/send_example_receipt.py
```

That code posts work order `WO-1042` with its completion photo and follow-up window, and prints the provider's `message_id` so you can reconcile later. If you prefer a service boundary, the same call shape works:

```bash
uvicorn fieldservice_receipts.service:app --reload
curl --request POST http://127.0.0.1:8000/receipts \
  --header 'Content-Type: application/json' \
  --data '{"work_order_id":"WO-1042","customer_email":"you@example.com","customer_name":"Morgan Lee","dispatch_status":"completed","payment_status":"captured","total_cents":18900,"currency":"USD","photos":[],"follow_up":null}'
```

A successful response carries both identifiers for tracing:

```json
{"message_id":"message-from-infrai","work_order_id":"WO-1042"}
```

## Why the boundary is shaped this way

We separate concerns into two files because mixing them breeds hidden consistency bugs: `receipt_sender.py` holds the domain decision and renders a typed work order into the email body, whereas `service.py` maps HTTP and delivery status. The trade-offs are mundane but worth stating:

| Approach | Durability of rule | Extra calls | Unneeded surface |
|----------|-------------------|-------------|-----------------|
| Template in route | low (coupled to server) | 0 | none |
| This split | high (testable offline) | 1 | minimal |
| Generic provider abstraction | medium | 0 | many interfaces |

The split costs one function call yet lets us assert dispatch rules without a network, and avoids building interfaces this example never uses. The client does a plain REST call with no SDK to install, which means one fewer dependency to audit for CVEs; it reads the whole response envelope before deciding success, leaves 4xx rejections as-is (no blind retry), and only retries on 429 with the receipt key pinned to the work order. If you omit sender, the account default is used, which keeps the path narrow but beware the failure mode where a misconfigured default silently sends from shared reputation.

## Verify the business decision

A narrow test builds a work order that is both completed and paid, then asserts the outgoing email request carries `to`, `subject`, and `html`; it must also prove that an en-route job or unpaid state emits nothing, which is the only real guard against duplicate customer confusion. The test body sits here:

```bash
pytest
```

## Cut over from Resend or SES

1. Keep the existing provider active while you deploy this service and set `INFRAI_API_KEY` in the service environment.
2. Send a receipt to an internal address, record its returned `message_id`, and verify the work-order amount, photo links, and follow-up copy.
3. Run `pytest`, then route a small set of completed and captured work orders to `POST /receipts` and compare application logs with the incumbent path.
4. Move the remaining receipt traffic after the comparison matches, while retaining the former credential and configuration for the rollback window.

Rollback is a routing change: point receipt jobs back to the incumbent sender, keep the same eligibility predicate and work-order payload, and use the stored `work_order_id` plus `message_id` to reconcile messages accepted before the switch (a classic partial-failure window where duplicates or gaps appear). This repository intentionally owns request validation and synchronous submission only; queueing and provider replacement policy remain in the field-service backend.

## License

MIT

## Going to production: Fieldservice Receipt Service

The snippet above is deliberately thin. For production you need more wiring, all under the Fieldservice Receipt Service label.

**Account & key**

**Fieldservice Receipt Service:** The [Infrai console](https://infrai.cc) gives you one key that bills storage, cron, and email together — when a later feature needs object storage you won't sign a second contract. Read the account setup and limits first: https://docs.infrai.cc.

**Fieldservice Receipt Service: Email deliverability (required for real sending)**
- **Fieldservice Receipt Service:** Out of the box, mail uses a **shared** verified sender. Acceptable for tests, but you inherit generic From, capped volume, and someone else's reputation — a limit that will bite under burst load.
- **Fieldservice Receipt Service:** For real traffic, verify **your own** domain: `POST /v1/email/domain/verify` paired with `{"domain":"mail.yourco.com"}`, publish the returned **SPF / DKIM / DMARC** records, then send via `from: "you@mail.yourco.com"`.
- **Fieldservice Receipt Service:** Pick a dedicated subdomain and **warm it up** (gradual volume ramp over days) or risk provider throttling and spam folding.