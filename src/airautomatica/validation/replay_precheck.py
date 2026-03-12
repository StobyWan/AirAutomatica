"""Replay sample order pre-check for Real-Flight Replay Validation Plan (Section 0).

Validates that replay samples are oldest-first and timestamps increase monotonically.
"""

from dataclasses import dataclass
from datetime import datetime

from airautomatica.services.persistence import PersistenceService


@dataclass
class ReplaySampleOrderResult:
    """Result of replay sample order validation."""

    session_id: int
    passed: bool
    sample_count: int
    first_timestamp: str | None
    last_timestamp: str | None
    non_monotonic_indices: list[int]
    duplicate_timestamps: list[int]
    message: str


def _parse_ts(s: str) -> datetime | None:
    """Parse ISO timestamp string. Returns None on failure."""
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def validate_replay_sample_order(
    session_id: int,
    persistence: PersistenceService | None = None,
    limit: int = 5000,
) -> ReplaySampleOrderResult:
    """Validate replay samples for a session: oldest-first, monotonic timestamps.

    Fetches samples via GET /sessions/{id}/telemetry-samples?limit=5000&order=asc
    and checks:
    - Samples are oldest-first (first timestamp < last timestamp)
    - Timestamps increase monotonically (each >= previous)
    - No weird gaps or duplicates that would distort seeking/playback

    Returns ReplaySampleOrderResult with pass/fail and details.
    """
    if persistence is None:
        persistence = PersistenceService()

    samples = persistence.get_recent_telemetry_samples(
        session_id, limit=limit, order="asc"
    )

    if not samples:
        return ReplaySampleOrderResult(
            session_id=session_id,
            passed=False,
            sample_count=0,
            first_timestamp=None,
            last_timestamp=None,
            non_monotonic_indices=[],
            duplicate_timestamps=[],
            message="No samples returned",
        )

    first_ts = samples[0].get("timestamp")
    last_ts = samples[-1].get("timestamp")
    first_dt = _parse_ts(first_ts) if isinstance(first_ts, str) else None
    last_dt = _parse_ts(last_ts) if isinstance(last_ts, str) else None

    if first_dt is None or last_dt is None:
        return ReplaySampleOrderResult(
            session_id=session_id,
            passed=False,
            sample_count=len(samples),
            first_timestamp=first_ts,
            last_timestamp=last_ts,
            non_monotonic_indices=[],
            duplicate_timestamps=[],
            message="Could not parse timestamps",
        )

    if first_dt > last_dt:
        return ReplaySampleOrderResult(
            session_id=session_id,
            passed=False,
            sample_count=len(samples),
            first_timestamp=first_ts,
            last_timestamp=last_ts,
            non_monotonic_indices=[],
            duplicate_timestamps=[],
            message="Samples not oldest-first: first > last",
        )

    non_monotonic: list[int] = []
    duplicates: list[int] = []
    prev_dt: datetime | None = None

    for i, s in enumerate(samples):
        ts = s.get("timestamp")
        dt = _parse_ts(ts) if isinstance(ts, str) else None
        if dt is None:
            non_monotonic.append(i)
            continue
        if prev_dt is not None:
            if dt < prev_dt:
                non_monotonic.append(i)
            elif dt == prev_dt:
                duplicates.append(i)
        prev_dt = dt

    passed = len(non_monotonic) == 0 and len(duplicates) == 0
    msg_parts: list[str] = []
    if non_monotonic:
        msg_parts.append(
            f"non-monotonic at indices: {non_monotonic[:10]}{'...' if len(non_monotonic) > 10 else ''}"
        )
    if duplicates:
        msg_parts.append(
            f"duplicates at indices: {duplicates[:10]}{'...' if len(duplicates) > 10 else ''}"
        )
    message = "; ".join(msg_parts) if msg_parts else "OK"

    return ReplaySampleOrderResult(
        session_id=session_id,
        passed=passed,
        sample_count=len(samples),
        first_timestamp=first_ts,
        last_timestamp=last_ts,
        non_monotonic_indices=non_monotonic,
        duplicate_timestamps=duplicates,
        message=message,
    )
