"""add generated_debrief_summary and generated_debrief_at to flight_sessions

Revision ID: a1b2c3d4e5f6
Revises: 9d4e5f6a7b8c
Create Date: 2026-03-12

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9d4e5f6a7b8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "flight_sessions",
        sa.Column("generated_debrief_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "flight_sessions",
        sa.Column("generated_debrief_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("flight_sessions", "generated_debrief_at")
    op.drop_column("flight_sessions", "generated_debrief_summary")
