"""add path_points

Revision ID: 7b2c3d4e5f6a
Revises: 45a9465a5b98
Create Date: 2026-03-09 19:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "7b2c3d4e5f6a"
down_revision: Union[str, Sequence[str], None] = "45a9465a5b98"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "path_points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("rel_alt_m", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["flight_sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_path_points_session_id",
        "path_points",
        ["session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_path_points_session_id", table_name="path_points")
    op.drop_table("path_points")
