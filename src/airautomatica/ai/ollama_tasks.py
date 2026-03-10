"""Ollama task types, prompts, and defensive parsers. Schema-first, no trust of LLM output."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypedDict

from airautomatica.ai.models import AiResult
from airautomatica.models.state import AircraftState


class OllamaTaskType(str, Enum):
    """Supported Ollama inference task types."""

    PERCEPTION_DETECTION = "perception_detection"
    TELEMETRY_SUMMARY = "telemetry_summary"
    EVENT_CLASSIFICATION = "event_classification"


# --- Result dataclasses ---


@dataclass(frozen=True)
class TelemetrySummaryResult:
    """Structured telemetry summary. Never trust raw Ollama output."""

    status: str
    summary: str
    concerns: tuple[str, ...]
    recommendations: tuple[str, ...]


@dataclass(frozen=True)
class EventClassificationResult:
    """Structured event classification. Never trust raw Ollama output."""

    severity: str
    category: str
    summary: str
    likely_causes: tuple[str, ...]
    recommended_checks: tuple[str, ...]


# --- Context types ---


class PerceptionContext(TypedDict, total=False):
    """Context for perception_detection."""

    state: AircraftState | None


class TelemetrySummaryContext(TypedDict, total=False):
    """Context for telemetry_summary."""

    state: AircraftState | None
    telemetry_samples: list[dict[str, Any]]


class EventClassificationContext(TypedDict, total=False):
    """Context for event_classification."""

    events: list[dict[str, Any]]


# --- Prompt builders (short, schema-first) ---

_SCHEMA_TELEMETRY = (
    '{"status":"str","summary":"str","concerns":["str"],"recommendations":["str"]}'
)
_SCHEMA_EVENT = (
    '{"severity":"str","category":"str","summary":"str",'
    '"likely_causes":["str"],"recommended_checks":["str"]}'
)
_SCHEMA_PERCEPTION = (
    '{"label":"str","confidence":0-1,"summary":"str","bbox":[x,y,w,h],"action":"str"}'
)


def build_prompt(task_type: OllamaTaskType, context: dict[str, Any]) -> str:
    """Build schema-first prompt. Short, deterministic, JSON-only."""
    if task_type == OllamaTaskType.PERCEPTION_DETECTION:
        state = context.get("state")
        ctx = "mode=unknown, alt=N/A, heading=N/A, battery=N/A"
        if state is not None:
            ctx = (
                f"mode={state.mode}, alt={state.rel_alt_m}m, "
                f"heading={state.heading_deg}deg, battery={state.voltage_v}V"
            )
        return (
            "Return only valid JSON. No markdown. No explanation.\n"
            f"Schema: {_SCHEMA_PERCEPTION}\n"
            f"Context: {ctx}"
        )

    if task_type == OllamaTaskType.TELEMETRY_SUMMARY:
        state = context.get("state")
        samples = context.get("telemetry_samples") or []
        ctx_parts = []
        if state is not None:
            ctx_parts.append(
                f"current: mode={state.mode} alt={state.rel_alt_m}m "
                f"bat={state.voltage_v}V connected={state.connected}"
            )
        if samples:
            ctx_parts.append(f"recent_samples={min(len(samples), 10)}")
        ctx = "; ".join(ctx_parts) if ctx_parts else "no data"
        return (
            "Return only valid JSON. No markdown. No explanation.\n"
            "List fields must always be arrays. Use [] when empty. Never use null for list fields.\n"
            f"Schema: {_SCHEMA_TELEMETRY}\n"
            f"Context: {ctx}"
        )

    if task_type == OllamaTaskType.EVENT_CLASSIFICATION:
        events = context.get("events") or []
        ctx = f"events_count={len(events)}"
        if events:
            parts = []
            for e in events[:5]:
                et = e.get("event_type", "")
                msg = str(e.get("message", ""))[:60]
                parts.append(f"{et}: {msg}")
            ctx = "; ".join(parts)
        return (
            "Return only valid JSON. No markdown. No explanation.\n"
            "List fields must always be arrays. Use [] when empty. Never use null for list fields.\n"
            f"Schema: {_SCHEMA_EVENT}\n"
            f"Context: {ctx}"
        )

    return "Return only valid JSON: {}"


# --- JSON extraction (re-export for backward compatibility) ---

from airautomatica.ai.json_utils import extract_json

# --- Parsers (never trust Ollama; coerce everything) ---


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return s[:2000] if len(s) > 2000 else s


def _safe_str_list(v: Any) -> tuple[str, ...]:
    """Normalize list-like fields: null->(), string->(s,), list->coerced tuple."""
    if v is None:
        return ()
    if isinstance(v, str):
        s = v.strip()
        return (s,) if s else ()
    if not isinstance(v, (list, tuple)):
        return ()
    out = []
    for x in v:
        s = _safe_str(x)
        if s:
            out.append(s[:500])
    return tuple(out)


def parse_perception_response(
    raw: dict[str, Any] | None, source_backend: str
) -> AiResult:
    """Parse perception dict into AiResult. Never trust raw; use AiResult.from_dict."""
    if raw is None or not isinstance(raw, dict):
        raw = {}
    return AiResult.from_dict(raw, source_backend)


def parse_telemetry_summary_response(
    raw: dict[str, Any] | None,
) -> TelemetrySummaryResult:
    """Parse telemetry summary. Never trust Ollama; coerce and default."""
    if raw is None or not isinstance(raw, dict):
        raw = {}
    return TelemetrySummaryResult(
        status=_safe_str(raw.get("status")) or "unknown",
        summary=_safe_str(raw.get("summary")) or "",
        concerns=_safe_str_list(raw.get("concerns")),
        recommendations=_safe_str_list(raw.get("recommendations")),
    )


def parse_event_classification_response(
    raw: dict[str, Any] | None,
) -> EventClassificationResult:
    """Parse event classification. Never trust Ollama; coerce and default."""
    if raw is None or not isinstance(raw, dict):
        raw = {}
    severity = _safe_str(raw.get("severity")) or "info"
    if severity.lower() not in ("info", "warning", "error", "critical"):
        severity = "info"
    return EventClassificationResult(
        severity=severity,
        category=_safe_str(raw.get("category")) or "general",
        summary=_safe_str(raw.get("summary")) or "",
        likely_causes=_safe_str_list(raw.get("likely_causes")),
        recommended_checks=_safe_str_list(raw.get("recommended_checks")),
    )
