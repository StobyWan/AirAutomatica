"""add manual_home_lat, manual_home_lon, home_source, home_set_at to flight_sessions

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-12

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "flight_sessions",
        sa.Column("manual_home_lat", sa.Float(), nullable=True),
    )
    op.add_column(
        "flight_sessions",
        sa.Column("manual_home_lon", sa.Float(), nullable=True),
    )
    op.add_column(
        "flight_sessions",
        sa.Column("home_source", sa.String(32), nullable=True),
    )
    op.add_column(
        "flight_sessions",
        sa.Column("home_set_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("flight_sessions", "home_set_at")
    op.drop_column("flight_sessions", "home_source")
    op.drop_column("flight_sessions", "manual_home_lon")
    op.drop_column("flight_sessions", "manual_home_lat")
