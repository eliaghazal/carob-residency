# ADR 0002: Transactional outbox; no network calls inside a transaction

Date: 2026-04-14 · Status: accepted · Author: Omar Aziz

## Context

Sending an email or calling a partner inside a database transaction holds locks and a pooled
connection while we wait on someone else's network, and if the transaction rolls back after the
call, the side effect cannot be taken back.

## Decision

- Side effects are written to the `outbox` table in the same transaction as the business change
  and delivered afterwards by the worker, with retries and backoff.
- Calls to partners (Paystub) happen before or after a transaction, never inside one.

## Consequences

Notifications can arrive twice (a retry after a crash), never for a change that did not happen.
Handlers must tolerate repeats.
