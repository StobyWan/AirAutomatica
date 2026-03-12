"""SQLAlchemy models for SQLite persistence."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all models."""

    pass


class FlightSession(Base):
    """Flight session record."""

    __tablename__ = "flight_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    telemetry_backend: Mapped[str] = mapped_column(String(64), nullable=False)
    ai_backend: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_port: Mapped[str | None] = mapped_column(String(128), nullable=True)
    autopilot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    connection_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    baud: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_debrief_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_debrief_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    manual_home_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    manual_home_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    home_set_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    telemetry_samples = relationship("TelemetrySample", back_populates="session")
    path_points = relationship("PathPoint", back_populates="session")
    detections = relationship("Detection", back_populates="session")
    system_events = relationship("SystemEvent", back_populates="session")
    commands_sent = relationship("CommandSent", back_populates="session")
    flight_events = relationship("FlightEvent", back_populates="session")
    phase_intervals = relationship("PhaseInterval", back_populates="session")


class TelemetrySample(Base):
    """Throttled telemetry sample."""

    __tablename__ = "telemetry_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("flight_sessions.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    telemetry_status: Mapped[str] = mapped_column(String(32), nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    rel_alt_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    roll_rad: Mapped[float | None] = mapped_column(Float, nullable=True)
    pitch_rad: Mapped[float | None] = mapped_column(Float, nullable=True)
    yaw_rad: Mapped[float | None] = mapped_column(Float, nullable=True)
    voltage_v: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    groundspeed_m_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    airspeed_m_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    heartbeat_age_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    heartbeat: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reconnect_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_disconnect_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    connected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    armed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    climb_rate_m_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_fix_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    satellites_visible: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    watts: Mapped[float | None] = mapped_column(Float, nullable=True)

    session = relationship("FlightSession", back_populates="telemetry_samples")


class PathPoint(Base):
    """Flight path point (distance-based sampling for compact path storage)."""

    __tablename__ = "path_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("flight_sessions.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    rel_alt_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    session = relationship("FlightSession", back_populates="path_points")


class Detection(Base):
    """AI detection result."""

    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("flight_sessions.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_backend: Mapped[str] = mapped_column(String(64), nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    rel_alt_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False)

    session = relationship("FlightSession", back_populates="detections")


class SystemEvent(Base):
    """System event log."""

    __tablename__ = "system_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("flight_sessions.id"), nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    session = relationship("FlightSession", back_populates="system_events")


class CommandSent(Base):
    """MAVLink or other command sent."""

    __tablename__ = "commands_sent"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("flight_sessions.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    command_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    session = relationship("FlightSession", back_populates="commands_sent")


class FlightEvent(Base):
    """EventEngine output: rule-based flight events with start/end times."""

    __tablename__ = "flight_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("flight_sessions.id"), nullable=False
    )
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_hint: Mapped[str | None] = mapped_column(Text, nullable=True)

    session = relationship("FlightSession", back_populates="flight_events")


class PhaseInterval(Base):
    """FlightPhaseEngine output: phase intervals for timeline bands."""

    __tablename__ = "phase_intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("flight_sessions.id"), nullable=False
    )
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    session = relationship("FlightSession", back_populates="phase_intervals")
