"""add replay telemetry fields to telemetry_samples

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-12

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "telemetry_samples",
        sa.Column("armed", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("climb_rate_m_s", sa.Float(), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("gps_fix_type", sa.Integer(), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("satellites_visible", sa.Integer(), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("home_lat", sa.Float(), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("home_lon", sa.Float(), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("watts", sa.Float(), nullable=True),
    )
    op.create_index(
        "ix_telemetry_samples_session_timestamp",
        "telemetry_samples",
        ["session_id", "timestamp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_telemetry_samples_session_timestamp",
        table_name="telemetry_samples",
    )
    op.drop_column("telemetry_samples", "watts")
    op.drop_column("telemetry_samples", "home_lon")
    op.drop_column("telemetry_samples", "home_lat")
    op.drop_column("telemetry_samples", "satellites_visible")
    op.drop_column("telemetry_samples", "gps_fix_type")
    op.drop_column("telemetry_samples", "climb_rate_m_s")
    op.drop_column("telemetry_samples", "armed")
