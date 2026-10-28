"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-28

The first migration creates the schema from the ORM metadata, so the models in desk/models.py are the
single statement of the tables (the brief's "full schema laid down"). Later migrations are written by
hand against this baseline. Seeds the log head and the two id counters.
"""

from alembic import op
import sqlalchemy as sa

import desk.models  # noqa: F401
from desk.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    bind = op.get_bind()
    Base.metadata.create_all(bind)
    op.execute(
        sa.text(
            "INSERT INTO log_head (id, index, hash) VALUES (1, -1, :z) ON CONFLICT (id) DO NOTHING"
        ).bindparams(z="0" * 64)
    )
    op.execute(
        "INSERT INTO id_counters (kind, next) VALUES ('bounty', 1), ('support', 1) ON CONFLICT (kind) DO NOTHING"
    )


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
