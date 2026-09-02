# Architecture

## Services

```
customer app ----> api (FastAPI, :8000) ----> Postgres
                     |                          ^
                     +--> support router         |
paystub (sandbox, :8090) --signed webhooks--> api |
worker (outbox, gauges) --------------------------+
staff console (React) --/api--> nginx --> api
```

- **api** (`src/carob/api`): the customer API under `/v1`, Paystub webhooks under `/webhooks`, the
  staff console's API under `/staff`, `/healthz` and `/metrics`. Handlers are synchronous and run in
  the threadpool; each request gets its own SQLAlchemy session (`carob.db.get_session`).
- **worker** (`src/carob/worker`): delivers outbox messages (emails today) and refreshes the gauges
  the on-call alerts read. Several workers can run at once (`FOR UPDATE SKIP LOCKED`).
- **paystub** (`src/paystub`): the payment provider's sandbox. It calls us; we call it. Its retries,
  timeouts and secret rotations are outside our control.
- **web** (`web/`): the staff console.

## Money

Amounts are integers in minor units with an ISO currency (ADR 0001). Every movement is one journal
entry whose postings sum to zero per currency (`carob.ledger.post_entry`). `accounts.balance_minor`
is a cache of the postings, written in the same transaction.

| Flow | Postings |
| --- | --- |
| Top-up (webhook `payment.succeeded`) | provider clearing -A, wallet +A |
| Transfer with fee F | sender -(A+F), recipient +A, house fees +F |
| Exchange A (from) to B (to) | wallet(from) -A, house fx(from) +A, house fx(to) -B, wallet(to) +B |
| Reversal | the opposite of the original transfer, fee included |

Fees follow Finance policy FP-3 and exchange follows FP-5 (docs/policies/fees.md).

## Tables

| Table | Holds |
| --- | --- |
| customers, api_tokens | Customers and their hashed API tokens |
| staff | Staff accounts and roles (agent, supervisor, admin) |
| accounts | Customer wallets and house accounts (fees, fx, provider clearing) |
| journal_entries, postings | The double-entry journal |
| topups, provider_events | Card top-ups and every webhook we accepted |
| transfers | Transfers between customers |
| fx_rates, fx_quotes, fx_conversions | Rates, quotes, conversions |
| support_conversations, support_messages | The support desk |
| outbox | Side effects waiting for the worker (ADR 0002) |
| audit_log | Who did what, for compliance |

## Support routing

A customer's first message is routed to a queue (ADR 0003). The router is either the keyword rules
or a model from the registry (`CAROB_ROUTER_MODEL_PATH`), checked against its manifest's hash.
Below the confidence threshold (0.55) the conversation goes to triage. Each queue has a first-answer
SLA (`carob.support.service.SLA_MINUTES`).

## Observability

JSON logs on stdout, one line per request with route, status and duration. Prometheus metrics on the
API's `/metrics` and the worker's port 9101; Grafana's "Carob on call" dashboard reads them.
