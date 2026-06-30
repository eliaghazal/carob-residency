# ADR 0001: Money in integer minor units, double-entry journal

Date: 2025-11-04 · Status: accepted · Author: Rania Haddad

## Context

Floats cannot represent most decimal amounts exactly, and balances that are updated in place
cannot explain themselves when Finance asks why a number is what it is.

## Decision

- Store and compute money as integers in the currency's ISO 4217 minor units, with the currency
  code next to every amount. Use `Decimal` only for rates and percentages, and round explicitly.
- Record every movement as one journal entry of two or more postings that sum to zero per
  currency. Never update a balance without a posting.
- Keep `accounts.balance_minor` as a cache updated in the same transaction as the postings, and
  reconcile it against the postings.

## Consequences

Every amount is exact and auditable. Code that divides money must name its rounding rule (the
policies say which). Floats anywhere near money are a review blocker.
