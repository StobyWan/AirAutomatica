"""Persistence service and throttled telemetry sampler."""

import json
import logging
import math
import threading
import typing
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast

from sqlalchemy import delete, func, select

from airautomatica.ai.event_normalizer import get_event_type
from airautomatica.config import (
    get_effective_ai_backend,
    get_serial_baud,
    get_serial_port,
)
from airautomatica.db.base import get_engine
from airautomatica.db.models import (
    CommandSent,
    Detection,
    FlightEvent,
    FlightSession,
    PathPoint,
    PhaseInterval,
    SystemEvent,
    TelemetrySample,
)
from airautomatica.db.session import get_session
from airautomatica.models.state import nan_to_none

if TYPE_CHECKING:
    from airautomatica.ai.models import AiResult
    from airautomatica.models.state import AircraftState
    from airautomatica.services.connection_state_store import ConnectionStateStore

logger = logging.getLogger(__name__)


def build_session_start_params(
    connection_store: "ConnectionStateStore | None",
) -> dict:
    """Build kwargs for PersistenceService.start_session from connection_store.

    Used by both manual (POST /session/start) and auto (SessionAutoController) session creation.
    """
    mode = connection_store.get_mode() if connection_store else None
    mode_str = mode.value if mode and hasattr(mode, "value") else "mock"
    telemetry_backend = "mock" if mode_str == "mock" else "serial"
    connection_mode = mode_str
    source_port = None
    autopilot = None
    baud = None
    if connection_store:
        det = connection_store.get_detection_result()
        if det:
            source_port = det.port
            autopilot = det.autopilot
            baud = det.baud
        if not source_port and connection_mode != "mock":
            source_port = get_serial_port()
            baud = get_serial_baud()
    return {
        "telemetry_backend": telemetry_backend,
        "ai_backend": get_effective_ai_backend(),
        "source_port": source_port,
        "autopilot": autopilot,
        "connection_mode": connection_mode,
        "baud": baud,
    }


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
        source_port: str | None = None,
        autopilot: str | None = None,
        connection_mode: str | None = None,
        baud: int | None = None,
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
                    source_port=source_port,
                    autopilot=autopilot,
                    connection_mode=connection_mode,
                    baud=baud,
                )
                session.add(row)
                session.flush()
                return cast(int, row.id)
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

    def delete_session(self, session_id: int) -> bool:
        """Delete session and all child rows. Returns True on success, False on failure."""
        if get_engine() is None:
            return False
        try:
            with get_session() as session:
                if session is None:
                    return False
                session.execute(
                    delete(TelemetrySample).where(
                        TelemetrySample.session_id == session_id
                    )
                )
                session.execute(
                    delete(PathPoint).where(PathPoint.session_id == session_id)
                )
                session.execute(
                    delete(Detection).where(Detection.session_id == session_id)
                )
                session.execute(
                    delete(SystemEvent).where(SystemEvent.session_id == session_id)
                )
                session.execute(
                    delete(CommandSent).where(CommandSent.session_id == session_id)
                )
                session.execute(
                    delete(FlightEvent).where(FlightEvent.session_id == session_id)
                )
                session.execute(
                    delete(PhaseInterval).where(PhaseInterval.session_id == session_id)
                )
                session.execute(
                    delete(FlightSession).where(FlightSession.id == session_id)
                )
            return True
        except Exception as e:
            self._record_error(str(e))
            logger.exception("delete_session failed: %s", e)
            return False

    def get_session_time_range(
        self, session_id: int
    ) -> tuple[datetime | None, datetime | None]:
        """Return (started_at, ended_at) for session. (None, None) if not found or DB disabled."""
        if get_engine() is None:
            return (None, None)
        try:
            with get_session() as session:
                if session is None:
                    return (None, None)
                row = session.get(FlightSession, session_id)
                if row is None:
                    return (None, None)
                return (row.started_at, row.ended_at)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("get_session_time_range failed: %s", e)
            return (None, None)

    def insert_telemetry_sample(self, session_id: int, state: "AircraftState") -> None:
        """Insert telemetry_samples row. Converts NaN to None.

        Watts is stored only when both voltage_v and current_a are valid;
        otherwise NULL (never 0) to keep replay and charting honest.
        """
        if get_engine() is None:
            return
        v = nan_to_none(state.voltage_v)
        i = nan_to_none(state.current_a)
        watts_val: float | None = None
        if v is not None and i is not None:
            watts_val = v * i
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
                    roll_rad=nan_to_none(state.roll_rad),
                    pitch_rad=nan_to_none(state.pitch_rad),
                    yaw_rad=nan_to_none(state.yaw_rad),
                    voltage_v=v,
                    current_a=i,
                    groundspeed_m_s=nan_to_none(state.groundspeed_m_s),
                    airspeed_m_s=nan_to_none(state.airspeed_m_s),
                    mode=state.mode or None,
                    heartbeat_age_s=nan_to_none(state.heartbeat_age_s),
                    heartbeat=state.heartbeat,
                    reconnect_count=state.reconnect_count,
                    last_heartbeat_at=state.last_heartbeat_at,
                    last_disconnect_reason=state.last_disconnect_reason,
                    connected=state.connected,
                    armed=state.armed,
                    climb_rate_m_s=nan_to_none(state.climb_rate_m_s),
                    gps_fix_type=state.gps_fix_type,
                    satellites_visible=state.satellites_visible,
                    home_lat=nan_to_none(state.home_lat),
                    home_lon=nan_to_none(state.home_lon),
                    watts=watts_val,
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
                    event_type = get_event_type(row.label)
                    out.append(
                        {
                            "id": row.id,
                            "session_id": row.session_id,
                            "timestamp": row.timestamp.isoformat(),
                            "label": row.label,
                            "event_type": event_type,
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

    def get_session(self, session_id: int) -> dict | None:
        """Fetch a single session by id. Returns None if not found or DB disabled."""
        if get_engine() is None:
            return None
        try:
            with get_session() as session:
                if session is None:
                    return None
                row = session.get(FlightSession, session_id)
                if row is None:
                    return None
                out: dict = {
                    "id": row.id,
                    "started_at": row.started_at.isoformat(),
                    "ended_at": (row.ended_at.isoformat() if row.ended_at else None),
                    "telemetry_backend": row.telemetry_backend,
                    "ai_backend": row.ai_backend,
                    "notes": row.notes,
                    "source_port": row.source_port,
                    "autopilot": row.autopilot,
                    "connection_mode": row.connection_mode,
                    "baud": row.baud,
                }
                home_lat, home_lon, home_source = self._get_session_home_impl(
                    session, session_id, row
                )
                if home_lat is not None and home_lon is not None:
                    out["home_lat"] = home_lat
                    out["home_lon"] = home_lon
                if home_source is not None:
                    out["home_source"] = home_source
                return out
        except Exception as e:
            self._record_error(str(e))
            logger.exception("get_session failed: %s", e)
            return None

    def _get_session_home_impl(
        self,
        db_session: typing.Any,
        session_id: int,
        flight_session: FlightSession | None = None,
    ) -> tuple[float | None, float | None, str | None]:
        """Return (home_lat, home_lon, home_source) for a session.
        home_source: 'manual_session' | 'autopilot' | 'fallback'
        Session replay/debrief override only; does not affect FC.
        """
        row = flight_session
        if row is None:
            row = db_session.get(FlightSession, session_id)
        if row is None:
            return (None, None, None)

        def _valid(x: typing.Any) -> typing.TypeGuard[float]:
            return x is not None and isinstance(x, (int, float)) and not math.isnan(x)

        if _valid(row.manual_home_lat) and _valid(row.manual_home_lon):
            return (
                float(row.manual_home_lat),
                float(row.manual_home_lon),
                "manual_session",
            )

        result = db_session.execute(
            select(TelemetrySample)
            .where(TelemetrySample.session_id == session_id)
            .order_by(TelemetrySample.timestamp.asc())
            .limit(100)
        )
        samples = result.scalars().all()
        for s in samples:
            if _valid(s.home_lat) and _valid(s.home_lon):
                return (float(s.home_lat), float(s.home_lon), "autopilot")
        for s in samples:
            if _valid(s.lat) and _valid(s.lon):
                return (float(s.lat), float(s.lon), "fallback")

        path_result = db_session.execute(
            select(PathPoint)
            .where(PathPoint.session_id == session_id)
            .order_by(PathPoint.timestamp.asc())
            .limit(1)
        )
        path_row = path_result.scalars().first()
        if path_row is not None and _valid(path_row.lat) and _valid(path_row.lon):
            return (float(path_row.lat), float(path_row.lon), "fallback")

        return (None, None, None)

    def get_session_home(
        self, session_id: int
    ) -> tuple[float | None, float | None, str | None]:
        """Return (home_lat, home_lon, home_source) for a session. (None, None, None) if not found."""
        if get_engine() is None:
            return (None, None, None)
        try:
            with get_session() as session:
                if session is None:
                    return (None, None, None)
                return self._get_session_home_impl(session, session_id)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("get_session_home failed: %s", e)
            return (None, None, None)

    def update_session_home(self, session_id: int, lat: float, lon: float) -> bool:
        """Set replay/debrief home override for a session. Returns True on success.
        Does not affect the flight controller's RTL home."""
        if get_engine() is None:
            return False
        try:
            with get_session() as session:
                if session is None:
                    return False
                row = session.get(FlightSession, session_id)
                if row is None:
                    return False
                row.manual_home_lat = lat
                row.manual_home_lon = lon
                row.home_source = (
                    "manual_session"  # Replay/debrief override only; does not affect FC
                )
                row.home_set_at = datetime.now(timezone.utc)
                return True
        except Exception as e:
            self._record_error(str(e))
            logger.exception("update_session_home failed: %s", e)
            return False

    def clear_session_home(self, session_id: int) -> bool:
        """Clear manual home for a session. Returns True on success."""
        if get_engine() is None:
            return False
        try:
            with get_session() as session:
                if session is None:
                    return False
                row = session.get(FlightSession, session_id)
                if row is None:
                    return False
                row.manual_home_lat = None
                row.manual_home_lon = None
                row.home_source = None
                row.home_set_at = None
                return True
        except Exception as e:
            self._record_error(str(e))
            logger.exception("clear_session_home failed: %s", e)
            return False

    def get_recent_sessions(
        self,
        limit: int = 10,
        include_detection_count: bool = True,
        autopilot_filter: str | None = None,
        connection_mode_filter: str | None = None,
    ) -> list[dict]:
        """Fetch recent flight sessions, newest first. Returns [] when DB disabled or on error.

        When include_detection_count is True, each session dict includes detection_count.
        Optional autopilot_filter and connection_mode_filter filter by metadata.
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
                    )
                    if autopilot_filter:
                        stmt = stmt.where(FlightSession.autopilot == autopilot_filter)
                    if connection_mode_filter:
                        stmt = stmt.where(
                            FlightSession.connection_mode == connection_mode_filter
                        )
                    stmt = stmt.limit(limit)
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
                                "source_port": fs.source_port,
                                "autopilot": fs.autopilot,
                                "connection_mode": fs.connection_mode,
                                "baud": fs.baud,
                            }
                        )
                    return out
                stmt_simple = (
                    select(FlightSession)
                    .order_by(FlightSession.started_at.desc())
                    .limit(limit)
                )
                if autopilot_filter:
                    stmt_simple = stmt_simple.where(
                        FlightSession.autopilot == autopilot_filter
                    )
                if connection_mode_filter:
                    stmt_simple = stmt_simple.where(
                        FlightSession.connection_mode == connection_mode_filter
                    )
                result = session.execute(stmt_simple)
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
                        "source_port": row.source_port,
                        "autopilot": row.autopilot,
                        "connection_mode": row.connection_mode,
                        "baud": row.baud,
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

    def _sample_to_api_dict(
        self, row: TelemetrySample, for_debrief: bool = False
    ) -> dict:
        """Convert TelemetrySample row to dict. Consistent ISO timestamp.
        for_debrief=True adds armed, climb_rate_m_s, home_lat, home_lon, gps_fix_type, satellites_visible.
        for_debrief=False adds heartbeat_age_s, reconnect_count."""
        base = {
            "timestamp": row.timestamp.isoformat(),
            "lat": row.lat,
            "lon": row.lon,
            "rel_alt_m": row.rel_alt_m,
            "voltage_v": row.voltage_v,
            "current_a": row.current_a,
            "groundspeed_m_s": row.groundspeed_m_s,
            "mode": row.mode,
            "heading_deg": row.heading_deg,
            "roll_rad": row.roll_rad,
            "pitch_rad": row.pitch_rad,
            "yaw_rad": row.yaw_rad,
            "airspeed_m_s": row.airspeed_m_s,
            "connected": row.connected,
            "watts": row.watts,
        }
        if for_debrief:
            base["armed"] = row.armed
            base["climb_rate_m_s"] = row.climb_rate_m_s
            base["gps_fix_type"] = row.gps_fix_type
            base["satellites_visible"] = row.satellites_visible
            base["home_lat"] = row.home_lat
            base["home_lon"] = row.home_lon
        else:
            base["heartbeat_age_s"] = row.heartbeat_age_s
            base["reconnect_count"] = row.reconnect_count
        return base

    def get_session_telemetry(
        self,
        session_id: int | None,
        order: str = "desc",
        limit: int = 60,
        for_debrief: bool = False,
    ) -> list[dict]:
        """Unified telemetry sample access. order: asc|desc. limit: max 10000.
        for_debrief=True returns debrief-oriented fields (armed, climb_rate_m_s, home_lat, etc).
        """
        if get_engine() is None or session_id is None:
            return []
        limit = min(max(1, limit), 10000)
        asc = order.lower() == "asc"
        try:
            with get_session() as session:
                if session is None:
                    return []
                stmt = (
                    select(TelemetrySample)
                    .where(TelemetrySample.session_id == session_id)
                    .order_by(
                        TelemetrySample.timestamp.asc()
                        if asc
                        else TelemetrySample.timestamp.desc()
                    )
                    .limit(limit)
                )
                result = session.execute(stmt)
                rows = result.scalars().all()
                return [
                    self._sample_to_api_dict(r, for_debrief=for_debrief) for r in rows
                ]
        except Exception as e:
            self._record_error(str(e))
            logger.exception("get_session_telemetry failed: %s", e)
            return []

    def get_recent_telemetry_samples(
        self,
        session_id: int | None,
        limit: int = 60,
        order: str = "desc",
    ) -> list[dict]:
        """Fetch telemetry samples for session. Returns [] when DB disabled or on error.

        order: "desc" (newest first, default) or "asc" (oldest first, for replay).
        limit: max 10000.
        """
        return self.get_session_telemetry(
            session_id, order=order, limit=limit, for_debrief=False
        )

    def get_session_telemetry_for_debrief(
        self,
        session_id: int,
        limit: int = 10000,
    ) -> list[dict]:
        """Fetch all telemetry samples for session, oldest first. For debrief analysis."""
        return self.get_session_telemetry(
            session_id, order="asc", limit=limit, for_debrief=True
        )

    def save_generated_debrief(
        self,
        session_id: int,
        generated_summary: str,
    ) -> None:
        """Persist generated debrief summary for a session. No-op if engine unavailable."""
        if get_engine() is None:
            return
        if not generated_summary or not generated_summary.strip():
            return
        if generated_summary.strip().startswith("Debrief summary unavailable:"):
            return
        try:
            with get_session() as session:
                if session is None:
                    return
                row = session.get(FlightSession, session_id)
                if row is not None:
                    row.generated_debrief_summary = generated_summary.strip()
                    row.generated_debrief_at = datetime.now(timezone.utc)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("save_generated_debrief failed: %s", e)

    def get_generated_debrief(self, session_id: int) -> str | None:
        """Return persisted generated debrief summary for session, or None."""
        if get_engine() is None:
            return None
        try:
            with get_session() as session:
                if session is None:
                    return None
                row = session.get(FlightSession, session_id)
                if row is None or not row.generated_debrief_summary:
                    return None
                return cast(str, row.generated_debrief_summary)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("get_generated_debrief failed: %s", e)
            return None

    def get_generated_debrief_at(self, session_id: int) -> datetime | None:
        """Return persisted generated_debrief_at for session, or None."""
        if get_engine() is None:
            return None
        try:
            with get_session() as session:
                if session is None:
                    return None
                row = session.get(FlightSession, session_id)
                if row is None or row.generated_debrief_at is None:
                    return None
                return cast(datetime, row.generated_debrief_at)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("get_generated_debrief_at failed: %s", e)
            return None

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

    def insert_flight_event(
        self,
        session_id: int,
        event_name: str,
        severity: str,
        started_at: datetime,
        ended_at: datetime | None = None,
        evidence: dict | None = None,
        operator_hint: str | None = None,
    ) -> None:
        """Insert flight_events row. EventEngine output."""
        if get_engine() is None:
            return
        try:
            evidence_json = json.dumps(evidence) if evidence else None
            with get_session() as session:
                if session is None:
                    return
                row = FlightEvent(
                    session_id=session_id,
                    event_name=event_name,
                    severity=severity,
                    started_at=started_at,
                    ended_at=ended_at,
                    evidence_json=evidence_json,
                    operator_hint=operator_hint,
                )
                session.add(row)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("insert_flight_event failed: %s", e)

    def get_session_flight_events(
        self,
        session_id: int,
        limit: int = 200,
    ) -> list[dict]:
        """Fetch flight events for session, oldest first. For replay timeline."""
        if get_engine() is None or session_id is None:
            return []
        try:
            with get_session() as session:
                if session is None:
                    return []
                result = session.execute(
                    select(FlightEvent)
                    .where(FlightEvent.session_id == session_id)
                    .order_by(FlightEvent.started_at.asc())
                    .limit(limit)
                )
                rows = result.scalars().all()
                out: list[dict] = []
                for row in rows:
                    try:
                        evidence = (
                            json.loads(row.evidence_json) if row.evidence_json else {}
                        )
                    except json.JSONDecodeError:
                        evidence = {}
                    out.append(
                        {
                            "id": row.id,
                            "session_id": row.session_id,
                            "event_name": row.event_name,
                            "severity": row.severity,
                            "started_at": row.started_at.isoformat(),
                            "ended_at": (
                                row.ended_at.isoformat() if row.ended_at else None
                            ),
                            "evidence": evidence,
                            "operator_hint": row.operator_hint,
                        }
                    )
                return out
        except Exception as e:
            self._record_error(str(e))
            logger.exception("get_session_flight_events failed: %s", e)
            return []

    def insert_phase_interval(
        self,
        session_id: int,
        phase: str,
        started_at: datetime,
        ended_at: datetime,
    ) -> None:
        """Insert phase_intervals row. FlightPhaseEngine output."""
        if get_engine() is None:
            return
        try:
            with get_session() as session:
                if session is None:
                    return
                row = PhaseInterval(
                    session_id=session_id,
                    phase=phase,
                    started_at=started_at,
                    ended_at=ended_at,
                )
                session.add(row)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("insert_phase_interval failed: %s", e)

    def get_session_phase_intervals(
        self,
        session_id: int,
        limit: int = 500,
    ) -> list[dict]:
        """Fetch phase intervals for session, oldest first. For replay timeline bands."""
        if get_engine() is None or session_id is None:
            return []
        try:
            with get_session() as session:
                if session is None:
                    return []
                result = session.execute(
                    select(PhaseInterval)
                    .where(PhaseInterval.session_id == session_id)
                    .order_by(PhaseInterval.started_at.asc())
                    .limit(limit)
                )
                rows = result.scalars().all()
                return [
                    {
                        "id": r.id,
                        "session_id": r.session_id,
                        "phase": r.phase,
                        "started_at": r.started_at.isoformat(),
                        "ended_at": r.ended_at.isoformat(),
                    }
                    for r in rows
                ]
        except Exception as e:
            self._record_error(str(e))
            logger.exception("get_session_phase_intervals failed: %s", e)
            return []


# Re-export recorders for backward compatibility. Implementations live in persistence_recorders.py.
from airautomatica.services.persistence_recorders import (
    EventPersistenceRecorder,
    PathRecorder,
    PhasePersistenceRecorder,
    TelemetryLifecycleLogger,
    TelemetrySampler,
    _haversine_m,
)

__all__ = [
    "PersistenceService",
    "build_session_start_params",
    "EventPersistenceRecorder",
    "PhasePersistenceRecorder",
    "PathRecorder",
    "TelemetrySampler",
    "TelemetryLifecycleLogger",
    "_haversine_m",
]
