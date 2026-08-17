"""label clicks as bot traffic

Revision ID: 538166796434
Revises: 289d5fe89487
Create Date: 2026-08-17 13:55:44.513266

Autogenerate produced `add_column(Column('is_bot', Boolean, nullable=False))`,
which works on an empty table and fails the moment there is a single row:

    sqlite3.OperationalError: Cannot add a NOT NULL column with default value NULL

Postgres rejects it the same way. A NOT NULL column added to a populated table
needs a server-side default so existing rows have something to be. Adding one
turns a migration that would have failed in production into one that doesn't.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "538166796434"
down_revision: Union[str, None] = "289d5fe89487"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("clicks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_bot",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.create_index(batch_op.f("ix_clicks_is_bot"), ["is_bot"], unique=False)

    # Backfill what can be known. A click with no user agent was a script —
    # every real browser sends one. Historic rows that had a bot user agent
    # stay labelled human, because reclassifying them would silently rewrite
    # numbers someone may already have reported.
    op.execute("UPDATE clicks SET is_bot = true WHERE user_agent IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("clicks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_clicks_is_bot"))
        batch_op.drop_column("is_bot")
