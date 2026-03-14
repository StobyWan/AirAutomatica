"""Ollama task types, prompts, and defensive parsers. Schema-first, no trust of LLM output."""

import logging
import re
from collections import defaultdict
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
    DEBRIEF_SUMMARY = "debrief_summary"


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


@dataclass(frozen=True)
class DebriefSummaryResult:
    """Post-flight debrief summary from Llama. 2-4 sentences max."""

    summary: str


# --- Context types ---


class PerceptionContext(TypedDict, total=False):
    """Context for perception_detection."""

    state: AircraftState | None


class TelemetrySummaryContext(TypedDict, total=False):
    """Context for telemetry_summary."""

    state: AircraftState | None
    telemetry_samples: list[dict[str, Any]]
    llm_context: dict[str, Any] | None  # Preprocessed LlmContextPayload as dict


class EventClassificationContext(TypedDict, total=False):
    """Context for event_classification."""

    events: list[dict[str, Any]]


class DebriefSummaryContext(TypedDict, total=False):
    """Context for debrief_summary. Uses CompactDebriefPayload.to_dict() only."""

    compact_debrief: dict[str, Any]


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

SCHEMA_DEBRIEF_OBJ: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
    },
    "required": ["summary"],
    "additionalProperties": False,
}


def get_format_for_task(task_type: OllamaTaskType) -> str | dict[str, Any]:
    """Return format for Ollama: schema dict for schema-based tasks, 'json' otherwise."""
    if task_type == OllamaTaskType.TELEMETRY_SUMMARY:
        return SCHEMA_TELEMETRY_OBJ
    if task_type == OllamaTaskType.EVENT_CLASSIFICATION:
        return SCHEMA_EVENT_OBJ
    if task_type == OllamaTaskType.DEBRIEF_SUMMARY:
        return SCHEMA_DEBRIEF_OBJ
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
_SCHEMA_DEBRIEF = '{"summary":"2-4 sentence post-flight summary."}'


def _build_debrief_summary_prompt(compact: dict[str, Any]) -> str:
    """Build debrief prompt from compact payload. Includes telemetry, detections, recordings."""
    parts = []
    if compact.get("total_duration_sec") is not None:
        mins = int(compact["total_duration_sec"] / 60)
        parts.append(f"duration={mins}min")
    if compact.get("dominant_phase"):
        parts.append(f"dominant_phase={compact['dominant_phase']}")
    events = compact.get("top_3_event_summaries") or []
    for e in events[:3]:
        if e:
            parts.append(f"event={e}")
    metrics = compact.get("top_5_metrics") or {}
    for k, v in metrics.items():
        if k and v is not None:
            parts.append(f"{k}={v}")
    if compact.get("assessment_sentence"):
        parts.append(f"assessment={compact['assessment_sentence']}")
    if compact.get("detections_summary"):
        parts.append(f"detections={compact['detections_summary']}")
    if compact.get("recordings_count") is not None and compact["recordings_count"] > 0:
        parts.append(f"recordings={compact['recordings_count']}")
    ctx = "\n".join(parts) if parts else "no data"
    return (
        "Post-flight mission-assist summary. Write 2-4 short sentences for the operator. "
        "1) Summarize the session briefly. 2) Highlight the most important issue or condition if any. "
        "3) If detections or recordings exist, mention what was observed or captured. "
        "4) Mention one practical thing to monitor or improve next time. "
        "Stay grounded in the evidence. No exaggerated certainty. No fabricated causes. "
        "Return ONLY valid JSON. No markdown.\n"
        '{"summary":"<2-4 sentences>"}\n'
        f"Data:\n{ctx}"
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
        llm_ctx = context.get("llm_context")
        if llm_ctx is not None:
            phase = llm_ctx.get("phase", "")
            mode = llm_ctx.get("mode", "")
            trend = llm_ctx.get("trend_summary", "")
            events = llm_ctx.get("top_events") or []
            metrics = llm_ctx.get("top_metrics") or {}
            ev_str = (
                ", ".join(
                    f"{e.get('name', '')}({e.get('severity', '')})"
                    for e in events[:3]
                    if e.get("name")
                )
                or "none"
            )
            m_str = ", ".join(f"{k}={v}" for k, v in list(metrics.items())[:5])
            ctx = f"phase={phase} mode={mode} trend={trend} events=[{ev_str}] metrics=[{m_str}]"
        else:
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

    if task_type == OllamaTaskType.DEBRIEF_SUMMARY:
        compact = context.get("compact_debrief") or {}
        return _build_debrief_summary_prompt(compact)

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

_TELEMETRY_SUMMARY_COUNTS: dict[str, int] = defaultdict(int)


def get_telemetry_summary_counts() -> dict[str, int]:
    """Return copy of outcome counters for observability."""
    return {
        "accepted_meaningful": _TELEMETRY_SUMMARY_COUNTS["accepted_meaningful"],
        "normalized_to_nominal": _TELEMETRY_SUMMARY_COUNTS["normalized_to_nominal"],
        "parse_error": _TELEMETRY_SUMMARY_COUNTS["parse_error"],
    }


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
        _TELEMETRY_SUMMARY_COUNTS["parse_error"] += 1
        logger.debug(
            "Telemetry summary parser: raw=%s, using empty dict",
            type(raw).__name__ if raw is not None else "None",
        )
        return TelemetrySummaryResult(
            status="unknown",
            summary="Telemetry nominal",
            concerns=(),
            recommendations=(),
        )
    status = _safe_str(raw.get("status")) or "unknown"
    if status.lower() == "str" or status.lower() not in ("ok", "warn", "error"):
        status = "unknown"
    summary = _safe_str(raw.get("summary")) or ""
    reason = _get_summary_reject_reason(summary)
    if reason:
        _TELEMETRY_SUMMARY_COUNTS["normalized_to_nominal"] += 1
        logger.debug("telemetry summary weak: reason=%s raw=%r", reason, summary)
        summary = "Telemetry nominal"
    else:
        _TELEMETRY_SUMMARY_COUNTS["accepted_meaningful"] += 1
    return TelemetrySummaryResult(
        status=status,
        summary=summary,
        concerns=_safe_str_list(raw.get("concerns"), "concerns"),
        recommendations=_safe_str_list(raw.get("recommendations"), "recommendations"),
    )


def parse_debrief_summary_response(
    raw: dict[str, Any] | None,
) -> DebriefSummaryResult:
    """Parse debrief summary. Never trust raw; coerce to 2-4 sentences."""
    if raw is None or not isinstance(raw, dict):
        raw = {}
    summary = _safe_str(raw.get("summary")) or ""
    if len(summary) > 800:
        summary = summary[:797] + "..."
    return DebriefSummaryResult(summary=summary)


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
