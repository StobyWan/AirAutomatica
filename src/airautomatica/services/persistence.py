"""Persistence service and throttled telemetry sampler."""

import json
import logging
import math
import threading
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from airautomatica.db.base import get_engine
from airautomatica.db.models import (
    Detection,
    FlightSession,
    PathPoint,
    SystemEvent,
    TelemetrySample,
)
from airautomatica.db.session import get_session
from airautomatica.models.state import nan_to_none

if TYPE_CHECKING:
    from airautomatica.ai.models import AiResult
    from airautomatica.models.state import AircraftState

logger = logging.getLogger(__name__)


class PersistenceService:
    """Repository layer for SQLite persistence. All methods catch exceptions and no-op on failure."""

    def __init__(self) -> None:
        self._last_error: str | None = None
        self._last_error_lock = threading.Lock()

    def _record_error(self, msg: str) -> None:
        with self._last_error_lock:
            self._last_error = msg

    def get_last_persistence_error(self) -> str | None:
        """Return last persistence error message, if any."""
        with self._last_error_lock:
            return self._last_error

    def start_session(
        self,
        telemetry_backend: str,
        ai_backend: str,
        notes: str | None = None,
    ) -> int | None:
        """Insert flight_sessions row. Return session_id or None on failure."""
        if get_engine() is None:
            return None
        try:
            with get_session() as session:
                if session is None:
                    return None
                row = FlightSession(
                    started_at=datetime.now(timezone.utc),
                    ended_at=None,
                    telemetry_backend=telemetry_backend,
                    ai_backend=ai_backend,
                    notes=notes,
                )
                session.add(row)
                session.flush()
                return row.id
        except Exception as e:
            self._record_error(str(e))
            logger.exception("start_session failed: %s", e)
            return None

    def end_session(self, session_id: int) -> None:
        """Set ended_at for the session."""
        if get_engine() is None:
            return
        try:
            with get_session() as session:
                if session is None:
                    return
                row = session.get(FlightSession, session_id)
                if row is not None:
                    row.ended_at = datetime.now(timezone.utc)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("end_session failed: %s", e)

    def insert_telemetry_sample(self, session_id: int, state: "AircraftState") -> None:
        """Insert telemetry_samples row. Converts NaN to None."""
        if get_engine() is None:
            return
        try:
            with get_session() as session:
                if session is None:
                    return
                row = TelemetrySample(
                    session_id=session_id,
                    timestamp=state.timestamp,
                    telemetry_status=state.telemetry_status,
                    lat=nan_to_none(state.lat),
                    lon=nan_to_none(state.lon),
                    rel_alt_m=nan_to_none(state.rel_alt_m),
                    heading_deg=nan_to_none(state.heading_deg),
                    voltage_v=nan_to_none(state.voltage_v),
                    current_a=nan_to_none(state.current_a),
                    groundspeed_m_s=nan_to_none(state.groundspeed_m_s),
                    airspeed_m_s=nan_to_none(state.airspeed_m_s),
                )
                session.add(row)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("insert_telemetry_sample failed: %s", e)

    def insert_detection(
        self,
        session_id: int,
        result: "AiResult",
        lat: float | None,
        lon: float | None,
        rel_alt_m: float | None,
    ) -> None:
        """Insert detections row."""
        if get_engine() is None:
            return
        try:
            lat_n = nan_to_none(lat)
            lon_n = nan_to_none(lon)
            alt_n = nan_to_none(rel_alt_m)
            metadata_json = json.dumps(result.metadata or {})
            with get_session() as session:
                if session is None:
                    return
                row = Detection(
                    session_id=session_id,
                    timestamp=result.timestamp,
                    label=result.label,
                    confidence=result.confidence,
                    summary=result.summary,
                    source_backend=result.source_backend,
                    lat=lat_n,
                    lon=lon_n,
                    rel_alt_m=alt_n,
                    metadata_json=metadata_json,
                )
                session.add(row)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("insert_detection failed: %s", e)

    def get_recent_detections(
        self,
        session_id: int | None,
        limit: int = 20,
    ) -> list[dict]:
        """Fetch recent detections for session. Newest first. Returns [] when DB disabled or on error."""
        if get_engine() is None or session_id is None:
            return []
        try:
            with get_session() as session:
                if session is None:
                    return []
                result = session.execute(
                    select(Detection)
                    .where(Detection.session_id == session_id)
                    .order_by(Detection.timestamp.desc())
                    .limit(limit)
                )
                rows = result.scalars().all()
                out: list[dict] = []
                for row in rows:
                    try:
                        meta = (
                            json.loads(row.metadata_json) if row.metadata_json else {}
                        )
                    except json.JSONDecodeError:
                        meta = {}
                    out.append(
                        {
                            "id": row.id,
                            "session_id": row.session_id,
                            "timestamp": row.timestamp.isoformat(),
                            "label": row.label,
                            "confidence": row.confidence,
                            "summary": row.summary,
                            "source_backend": row.source_backend,
                            "lat": row.lat,
                            "lon": row.lon,
                            "rel_alt_m": row.rel_alt_m,
                            "metadata": meta,
                        }
                    )
                return out
        except Exception as e:
            self._record_error(str(e))
            logger.exception("get_recent_detections failed: %s", e)
            return []

    def insert_path_point(
        self,
        session_id: int,
        timestamp: datetime,
        lat: float,
        lon: float,
        rel_alt_m: float | None = None,
    ) -> None:
        """Insert a path point. Used by PathRecorder for distance-based sampling."""
        if get_engine() is None:
            return
        try:
            with get_session() as session:
                if session is None:
                    return
                row = PathPoint(
                    session_id=session_id,
                    timestamp=timestamp,
                    lat=lat,
                    lon=lon,
                    rel_alt_m=rel_alt_m,
                )
                session.add(row)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("insert_path_point failed: %s", e)

    def get_session_path(
        self,
        session_id: int,
        limit: int = 5000,
    ) -> list[dict]:
        """Fetch flight path for a session, oldest first. Returns [] when DB disabled or on error.

        Uses path_points if available; otherwise falls back to telemetry_samples for backward
        compatibility with sessions recorded before path_points existed.
        """
        if get_engine() is None or session_id is None:
            return []
        try:
            with get_session() as session:
                if session is None:
                    return []
                # Prefer path_points (compact); fallback to telemetry_samples
                result = session.execute(
                    select(PathPoint)
                    .where(PathPoint.session_id == session_id)
                    .order_by(PathPoint.timestamp.asc())
                    .limit(limit)
                )
                rows = result.scalars().all()
                if rows:
                    return [
                        {
                            "timestamp": r.timestamp.isoformat(),
                            "lat": r.lat,
                            "lon": r.lon,
                            "rel_alt_m": r.rel_alt_m,
                        }
                        for r in rows
                    ]
                # Fallback: use telemetry_samples (filter out null lat/lon)
                result = session.execute(
                    select(TelemetrySample)
                    .where(
                        TelemetrySample.session_id == session_id,
                        TelemetrySample.lat.isnot(None),
                        TelemetrySample.lon.isnot(None),
                    )
                    .order_by(TelemetrySample.timestamp.asc())
                    .limit(limit)
                )
                rows = result.scalars().all()
                return [
                    {
                        "timestamp": r.timestamp.isoformat(),
                        "lat": r.lat,
                        "lon": r.lon,
                        "rel_alt_m": r.rel_alt_m,
                    }
                    for r in rows
                ]
        except Exception as e:
            self._record_error(str(e))
            logger.exception("get_session_path failed: %s", e)
            return []

    def get_recent_sessions(
        self,
        limit: int = 10,
        include_detection_count: bool = True,
    ) -> list[dict]:
        """Fetch recent flight sessions, newest first. Returns [] when DB disabled or on error.

        When include_detection_count is True, each session dict includes detection_count.
        """
        if get_engine() is None:
            return []
        try:
            with get_session() as session:
                if session is None:
                    return []
                if include_detection_count:
                    stmt = (
                        select(
                            FlightSession,
                            func.count(Detection.id).label("detection_count"),
                        )
                        .outerjoin(Detection, Detection.session_id == FlightSession.id)
                        .group_by(FlightSession.id)
                        .order_by(FlightSession.started_at.desc())
                        .limit(limit)
                    )
                    result = session.execute(stmt)
                    rows = result.all()
                    out: list[dict] = []
                    for row in rows:
                        fs, det_count = row
                        out.append(
                            {
                                "id": fs.id,
                                "started_at": fs.started_at.isoformat(),
                                "ended_at": (
                                    fs.ended_at.isoformat() if fs.ended_at else None
                                ),
                                "telemetry_backend": fs.telemetry_backend,
                                "ai_backend": fs.ai_backend,
                                "detection_count": det_count or 0,
                            }
                        )
                    return out
                result = session.execute(
                    select(FlightSession)
                    .order_by(FlightSession.started_at.desc())
                    .limit(limit)
                )
                rows = result.scalars().all()
                return [
                    {
                        "id": row.id,
                        "started_at": row.started_at.isoformat(),
                        "ended_at": (
                            row.ended_at.isoformat() if row.ended_at else None
                        ),
                        "telemetry_backend": row.telemetry_backend,
                        "ai_backend": row.ai_backend,
                    }
                    for row in rows
                ]
        except Exception as e:
            self._record_error(str(e))
            logger.exception("get_recent_sessions failed: %s", e)
            return []

    def insert_system_event(
        self,
        session_id: int | None,
        level: str,
        event_type: str,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        """Insert system_events row."""
        if get_engine() is None:
            return
        try:
            metadata_json = json.dumps(metadata) if metadata else None
            with get_session() as session:
                if session is None:
                    return
                row = SystemEvent(
                    session_id=session_id,
                    timestamp=datetime.now(timezone.utc),
                    level=level,
                    event_type=event_type,
                    message=message,
                    metadata_json=metadata_json,
                )
                session.add(row)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("insert_system_event failed: %s", e)

    def get_recent_system_events(self, limit: int = 50) -> list[dict]:
        """Fetch recent system events, newest first. Returns [] when DB disabled or on error."""
        if get_engine() is None:
            return []
        try:
            with get_session() as session:
                if session is None:
                    return []
                result = session.execute(
                    select(SystemEvent)
                    .order_by(SystemEvent.timestamp.desc())
                    .limit(limit)
                )
                rows = result.scalars().all()
                out: list[dict] = []
                for row in rows:
                    try:
                        meta = (
                            json.loads(row.metadata_json) if row.metadata_json else {}
                        )
                    except json.JSONDecodeError:
                        meta = {}
                    out.append(
                        {
                            "id": row.id,
                            "session_id": row.session_id,
                            "timestamp": row.timestamp.isoformat(),
                            "level": row.level,
                            "event_type": row.event_type,
                            "message": row.message,
                            "metadata": meta,
                        }
                    )
                return out
        except Exception as e:
            self._record_error(str(e))
            logger.exception("get_recent_system_events failed: %s", e)
            return []

    def get_recent_telemetry_samples(
        self,
        session_id: int | None,
        limit: int = 60,
    ) -> list[dict]:
        """Fetch recent telemetry samples for session, newest first. Returns [] when DB disabled or on error."""
        if get_engine() is None or session_id is None:
            return []
        try:
            with get_session() as session:
                if session is None:
                    return []
                result = session.execute(
                    select(TelemetrySample)
                    .where(TelemetrySample.session_id == session_id)
                    .order_by(TelemetrySample.timestamp.desc())
                    .limit(limit)
                )
                rows = result.scalars().all()
                return [
                    {
                        "timestamp": r.timestamp.isoformat(),
                        "lat": r.lat,
                        "lon": r.lon,
                        "rel_alt_m": r.rel_alt_m,
                        "voltage_v": r.voltage_v,
                        "groundspeed_m_s": r.groundspeed_m_s,
                    }
                    for r in rows
                ]
        except Exception as e:
            self._record_error(str(e))
            logger.exception("get_recent_telemetry_samples failed: %s", e)
            return []

    def insert_command_sent(
        self,
        session_id: int,
        command_name: str,
        status: str,
        metadata: dict | None = None,
    ) -> None:
        """Insert commands_sent row."""
        if get_engine() is None:
            return
        try:
            from airautomatica.db.models import CommandSent

            metadata_json = json.dumps(metadata) if metadata else None
            with get_session() as session:
                if session is None:
                    return
                row = CommandSent(
                    session_id=session_id,
                    timestamp=datetime.now(timezone.utc),
                    command_name=command_name,
                    status=status,
                    metadata_json=metadata_json,
                )
                session.add(row)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("insert_command_sent failed: %s", e)


class TelemetryLifecycleLogger:
    """Logs telemetry_status transitions as system_events. Only logs when status changes."""

    def __init__(
        self,
        persistence: PersistenceService,
        session_id: int | None,
    ) -> None:
        self._persistence = persistence
        self._session_id = session_id
        self._last_status: str | None = None

    def maybe_log_transition(self, state: "AircraftState") -> None:
        """If telemetry_status changed, log system_event. No-op if persistence unavailable."""
        if self._session_id is None:
            return
        if get_engine() is None:
            return
        status = state.telemetry_status
        if self._last_status == status:
            return
        prev = self._last_status
        self._last_status = status

        metadata: dict = {"from": prev, "to": status}
        if state.reconnect_count > 0:
            metadata["reconnect_count"] = state.reconnect_count
        if state.last_disconnect_reason is not None:
            metadata["last_disconnect_reason"] = state.last_disconnect_reason

        event_type = "telemetry_status_transition"
        message = f"Telemetry {prev or 'initial'} -> {status}"
        level = (
            "info"
            if status == "connected"
            else "warning" if status in ("stale", "backoff") else "info"
        )
        self._persistence.insert_system_event(
            session_id=self._session_id,
            level=level,
            event_type=event_type,
            message=message,
            metadata=metadata,
        )


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance in meters between two lat/lon points."""
    R = 6_371_000  # Earth radius in m
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class PathRecorder:
    """Distance-based path recorder. Stores a point only when aircraft has moved > min_distance_m."""

    def __init__(
        self,
        persistence: PersistenceService,
        session_id: int | None,
        min_distance_m: float = 5.0,
    ) -> None:
        self._persistence = persistence
        self._session_id = session_id
        self._min_distance_m = min_distance_m
        self._last_lat: float | None = None
        self._last_lon: float | None = None

    def maybe_record(self, state: "AircraftState") -> None:
        """If moved enough from last point (or first valid point), insert path point."""
        if self._session_id is None:
            return
        if get_engine() is None:
            return
        lat = nan_to_none(state.lat)
        lon = nan_to_none(state.lon)
        if lat is None or lon is None:
            return
        if self._last_lat is None or self._last_lon is None:
            self._persistence.insert_path_point(
                self._session_id,
                state.timestamp,
                lat,
                lon,
                nan_to_none(state.rel_alt_m),
            )
            self._last_lat = lat
            self._last_lon = lon
            return
        dist = _haversine_m(self._last_lat, self._last_lon, lat, lon)
        if dist >= self._min_distance_m:
            self._persistence.insert_path_point(
                self._session_id,
                state.timestamp,
                lat,
                lon,
                nan_to_none(state.rel_alt_m),
            )
            self._last_lat = lat
            self._last_lon = lon


class TelemetrySampler:
    """Throttled sampling wrapper. Samples at most once per interval_sec."""

    def __init__(
        self,
        persistence: PersistenceService,
        session_id: int | None,
        interval_sec: float = 1.0,
    ) -> None:
        self._persistence = persistence
        self._session_id = session_id
        self._interval_sec = interval_sec
        self._last_sample_time: float = 0.0

    def maybe_sample(self, state: "AircraftState") -> None:
        """If session_id and persistence available, and interval elapsed, insert sample."""
        if self._session_id is None:
            return
        if get_engine() is None:
            return
        now = time.monotonic()
        if now - self._last_sample_time >= self._interval_sec:
            self._last_sample_time = now
            self._persistence.insert_telemetry_sample(self._session_id, state)
