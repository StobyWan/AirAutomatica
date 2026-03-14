"""Debrief service: helper for generating session debriefs."""

from typing import TYPE_CHECKING

from airautomatica.telemetry.preprocessing.debrief_engine import (
    CompactDebriefPayload,
    DebriefEngine,
    DebriefSummary,
    build_compact_debrief_context,
)

if TYPE_CHECKING:
    from airautomatica.ai.ollama_task_service import OllamaTaskService
    from airautomatica.services.persistence import PersistenceService


def get_session_debrief(
    session_id: int,
    persistence: "PersistenceService",
    sample_limit: int = 10000,
) -> tuple[DebriefSummary | None, CompactDebriefPayload | None]:
    """Generate debrief for a session. Returns (summary, compact_payload) or (None, None)."""
    engine = DebriefEngine()
    summary = engine.generate(session_id, persistence, sample_limit=sample_limit)
    if summary is None:
        return (None, None)
    compact = build_compact_debrief_context(summary)
    return (summary, compact)


async def get_session_debrief_with_llm(
    session_id: int,
    persistence: "PersistenceService",
    task_service: "OllamaTaskService",
    sample_limit: int = 10000,
    recordings_count: int = 0,
) -> tuple[DebriefSummary | None, CompactDebriefPayload | None, str | None]:
    """Generate debrief and optional LLM summary. Returns (summary, compact, generated_summary) or (None, None, None)."""
    from airautomatica.ai.ollama_tasks import DebriefSummaryResult, OllamaTaskType

    summary, compact = get_session_debrief(session_id, persistence, sample_limit)
    if summary is None or compact is None:
        return (None, None, None)

    detections = persistence.get_recent_detections(session_id, limit=50)
    det_summary: list[str] = []
    if detections:
        by_label: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for d in detections:
            lbl = d.get("label") or "unknown"
            by_label[lbl] = by_label.get(lbl, 0) + 1
            src = d.get("source_backend") or "unknown"
            by_source[src] = by_source.get(src, 0) + 1
        label_parts = [f"{lbl}×{n}" for lbl, n in sorted(by_label.items())]
        source_parts = [f"{src}:{n}" for src, n in sorted(by_source.items())]
        det_summary = [
            f"labels=({', '.join(label_parts)})",
            f"sources=({', '.join(source_parts)})",
        ]
    compact_dict = compact.to_dict()
    compact_dict["detections_summary"] = (
        "; ".join(det_summary) if det_summary else "none"
    )
    compact_dict["recordings_count"] = recordings_count
    context = {"compact_debrief": compact_dict}
    result = await task_service.infer_task(OllamaTaskType.DEBRIEF_SUMMARY, context)
    if isinstance(result, DebriefSummaryResult) and result.summary:
        return (summary, compact, result.summary)
    return (summary, compact, None)
