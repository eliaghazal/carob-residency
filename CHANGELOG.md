# Changelog

## v1.0.0 (2026-10-02)

- Transfers to yourself are refused.
- Webhooks whose amount or currency differs from the top-up are refused and logged.
- Exchange quotes last 30 seconds (Finance FP-5).
- The worker expires top-ups abandoned for 24 hours.
- Every view of a customer by staff is audited.
- The router refuses a model whose hash does not match its manifest.
- Console: router confidence on conversations, VIP badge, SLA timer turns red when breached,
  queue counts refresh every 15 seconds.
- Pricing: fee rounding simplified.
- ML: metrics by language variety; ArBanking77 pinned to a commit; data card with the baseline.
- Ops: Grafana on-call dashboard, on-call runbook, traffic generator, architecture overview,
  CI caches npm and validates the Compose files.

## v0.9.0 (2026-06-30)

First release from this repository, imported from the monorepo (`services/carob`).
