"""Transactional outbox for notifications and other side effects.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-14
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE outbox (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            topic text NOT NULL,
            payload jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            available_at timestamptz NOT NULL DEFAULT now(),
            attempts integer NOT NULL DEFAULT 0,
            last_error text,
            delivered_at timestamptz,
            failed_at timestamptz
        );
        CREATE INDEX outbox_due ON outbox (available_at) WHERE delivered_at IS NULL AND failed_at IS NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE outbox")
