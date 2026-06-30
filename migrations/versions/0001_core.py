"""Core: customers, staff, accounts and the double-entry journal.

Revision ID: 0001
Revises:
Create Date: 2025-11-04
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE customers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            full_name text NOT NULL,
            email text NOT NULL UNIQUE,
            phone text,
            country char(2) NOT NULL DEFAULT 'LB',
            kyc_status text NOT NULL DEFAULT 'pending'
                CHECK (kyc_status IN ('pending', 'verified', 'rejected')),
            segment text NOT NULL DEFAULT 'standard' CHECK (segment IN ('standard', 'vip')),
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE api_tokens (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id uuid NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            prefix text NOT NULL,
            token_hash text NOT NULL UNIQUE,
            created_at timestamptz NOT NULL DEFAULT now(),
            last_used_at timestamptz,
            revoked_at timestamptz
        );

        CREATE TABLE staff (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email text NOT NULL UNIQUE,
            name text NOT NULL,
            role text NOT NULL CHECK (role IN ('agent', 'supervisor', 'admin')),
            password_hash text NOT NULL,
            active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        -- House accounts have no customer. Balances are a cache of the
        -- postings, updated in the same transaction as each posting.
        CREATE TABLE accounts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id uuid REFERENCES customers(id),
            kind text NOT NULL CHECK (kind IN ('wallet', 'house_fees', 'house_fx', 'provider_clearing')),
            currency char(3) NOT NULL,
            balance_minor bigint NOT NULL DEFAULT 0,
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'frozen', 'closed')),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (customer_id, kind, currency)
        );
        CREATE UNIQUE INDEX accounts_house_unique ON accounts (kind, currency) WHERE customer_id IS NULL;

        CREATE TABLE journal_entries (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            kind text NOT NULL CHECK (kind IN ('topup', 'transfer', 'fx', 'fee', 'reversal', 'adjustment')),
            reference text,
            memo text,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE postings (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            entry_id uuid NOT NULL REFERENCES journal_entries(id),
            account_id uuid NOT NULL REFERENCES accounts(id),
            amount_minor bigint NOT NULL CHECK (amount_minor <> 0),
            currency char(3) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX postings_entry_id ON postings (entry_id);
        CREATE INDEX postings_account_id_created_at ON postings (account_id, created_at);

        CREATE TABLE audit_log (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            actor_type text NOT NULL CHECK (actor_type IN ('customer', 'staff', 'system')),
            actor_id uuid,
            action text NOT NULL,
            target text,
            details jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX audit_log_created_at ON audit_log (created_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE audit_log, postings, journal_entries, accounts, staff, api_tokens, customers")
