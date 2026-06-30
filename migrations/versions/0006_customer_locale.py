"""Customers choose the language of notifications.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-09
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE customers ADD COLUMN locale text NOT NULL DEFAULT 'en' CHECK (locale IN ('en', 'ar'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE customers DROP COLUMN locale")
