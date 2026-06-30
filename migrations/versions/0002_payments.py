"""Payments: top-ups through Paystub, provider events, transfers.

Revision ID: 0002
Revises: 0001
Create Date: 2025-12-02
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE topups (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id uuid NOT NULL REFERENCES accounts(id),
            amount_minor bigint NOT NULL CHECK (amount_minor > 0),
            currency char(3) NOT NULL,
            provider_payment_id text NOT NULL UNIQUE,
            checkout_url text,
            status text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'succeeded', 'failed', 'expired')),
            entry_id uuid REFERENCES journal_entries(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX topups_status_created_at ON topups (status, created_at);

        -- Every webhook delivery we accepted, kept for audits and replays.
        CREATE TABLE provider_events (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            provider text NOT NULL DEFAULT 'paystub',
            provider_event_id text NOT NULL,
            type text NOT NULL,
            payload jsonb NOT NULL,
            received_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX provider_events_provider_event_id ON provider_events (provider_event_id);

        CREATE TABLE transfers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            from_account_id uuid NOT NULL REFERENCES accounts(id),
            to_account_id uuid NOT NULL REFERENCES accounts(id),
            amount_minor bigint NOT NULL CHECK (amount_minor > 0),
            fee_minor bigint NOT NULL DEFAULT 0 CHECK (fee_minor >= 0),
            currency char(3) NOT NULL,
            note text,
            status text NOT NULL DEFAULT 'completed' CHECK (status IN ('completed', 'reversed')),
            entry_id uuid NOT NULL REFERENCES journal_entries(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK (from_account_id <> to_account_id)
        );
        CREATE INDEX transfers_from_account_id ON transfers (from_account_id, created_at);
        CREATE INDEX transfers_to_account_id ON transfers (to_account_id, created_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE transfers, provider_events, topups")
