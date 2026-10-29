"""standing instructions on agent tokens

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-29

A token's owner can leave standing instructions for the agent that holds it; GET /v1/me returns them and the
agent brief folds them in. Idempotent, like 0002.
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE agent_tokens ADD COLUMN IF NOT EXISTS instructions TEXT NOT NULL DEFAULT ''")


def downgrade() -> None:
    op.execute("ALTER TABLE agent_tokens DROP COLUMN IF EXISTS instructions")
