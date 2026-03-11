"""Ollama task types, prompts, and defensive parsers. Schema-first, no trust of LLM output."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypedDict

from airautomatica.ai.models import AiResult
from airautomatica.models.state import AircraftState

logger = logging.getLogger(__name__)


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


# --- JSON Schema objects for Ollama format (schema-based structured outputs) ---

SCHEMA_TELEMETRY_OBJ: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["ok", "warn", "error"]},
        "summary": {"type": "string"},
        "concerns": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["status", "summary", "concerns", "recommendations"],
    "additionalProperties": False,
}

SCHEMA_EVENT_OBJ: dict[str, Any] = {
    "type": "object",
    "properties": {
        "severity": {"type": "string"},
        "category": {"type": "string"},
        "summary": {"type": "string"},
        "likely_causes": {"type": "array", "items": {"type": "string"}},
        "recommended_checks": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "severity",
        "category",
        "summary",
        "likely_causes",
        "recommended_checks",
    ],
    "additionalProperties": False,
}


def get_format_for_task(task_type: OllamaTaskType) -> str | dict[str, Any]:
    """Return format for Ollama: schema dict for schema-based tasks, 'json' otherwise."""
    if task_type == OllamaTaskType.TELEMETRY_SUMMARY:
        return SCHEMA_TELEMETRY_OBJ
    if task_type == OllamaTaskType.EVENT_CLASSIFICATION:
        return SCHEMA_EVENT_OBJ
    return "json"  # perception_detection and unknown


# --- Prompt builders (short, schema-first) ---
# Use example values, not "str" - small models (gemma3:1b) output "str" literally.

_SCHEMA_TELEMETRY = (
    '{"status":"ok","summary":"Brief summary.","concerns":[],"recommendations":[]}'
)
_SCHEMA_EVENT = (
    '{"severity":"info","category":"general","summary":"Brief summary.",'
    '"likely_causes":[],"recommended_checks":[]}'
)
_SCHEMA_PERCEPTION = (
    '{"label":"str","confidence":0-1,"summary":"str","bbox":[x,y,w,h],"action":"str"}'
)


def build_prompt(task_type: OllamaTaskType, context: dict[str, Any]) -> str:
    """Build schema-first prompt. Short, deterministic, JSON-only."""
    if task_type == OllamaTaskType.PERCEPTION_DETECTION:
        return (
            "Perception classifier. Label ONLY: vehicle, person, building, tree, road, "
            "obstacle, aircraft, tower, pole, target, ground vehicle, water, structure. "
            'If nothing: "none".\n'
            "Return ONLY valid JSON. No markdown.\n"
            '{"label":"<label>","confidence":<0-1>,"summary":"<sentence>","bbox":[x,y,w,h],"action":"<optional>"}'
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
            "Telemetry analyst. Summarize the most important operational state in one short sentence. "
            "Plain English only. Summary must be meaningful, not a number/mode/heading/battery/altitude value alone. "
            'If nothing notable: "Telemetry nominal".\n'
            "Return ONLY valid JSON. No markdown.\n"
            '{"status":"ok","summary":"<one sentence>","concerns":[],"recommendations":[]}\n'
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
        return f"Return only valid JSON. No markdown. No explanation.\nContext: {ctx}"

    return "Return only valid JSON: {}"


# --- JSON extraction (re-export for backward compatibility) ---

from airautomatica.ai.json_utils import extract_json

# --- Summary validation (telemetry) ---

_NEUTRAL_SUMMARIES: frozenset[str] = frozenset(
    {"telemetry nominal", "no immediate concerns"}
)
_TELEMETRY_SINGLE_TOKENS: frozenset[str] = frozenset(
    {
        "AUTO",
        "GUIDED",
        "RTL",
        "LOITER",
        "STABILIZE",
        "UNKNOWN",
        "HEADING",
        "ALTITUDE",
        "BATTERY",
        "VOLTAGE",
        "SPEED",
        "GPS",
        "MODE",
        "CONNECTED",
    }
)
# Measurement-only: number + optional unit (%, m, deg, V)
_MEASUREMENT_ONLY_RE = re.compile(r"^[\d.]+\s*(%|m|deg|v)?$", re.IGNORECASE)
_MIN_SUMMARY_LEN = 12


def _get_summary_reject_reason(s: str) -> str:
    """Reason why summary is weak. Empty string means acceptable."""
    t = (s or "").strip()
    if not t:
        return "summary_empty"
    if t.lower() in _NEUTRAL_SUMMARIES:
        return ""
    if _MEASUREMENT_ONLY_RE.match(t):
        return "summary_numeric_only"
    if t.upper() in _TELEMETRY_SINGLE_TOKENS:
        return "summary_single_token"
    if len(t) < _MIN_SUMMARY_LEN:
        return "summary_too_short"
    return ""


# --- Parsers (never trust Ollama; coerce everything) ---


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return s[:2000] if len(s) > 2000 else s


def _safe_str_list(v: Any, field_name: str = "") -> tuple[str, ...]:
    """Normalize list-like fields: null->(), string->(s,), list->coerced tuple."""
    if v is None:
        logger.debug("List field %s: null -> []", field_name or "?")
        return ()
    if isinstance(v, str):
        s = v.strip()
        # Filter model schema leakage: gemma3:1b sometimes outputs literal "str"
        result = (s,) if s and s.lower() != "str" else ()
        logger.debug(
            "List field %s: str %r -> %d item(s)",
            field_name or "?",
            v[:80],
            len(result),
        )
        return result
    if not isinstance(v, (list, tuple)):
        logger.debug("List field %s: %s -> []", field_name or "?", type(v).__name__)
        return ()
    out = []
    for x in v:
        s = _safe_str(x)
        # Filter model schema leakage: gemma3:1b sometimes outputs literal "str"
        if s and s.lower() != "str":
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
        logger.debug(
            "Telemetry summary parser: raw=%s, using empty dict",
            type(raw).__name__ if raw is not None else "None",
        )
        raw = {}
    status = _safe_str(raw.get("status")) or "unknown"
    if status.lower() == "str" or status.lower() not in ("ok", "warn", "error"):
        status = "unknown"
    summary = _safe_str(raw.get("summary")) or ""
    reason = _get_summary_reject_reason(summary)
    if reason:
        logger.debug("telemetry summary weak: reason=%s raw=%r", reason, summary)
        summary = "Telemetry nominal"
    return TelemetrySummaryResult(
        status=status,
        summary=summary,
        concerns=_safe_str_list(raw.get("concerns"), "concerns"),
        recommendations=_safe_str_list(raw.get("recommendations"), "recommendations"),
    )


def parse_event_classification_response(
    raw: dict[str, Any] | None,
) -> EventClassificationResult:
    """Parse event classification. Never trust Ollama; coerce and default."""
    if raw is None or not isinstance(raw, dict):
        logger.debug(
            "Event classification parser: raw=%s, using empty dict",
            type(raw).__name__ if raw is not None else "None",
        )
        raw = {}
    severity = _safe_str(raw.get("severity")) or "info"
    if severity.lower() == "str" or severity.lower() not in (
        "info",
        "warning",
        "error",
        "critical",
    ):
        severity = "info"
    return EventClassificationResult(
        severity=severity,
        category=_safe_str(raw.get("category")) or "general",
        summary=_safe_str(raw.get("summary")) or "",
        likely_causes=_safe_str_list(raw.get("likely_causes"), "likely_causes"),
        recommended_checks=_safe_str_list(
            raw.get("recommended_checks"), "recommended_checks"
        ),
    )
