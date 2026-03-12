"""Telemetry preprocessing pipeline orchestrator."""

from airautomatica.models.state import AircraftState
from airautomatica.telemetry.preprocessing.context_builder import build_llm_context
from airautomatica.telemetry.preprocessing.event_engine import EventEngine
from airautomatica.telemetry.preprocessing.feature_engine import FeatureEngine
from airautomatica.telemetry.preprocessing.flight_phase_engine import FlightPhaseEngine
from airautomatica.telemetry.preprocessing.models import (
    LlmContextPayload,
    PreprocessingSummary,
    TelemetryEvent,
)
from airautomatica.telemetry.preprocessing.normalizer import prepare_for_preprocessing
from airautomatica.telemetry.preprocessing.rolling_buffer import (
    RollingWindowBuffer,
    create_buffers,
)


class TelemetryPreprocessor:
    """Orchestrates preprocessing. Consumes state, maintains buffers, exposes summaries."""

    def __init__(
        self,
        short_maxlen: int = 20,
        medium_maxlen: int = 100,
        long_maxlen: int = 300,
    ) -> None:
        self._buffers = create_buffers(
            short_maxlen=short_maxlen,
            medium_maxlen=medium_maxlen,
            long_maxlen=long_maxlen,
        )
        self._last_state: AircraftState | None = None
        self._feature_engine = FeatureEngine()
        self._event_engine = EventEngine()
        self._phase_engine = FlightPhaseEngine()

    def on_state(self, state: AircraftState) -> None:
        """Accept state update. Updates buffers. EventEngine will populate _events later."""
        prepared = prepare_for_preprocessing(state)
        self._last_state = prepared
        for buf in self._buffers.values():
            buf.append(prepared)

    def get_summary(self) -> PreprocessingSummary:
        """Summary with phase, mode, buffer count."""
        features = self._feature_engine.compute(self._buffers, self._last_state)
        phase = self._phase_engine.classify(self._last_state, features)
        mode = self._last_state.mode if self._last_state else "UNKNOWN"
        sample_count = len(self._buffers["short"])
        last_ts = (
            self._buffers["short"].get_samples()[-1].timestamp if sample_count else None
        )
        return PreprocessingSummary(
            phase=phase,
            mode=mode,
            buffer_sample_count=sample_count,
            last_timestamp=last_ts,
        )

    def get_llm_context(self) -> LlmContextPayload:
        """Compact, deterministic payload for LLM. Capped: 3 events, 5 metrics, 1 trend."""
        features = self._feature_engine.compute(self._buffers, self._last_state)
        phase = self._phase_engine.classify(self._last_state, features)
        events = self._event_engine.evaluate(features, self._last_state)
        mode = self._last_state.mode if self._last_state else "UNKNOWN"
        return build_llm_context(
            phase=phase,
            mode=mode,
            events=events,
            features=features,
            current=self._last_state,
        )

    def get_recent_events(self) -> list[TelemetryEvent]:
        """Events from EventEngine."""
        features = self._feature_engine.compute(self._buffers, self._last_state)
        return self._event_engine.evaluate(features, self._last_state)

    def get_buffers(self) -> dict[str, RollingWindowBuffer[AircraftState]]:
        """Expose buffers for tests and future FeatureEngine."""
        return self._buffers
