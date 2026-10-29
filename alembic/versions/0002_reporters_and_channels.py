"""reporter portal and chat channels

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29

What Releases 2 and 3 added to the schema, as idempotent statements: a database created by 0001 today
already has all of it (0001 is create_all from the models), and a database created before Release 2
gains it here without being dropped. Nothing is removed or rewritten.
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

UP = [
    # Release 2: reporters sign in, bind a payout address, hold sessions and email links
    "ALTER TABLE reporters ADD COLUMN IF NOT EXISTS payout_proof JSONB NOT NULL DEFAULT '{}'::jsonb",
    "ALTER TABLE reporters ADD COLUMN IF NOT EXISTS xe_login_addresses JSONB NOT NULL DEFAULT '[]'::jsonb",
    "ALTER TABLE reporters ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS ix_reporters_xe_address ON reporters (xe_address)",
    "ALTER TABLE challenges ADD COLUMN IF NOT EXISTS detail JSONB NOT NULL DEFAULT '{}'::jsonb",
    """CREATE TABLE IF NOT EXISTS reporter_sessions (
        id SERIAL PRIMARY KEY,
        token_hash VARCHAR(64) NOT NULL UNIQUE,
        reporter_id INTEGER NOT NULL REFERENCES reporters (id),
        csrf VARCHAR(64) NOT NULL,
        how VARCHAR(16) NOT NULL DEFAULT '',
        created_at TIMESTAMPTZ DEFAULT now(),
        expires_at TIMESTAMPTZ NOT NULL,
        ip VARCHAR(64) NOT NULL DEFAULT ''
    )""",
    "CREATE INDEX IF NOT EXISTS ix_reporter_sessions_reporter_id ON reporter_sessions (reporter_id)",
    """CREATE TABLE IF NOT EXISTS reporter_links (
        id SERIAL PRIMARY KEY,
        token_hash VARCHAR(64) NOT NULL UNIQUE,
        email VARCHAR(256) NOT NULL,
        reporter_id INTEGER REFERENCES reporters (id),
        next_path VARCHAR(256) NOT NULL DEFAULT '/my',
        created_at TIMESTAMPTZ DEFAULT now(),
        expires_at TIMESTAMPTZ NOT NULL,
        used_at TIMESTAMPTZ
    )""",
    "CREATE INDEX IF NOT EXISTS ix_reporter_links_email ON reporter_links (email)",
    # web-filed tickets have no source_ref; the uniqueness is only for imported ones
    "DROP INDEX IF EXISTS uq_ticket_source",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_ticket_source ON tickets (source, source_repo, source_ref) "
    "WHERE source_ref <> ''",
    # Release 3: the state last mirrored to a chat thread
    "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS channel_state VARCHAR(8) NOT NULL DEFAULT ''",
]

DOWN = [
    "ALTER TABLE tickets DROP COLUMN IF EXISTS channel_state",
    "DROP TABLE IF EXISTS reporter_links",
    "DROP TABLE IF EXISTS reporter_sessions",
    "ALTER TABLE challenges DROP COLUMN IF EXISTS detail",
    "DROP INDEX IF EXISTS ix_reporters_xe_address",
    "ALTER TABLE reporters DROP COLUMN IF EXISTS last_login_at",
    "ALTER TABLE reporters DROP COLUMN IF EXISTS xe_login_addresses",
    "ALTER TABLE reporters DROP COLUMN IF EXISTS payout_proof",
]


def upgrade() -> None:
    for stmt in UP:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in DOWN:
        op.execute(stmt)
