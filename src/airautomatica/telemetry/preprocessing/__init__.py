"""Telemetry preprocessing pipeline. Reduces raw telemetry into compact summaries for LLM."""

from airautomatica.telemetry.preprocessing.debrief_engine import (
    CompactDebriefPayload,
    DebriefEngine,
    DebriefEventStat,
    DebriefSummary,
    build_compact_debrief_context,
)
from airautomatica.telemetry.preprocessing.feature_engine import (
    FeatureEngine,
    FeatureSet,
)
from airautomatica.telemetry.preprocessing.flight_phase_engine import FlightPhaseEngine
from airautomatica.telemetry.preprocessing.models import (
    FlightPhase,
    LlmContextPayload,
    PreprocessingSummary,
    TelemetryEvent,
)
from airautomatica.telemetry.preprocessing.pipeline import TelemetryPreprocessor

__all__ = [
    "CompactDebriefPayload",
    "DebriefEngine",
    "DebriefEventStat",
    "DebriefSummary",
    "FeatureEngine",
    "FeatureSet",
    "FlightPhase",
    "FlightPhaseEngine",
    "LlmContextPayload",
    "PreprocessingSummary",
    "TelemetryEvent",
    "TelemetryPreprocessor",
    "build_compact_debrief_context",
]
