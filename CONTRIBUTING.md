# Contributing

- Branches: `t-<ticket>-short-name` from `main`. One ticket per pull request.
- Every bug fix comes with a test that fails before the fix.
- Pull requests use the template: what and why, how you verified it, risk and rollback.
- `make lint`, `make typecheck` and `make test` pass before you ask for review.
- Money: integers in minor units, explicit rounding, balanced journal entries (ADR 0001).
- No secrets in the repository; `.env` and `infra/env/*.env` are ignored for a reason.
- Migrations are new files; never edit a migration that has shipped.
