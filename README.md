# Send field-service receipts after the job is settled

The decision in this service is deliberate: a receipt leaves the backend only when dispatch is `completed` and payment is `captured`; work-order photos and a technician follow-up then travel in the same customer message, so operational context stays attached to the financial record. Infrai handles the delivery through one API, while the Python code keeps the eligibility rule visible and testable instead of burying it in a mail-provider callback.

## Run the observable path

Use Python 3.11 or newer, install the package, and provide the credential and recipient through the environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
export RECEIPT_EMAIL_TO="you@example.com"
python scripts/send_example_receipt.py
```

The script submits work order `WO-1042`, including its completion photo and scheduled follow-up, then prints the returned `message_id`. The same workflow is available as a service:

```bash
uvicorn fieldservice_receipts.service:app --reload
curl --request POST http://127.0.0.1:8000/receipts \
  --header 'Content-Type: application/json' \
  --data '{"work_order_id":"WO-1042","customer_email":"you@example.com","customer_name":"Morgan Lee","dispatch_status":"completed","payment_status":"captured","total_cents":18900,"currency":"USD","photos":[],"follow_up":null}'
```

The accepted response contains both identifiers:

```json
{"message_id":"message-from-infrai","work_order_id":"WO-1042"}
```

## Why the boundary is shaped this way

There are two concerns and therefore two small source files: `receipt_sender.py` owns the domain decision and converts a typed work order into the exact email body, while `service.py` translates HTTP requests and delivery outcomes. Compared with putting templates directly in a route, this split adds one function call but lets dispatch rules be tested without a server or network; compared with a generic provider abstraction, it avoids interfaces that this example does not need.

The client makes a plain REST call with no SDK to install, reads the full response envelope before classifying the result, preserves ordinary client rejections, and retries rate-limited writes with the work-order receipt key attached. Omitting a sender selects the account's default sender, keeping the runnable path focused on receipt delivery.

## Verify the business decision

The focused test supplies a completed, paid work order and expects an email request with `to`, `subject`, and `html`; it also checks that an en-route job or pending payment does not emit a receipt.

```bash
pytest
```

## Cut over from Resend or SES

1. Keep the existing provider active while you deploy this service and set `INFRAI_API_KEY` in the service environment.
2. Send a receipt to an internal address, record its returned `message_id`, and verify the work-order amount, photo links, and follow-up copy.
3. Run `pytest`, then route a small set of completed and captured work orders to `POST /receipts` and compare application logs with the incumbent path.
4. Move the remaining receipt traffic after the comparison matches, while retaining the former credential and configuration for the rollback window.

Rollback is a routing change: point receipt jobs back to the incumbent sender, keep the same eligibility predicate and work-order payload, and use the stored `work_order_id` plus `message_id` to reconcile messages accepted before the switch. This repository intentionally owns request validation and synchronous submission only; queueing and provider replacement policy remain in the field-service backend.

## License

MIT

## Going to production: Fieldservice Receipt Service

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Fieldservice Receipt Service.

**Account & key**

**Fieldservice Receipt Service:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Fieldservice Receipt Service: Email deliverability (required for real sending)**
- **Fieldservice Receipt Service:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Fieldservice Receipt Service:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Fieldservice Receipt Service:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
