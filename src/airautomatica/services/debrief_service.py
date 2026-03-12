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
) -> tuple[DebriefSummary | None, CompactDebriefPayload | None, str | None]:
    """Generate debrief and optional LLM summary. Returns (summary, compact, generated_summary) or (None, None, None)."""
    from airautomatica.ai.ollama_tasks import DebriefSummaryResult, OllamaTaskType

    summary, compact = get_session_debrief(session_id, persistence, sample_limit)
    if summary is None or compact is None:
        return (None, None, None)

    context = {"compact_debrief": compact.to_dict()}
    result = await task_service.infer_task(OllamaTaskType.DEBRIEF_SUMMARY, context)
    if isinstance(result, DebriefSummaryResult) and result.summary:
        return (summary, compact, result.summary)
    return (summary, compact, None)
