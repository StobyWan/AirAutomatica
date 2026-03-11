"""Recordings service: scan, list, filter by session, delete. Time-based session association."""

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airautomatica.services.persistence import PersistenceService

logger = logging.getLogger(__name__)

_FILENAME_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_(\d{6})_cam\.(mp4|h264)$", re.IGNORECASE
)
_FALLBACK_LIMIT = 5


@dataclass
class RecordingInfo:
    """Recording metadata. Same shape for file-based or future DB-backed metadata."""

    filename: str
    timestamp_iso: str
    size_bytes: Optional[int]
    duration_sec: Optional[float]


@dataclass
class GetRecordingsResult:
    """Result of get_recordings with session association metadata."""

    session_id: Optional[int]
    session_resolved: bool
    fallback_used: bool
    count: int
    recordings: list[RecordingInfo]
    pre_filter_count: int
    post_filter_count: int


def _parse_filename_timestamp(filename: str) -> Optional[datetime]:
    """Parse YYYY-MM-DD_HHMMSS from filename. Returns UTC-aware datetime."""
    m = _FILENAME_PATTERN.match(filename)
    if not m:
        return None
    try:
        date_part, time_part, _ = m.groups()
        dt_str = f"{date_part}T{time_part[0:2]}:{time_part[2:4]}:{time_part[4:6]}"
        return datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize datetime to UTC. Naive datetimes assumed to be UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _get_duration_sec(path: Path) -> Optional[float]:
    """Get video duration via ffprobe if available. Returns None on failure."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError) as e:
        logger.debug("ffprobe duration failed for %s: %s", path, e)
    return None


def _safe_basename(filename: str) -> bool:
    """Return True if filename is a safe basename (no path traversal)."""
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return False
    return filename == Path(filename).name


class RecordingsService:
    """Scan, list, filter by session, and delete recordings. Time-based session association."""

    def __init__(
        self,
        recordings_dir: str,
        persistence: Optional["PersistenceService"] = None,
    ) -> None:
        self._dir = Path(recordings_dir).resolve()
        self._persistence = persistence

    def get_recordings(
        self,
        session_id: Optional[int] = None,
        allow_fallback: bool = False,
    ) -> GetRecordingsResult:
        """
        List recordings. When session_id given, filter by time overlap with session.

        Matching rule (all UTC):
        - recording.timestamp >= session.started_at
        - recording.timestamp <= session.ended_at, or <= now if session active

        When session_id provided but session not resolved:
        - session_resolved=False, recordings=[]
        - If allow_fallback=True, fallback_recordings contains recent N from all files
        """
        if not self._dir.is_dir():
            return GetRecordingsResult(
                session_id=session_id,
                session_resolved=session_id is None,
                fallback_used=False,
                count=0,
                recordings=[],
                pre_filter_count=0,
                post_filter_count=0,
            )

        all_candidates: list[RecordingInfo] = []
        for p in self._dir.iterdir():
            if not p.is_file():
                continue
            name = p.name
            lower = name.lower()
            if not (lower.endswith("_cam.mp4") or lower.endswith("_cam.h264")):
                continue
            ts = _parse_filename_timestamp(name)
            if ts is None:
                continue

            try:
                size = p.stat().st_size
            except OSError:
                size = None
            duration = _get_duration_sec(p)

            all_candidates.append(
                RecordingInfo(
                    filename=name,
                    timestamp_iso=ts.isoformat(),
                    size_bytes=size,
                    duration_sec=duration,
                )
            )

        all_candidates.sort(key=lambda r: r.timestamp_iso, reverse=True)
        pre_filter_count = len(all_candidates)

        if session_id is None:
            return GetRecordingsResult(
                session_id=None,
                session_resolved=True,
                fallback_used=False,
                count=pre_filter_count,
                recordings=all_candidates,
                pre_filter_count=pre_filter_count,
                post_filter_count=pre_filter_count,
            )

        start_dt, end_dt = self._get_session_time_range(session_id)
        if start_dt is None:
            logger.warning(
                "Recording session lookup failed: session_id=%s dir=%s pre_filter=%s",
                session_id,
                str(self._dir),
                pre_filter_count,
            )
            fallback = []
            if allow_fallback and all_candidates:
                fallback = all_candidates[:_FALLBACK_LIMIT]
            return GetRecordingsResult(
                session_id=session_id,
                session_resolved=False,
                fallback_used=allow_fallback and bool(fallback),
                count=len(fallback) if allow_fallback else 0,
                recordings=fallback,
                pre_filter_count=pre_filter_count,
                post_filter_count=0,
            )

        start_utc = _to_utc(start_dt)
        end_utc = _to_utc(end_dt) or datetime.now(timezone.utc)

        filtered: list[RecordingInfo] = []
        for r in all_candidates:
            ts = datetime.fromisoformat(r.timestamp_iso)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= start_utc and ts <= end_utc:
                filtered.append(r)

        post_filter_count = len(filtered)
        logger.debug(
            "Recordings session filter: session_id=%s range=[%s, %s] pre=%s post=%s",
            session_id,
            start_utc.isoformat(),
            end_utc.isoformat(),
            pre_filter_count,
            post_filter_count,
        )

        return GetRecordingsResult(
            session_id=session_id,
            session_resolved=True,
            fallback_used=False,
            count=post_filter_count,
            recordings=filtered,
            pre_filter_count=pre_filter_count,
            post_filter_count=post_filter_count,
        )

    def _get_session_time_range(
        self, session_id: int
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Return (started_at, ended_at) for session. (None, None) if not found."""
        if self._persistence is None:
            return (None, None)
        return self._persistence.get_session_time_range(session_id)

    def delete_recording(self, filename: str) -> bool:
        """Delete recording by basename. Returns True on success. Path traversal protected."""
        if not _safe_basename(filename):
            return False
        path = self._dir / filename
        if not path.is_file():
            return False
        try:
            path.unlink()
            return True
        except OSError as e:
            logger.warning("delete_recording failed for %s: %s", filename, e)
            return False
