"""LLM invocation policy. When to call Llama vs when not to."""

from datetime import datetime, timezone
from typing import Sequence

from airautomatica.telemetry.preprocessing.models import TelemetryEvent


def should_invoke_llm(
    *,
    user_requested: bool = False,
    events: Sequence[TelemetryEvent] = (),
    last_invoke_at: datetime | None = None,
    min_interval_sec: float = 20.0,
) -> bool:
    """True if Llama should be invoked. User request always wins."""
    if user_requested:
        return True
    if last_invoke_at is not None:
        elapsed = (datetime.now(timezone.utc) - last_invoke_at).total_seconds()
        if elapsed < min_interval_sec:
            return False
    nontrivial = [e for e in events if e.severity in ("warn", "error", "critical")]
    return len(nontrivial) > 0
