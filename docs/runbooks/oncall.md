# On call

Owner: Omar Aziz. You are on call when Dojo pages you; production is the `carob-prod` Compose project.

## When a page arrives

1. Acknowledge it (in Dojo) and note the time. Mitigate first, find the root cause second.
2. Open the dashboard: Grafana, "Carob on call" (`make observe`, then http://localhost:3000).
3. Read the logs: `docker compose -p carob-prod logs --since 30m api worker | grep -v healthz`.
4. Say what you see before you change anything: which route, since when, how many customers.
5. Change one thing at a time and watch the dashboard after each change.
6. When the symptom is gone, run the check Dojo gives you, then write the postmortem the same day.

## Where to look

| Question | Where |
| --- | --- |
| Are requests failing or slow? | Dashboard: error rate, p95 latency by route |
| Are webhooks arriving and accepted? | Dashboard: webhooks by result; API logs `webhook handled` and `webhook signature mismatch` |
| What does Paystub say? | Merchant dashboard: `curl -H "authorization: Bearer $PAYSTUB_ADMIN_TOKEN" localhost:8290/admin/settings` (notices, secret rotation time) and `/admin/events?status=failed` |
| Is the worker keeping up? | Dashboard: outbox due and oldest; worker logs `outbox delivery failed` |
| What is the database doing? | `docker compose -p carob-prod exec db psql -U carob` then `SELECT pid, state, wait_event_type, now() - query_start AS age, left(query, 80) FROM pg_stat_activity WHERE datname = 'carob' ORDER BY age DESC;` |
| Is an index missing? | `\di` in psql, compared with `migrations/versions` |
| Which version is running? | `docker compose -p carob-prod images` |

## Mitigations

- **Roll back a release:** set `CAROB_IMAGE_TAG` in `infra/env/production.env` to the previous
  version, `make prod-up`.
- **Restart a service:** `docker compose -p carob-prod restart api` (or `worker`). A restart that
  "fixes" something is a clue, not a root cause.
- **Replay webhooks Paystub could not deliver:** `POST /admin/events/resend-failed` on the merchant
  dashboard, after the cause is fixed.
- **Change configuration:** edit `infra/env/production.env`, then `make prod-up` (Compose recreates
  only what changed).

## Postmortem template

Timeline (with times), impact (who, how many, how long, money affected), how it was detected, root
cause (the mechanism, not a person), resolution, what went well, what went badly, action items with
owners. Blameless: describe decisions and the information available at the time.
