"""Support desk: conversations, messages and model routing.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-03
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE support_conversations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id uuid NOT NULL REFERENCES customers(id),
            status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'pending', 'closed')),
            queue text NOT NULL,
            intent text,
            confidence real,
            router_version text,
            language text,
            assigned_to uuid REFERENCES staff(id),
            sla_due_at timestamptz NOT NULL,
            first_response_at timestamptz,
            closed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX support_conversations_queue_status ON support_conversations (queue, status, sla_due_at);
        CREATE INDEX support_conversations_customer_id ON support_conversations (customer_id);

        CREATE TABLE support_messages (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            conversation_id uuid NOT NULL REFERENCES support_conversations(id) ON DELETE CASCADE,
            author_type text NOT NULL CHECK (author_type IN ('customer', 'staff', 'system')),
            author_id uuid,
            body text NOT NULL CHECK (length(body) BETWEEN 1 AND 4000),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX support_messages_conversation_id ON support_messages (conversation_id, id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE support_messages, support_conversations")
