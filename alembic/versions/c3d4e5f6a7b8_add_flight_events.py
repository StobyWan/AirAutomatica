"""add flight_events table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-12

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flight_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("operator_hint", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["flight_sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_flight_events_session_started",
        "flight_events",
        ["session_id", "started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_flight_events_session_started", table_name="flight_events")
    op.drop_table("flight_events")
