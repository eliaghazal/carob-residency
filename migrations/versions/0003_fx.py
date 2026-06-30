"""Exchange: daily rates, quotes and conversions.

Revision ID: 0003
Revises: 0002
Create Date: 2026-01-20
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        -- rate: units of quote currency per one unit of base currency (major units).
        CREATE TABLE fx_rates (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            base char(3) NOT NULL,
            quote char(3) NOT NULL,
            rate numeric(20, 10) NOT NULL CHECK (rate > 0),
            spread_bps integer NOT NULL DEFAULT 50 CHECK (spread_bps BETWEEN 0 AND 1000),
            valid_from timestamptz NOT NULL DEFAULT now(),
            source text NOT NULL DEFAULT 'manual',
            CHECK (base <> quote)
        );
        CREATE INDEX fx_rates_pair_valid_from ON fx_rates (base, quote, valid_from DESC);

        CREATE TABLE fx_quotes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id uuid NOT NULL REFERENCES customers(id),
            from_currency char(3) NOT NULL,
            to_currency char(3) NOT NULL,
            from_minor bigint NOT NULL CHECK (from_minor > 0),
            to_minor bigint NOT NULL CHECK (to_minor >= 0),
            rate numeric(20, 10) NOT NULL,
            spread_bps integer NOT NULL,
            expires_at timestamptz NOT NULL,
            used_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE fx_conversions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id uuid NOT NULL REFERENCES customers(id),
            quote_id uuid REFERENCES fx_quotes(id),
            from_account_id uuid NOT NULL REFERENCES accounts(id),
            to_account_id uuid NOT NULL REFERENCES accounts(id),
            from_minor bigint NOT NULL,
            to_minor bigint NOT NULL,
            rate numeric(20, 10) NOT NULL,
            spread_bps integer NOT NULL,
            entry_id uuid NOT NULL REFERENCES journal_entries(id),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE fx_conversions, fx_quotes, fx_rates")
