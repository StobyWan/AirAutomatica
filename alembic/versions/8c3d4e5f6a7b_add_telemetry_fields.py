"""add telemetry fields (roll, pitch, yaw, mode, heartbeat_age_s, etc.)

Revision ID: 8c3d4e5f6a7b
Revises: 7b2c3d4e5f6a
Create Date: 2026-03-09 20:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "8c3d4e5f6a7b"
down_revision: Union[str, Sequence[str], None] = "7b2c3d4e5f6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "telemetry_samples",
        sa.Column("roll_rad", sa.Float(), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("pitch_rad", sa.Float(), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("yaw_rad", sa.Float(), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("mode", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("heartbeat_age_s", sa.Float(), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("heartbeat", sa.Integer(), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("reconnect_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("last_disconnect_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "telemetry_samples",
        sa.Column("connected", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("telemetry_samples", "connected")
    op.drop_column("telemetry_samples", "last_disconnect_reason")
    op.drop_column("telemetry_samples", "last_heartbeat_at")
    op.drop_column("telemetry_samples", "reconnect_count")
    op.drop_column("telemetry_samples", "heartbeat")
    op.drop_column("telemetry_samples", "heartbeat_age_s")
    op.drop_column("telemetry_samples", "mode")
    op.drop_column("telemetry_samples", "yaw_rad")
    op.drop_column("telemetry_samples", "pitch_rad")
    op.drop_column("telemetry_samples", "roll_rad")
