"""Normalized AI result model for mission logic."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

# Allowed metadata keys per backend. Keeps metadata from becoming a junk drawer.
_METADATA_ALLOWLIST: frozenset[str] = frozenset({
    "error", "parse_error", "error_type", "raw_length",
    "call_count", "mode", "model_name", "device", "todo",
})


def _normalize_confidence(v: float) -> float:
    """Clamp confidence to 0.0–1.0."""
    try:
        f = float(v)
        return max(0.0, min(1.0, f))
    except (TypeError, ValueError):
        return 0.0


def _normalize_bbox(v: Any) -> tuple[float, float, float, float] | None:
    """Accept list/tuple of 4 floats; return (x, y, w, h) or None if invalid."""
    if v is None:
        return None
    try:
        seq = list(v)
        if len(seq) != 4:
            return None
        return (float(seq[0]), float(seq[1]), float(seq[2]), float(seq[3]))
    except (TypeError, ValueError, IndexError):
        return None


@dataclass(frozen=True)
class AiResult:
    """Normalized AI result. Mission logic consumes this regardless of source (mock, lmstudio, aihat)."""

    label: str  # Detection/inference label. Required.
    confidence: float  # 0.0–1.0. Clamped on parse.
    summary: str  # Human-readable summary. Required.
    source_backend: str  # "mock", "lmstudio", or "aihat".
    timestamp: datetime  # When produced.
    bbox: tuple[float, float, float, float] | None = None  # (x, y, w, h) for detections; optional.
    action: str | None = None  # Optional suggested action.
    metadata: dict[str, Any] | None = None  # Allowed keys only; see ai_backends.md.

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API or logging."""
        return {
            "label": self.label,
            "confidence": self.confidence,
            "summary": self.summary,
            "source_backend": self.source_backend,
            "timestamp": self.timestamp.isoformat(),
            "bbox": list(self.bbox) if self.bbox else None,
            "action": self.action,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any], source_backend: str) -> "AiResult":
        """Parse dict (e.g. from LM Studio JSON) into normalized AiResult. Missing fields use defaults."""
        if not isinstance(d, dict):
            d = {}
        label = str(d.get("label", "unknown")).strip() or "unknown"
        confidence = _normalize_confidence(d.get("confidence", 0.0))
        summary = str(d.get("summary", "")).strip() or ""
        action_raw = d.get("action")
        action = str(action_raw).strip() if action_raw is not None else None
        action = action if action else None
        bbox = _normalize_bbox(d.get("bbox"))
        metadata = {k: d[k] for k in _METADATA_ALLOWLIST if k in d}
        return cls(
            label=label,
            confidence=confidence,
            summary=summary,
            source_backend=source_backend,
            timestamp=datetime.now(timezone.utc),
            bbox=bbox,
            action=action,
            metadata=metadata if metadata else None,
        )
