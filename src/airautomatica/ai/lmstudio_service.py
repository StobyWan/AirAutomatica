"""LM Studio AI service for local macOS development and simulation."""

import json
import logging
import re
from datetime import datetime, timezone

import httpx

from airautomatica.ai.models import AiResult
from airautomatica.ai.service import AiService
from airautomatica.models.state import AircraftState

logger = logging.getLogger(__name__)


def _extract_json_from_content(content: str) -> dict | None:
    """Try to extract JSON from content. Handles markdown code blocks."""
    content = (content or "").strip()
    if not content:
        return None
    # Try raw parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    # Try extracting from ```json ... ``` block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    return None


class LmStudioAiService(AiService):
    """Local inference via LM Studio HTTP API. Simulates AI HAT-like outputs for dev."""

    def __init__(self, base_url: str, model: str, timeout_sec: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = httpx.Timeout(timeout_sec)

    def _fallback_result(self, summary: str, metadata: dict[str, object]) -> AiResult:
        """Return normalized error fallback. Metadata uses allowed keys only."""
        allowed = {"error", "parse_error", "error_type", "raw_length"}
        meta = {k: v for k, v in metadata.items() if k in allowed}
        return AiResult(
            label="error",
            confidence=0.0,
            summary=summary,
            source_backend="lmstudio",
            timestamp=datetime.now(timezone.utc),
            metadata=meta if meta else None,
        )

    async def infer(self, state: AircraftState | None) -> AiResult:
        """Call LM Studio chat completions. Returns normalized AiResult."""
        prompt = self._build_prompt(state)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.post(
                    f"{self._base_url}/v1/chat/completions",
                    json={
                        "model": self._model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 256,
                    },
                )
                r.raise_for_status()
                try:
                    data = r.json()
                except json.JSONDecodeError as e:
                    logger.warning("LM Studio returned invalid JSON: %s", e)
                    return self._fallback_result(
                        "Invalid JSON response",
                        {"parse_error": "json"},
                    )
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                content = (content or "").strip()
                parsed = _extract_json_from_content(content)
                if parsed is not None and isinstance(parsed, dict):
                    result = AiResult.from_dict(parsed, "lmstudio")
                    meta = dict(result.metadata or {})
                    meta["raw_length"] = len(content)
                    return AiResult(
                        label=result.label,
                        confidence=result.confidence,
                        summary=result.summary,
                        source_backend="lmstudio",
                        timestamp=result.timestamp,
                        bbox=result.bbox,
                        action=result.action,
                        metadata=meta,
                    )
                # Best-effort: use raw content as summary
                return AiResult(
                    label="lmstudio",
                    confidence=0.9,
                    summary=content[:200] if content else "No response",
                    source_backend="lmstudio",
                    timestamp=datetime.now(timezone.utc),
                    metadata={"raw_length": len(content)},
                )
        except httpx.TimeoutException as e:
            logger.warning("LM Studio inference timeout: %s", e)
            return self._fallback_result(
                str(e),
                {"error": True, "error_type": "timeout"},
            )
        except httpx.HTTPStatusError as e:
            logger.warning("LM Studio HTTP error: %s", e)
            return self._fallback_result(
                str(e),
                {"error": True, "error_type": "http"},
            )
        except httpx.RequestError as e:
            logger.warning("LM Studio request failed: %s", e)
            return self._fallback_result(
                str(e),
                {"error": True, "error_type": "network"},
            )

    def _build_prompt(self, state: AircraftState | None) -> str:
        """Build prompt from aircraft state. Asks for JSON to simulate AI HAT output."""
        ctx = "mode=unknown, alt=N/A, heading=N/A, battery=N/A"
        if state is not None:
            ctx = (
                f"mode={state.mode}, alt={state.rel_alt_m}m, "
                f"heading={state.heading_deg}deg, battery={state.voltage_v}V"
            )
        return (
            "Return ONLY valid JSON, no other text. Format:\n"
            '{"label":"<detection_label>","confidence":<0-1>,"summary":"<one sentence>","bbox":[x,y,w,h],"action":"<optional>"}\n'
            f"Context: {ctx}."
        )
