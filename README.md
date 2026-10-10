# Carob

> **Carob is a fictional company and this repository is a training simulation** (the Dojo Residency).
> The people, the `@carob.example` emails and the customers are invented, and the code contains
> deliberate defects that tickets ask you to find and fix. Never use it with real money or real
> personal data.

Carob is a money app for the Levant: wallets in US dollars, euros and Lebanese pounds, transfers
between customers, card top-ups through our payment provider (Paystub), currency exchange, and a
support desk where customer messages in English and Arabic are routed to the right team by a model.
The name comes from the carob seed, the old weight behind the carat.

## Run it

You need Docker (Colima or Docker Desktop), [uv](https://docs.astral.sh/uv/) and Node 24.

```bash
make dev        # Postgres, API, worker, Paystub sandbox, Mailpit; migrations and demo data
make web-dev    # the staff console on http://localhost:5173
```

| What | Where |
| --- | --- |
| API and its docs | http://localhost:8000/docs |
| Staff console | http://localhost:5173 (sign in as `nour.haddad@carob.example`, password `carob-dev-password`) |
| Paystub sandbox | http://localhost:8090 (merchant dashboard API under `/admin`, token `paystub-admin-dev`) |
| Mailpit (every email the worker sends) | http://localhost:8025 |
| Grafana, after `make observe` | http://localhost:3000 |

Staff in the demo data: Omar Aziz (admin), Nour Haddad (supervisor), Ziad Farah and Hala Mansour
(agents). Demo customers are `demo00@customers.carob.example` and onwards.

## Checks

```bash
make test        # Python tests against the carob_test database
make lint        # ruff
make typecheck   # mypy and tsc
make web-test    # console tests
```

CI runs all of them on every pull request; `main` only accepts pull requests whose checks pass.

## How the code is laid out

| Path | What |
| --- | --- |
| `src/carob/` | The API (`api/`), money (`ledger.py`, `payments.py`, `transfers.py`, `fx.py`, `pricing.py`), support (`support/`), staff work (`staff.py`), the worker (`worker/`) |
| `src/paystub/` | The provider's sandbox. Not our code to change: treat it as a third party |
| `src/carob_ml/` | The support router's data pipeline, training and evaluation |
| `migrations/` | Plain SQL migrations (Alembic) |
| `web/` | The staff console (React, TypeScript, Vite) |
| `infra/` | Dockerfiles, Compose for staging and production, Prometheus and Grafana |
| `docs/` | Architecture, decisions (`adr/`), policies, the on-call runbook, the data card |

Start with [docs/architecture.md](docs/architecture.md) and [docs/onboarding.md](docs/onboarding.md).

## How work ships

1. A ticket is a GitHub issue. Branch from `main` as `t-010-short-name`.
2. Open a pull request with the template filled in; CI must pass.
3. Merging to `main` builds images and deploys **staging** (`make staging-up` runs it locally on ports 81xx).
4. A version tag (`v1.4.0`) promotes the same images to **production** after approval in the protected
   `production` environment; `make prod-up` runs it on ports 82xx.

Rollback: set `CAROB_IMAGE_TAG` in `infra/env/production.env` to the previous version and run
`make prod-up`. On call: [docs/runbooks/oncall.md](docs/runbooks/oncall.md).

## Data and models

`make data`, `make train`, `make evaluate`. Sources, licenses and known limits are in
[docs/data/README.md](docs/data/README.md).

## Repository settings (for the owner)

- Branch protection on `main`: require a pull request and the `python`, `web` and `compose` checks;
  block force pushes and deletions. Approvals are off: GitHub does not let authors approve their own
  pull requests, and reviews come from outside the repository.
- Environments: `staging` (no rules) and `production` (required reviewer: the owner; wait timer
  5 minutes; deployments only from tags `v*`).
- Actions secret `ACCEPTANCE_TOKEN`: a fine-grained token with read access to the private acceptance
  repository, used only by `.github/workflows/acceptance.yml`.
- Packages: the deploy workflow publishes `carob-api` and `carob-web` to ghcr.io, linked to this
  repository and public, so `make staging-up` and `make prod-up` pull without signing in. Nothing to set.

## License

Code: MIT (see LICENSE). The datasets keep their own licenses (docs/data/README.md).
