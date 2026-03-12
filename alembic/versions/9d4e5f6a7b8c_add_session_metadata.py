"""add session metadata (source_port, autopilot, connection_mode, baud)

Revision ID: 9d4e5f6a7b8c
Revises: 8c3d4e5f6a7b
Create Date: 2026-03-12

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "9d4e5f6a7b8c"
down_revision: Union[str, Sequence[str], None] = "8c3d4e5f6a7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "flight_sessions",
        sa.Column("source_port", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "flight_sessions",
        sa.Column("autopilot", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "flight_sessions",
        sa.Column("connection_mode", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "flight_sessions",
        sa.Column("baud", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("flight_sessions", "baud")
    op.drop_column("flight_sessions", "connection_mode")
    op.drop_column("flight_sessions", "autopilot")
    op.drop_column("flight_sessions", "source_port")
