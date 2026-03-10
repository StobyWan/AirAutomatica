"""LM Studio AI service for local macOS development and simulation."""

import json
import logging
from datetime import datetime, timezone

import httpx

from airautomatica.ai.json_utils import extract_json
from airautomatica.ai.models import AiResult, create_error_fallback
from airautomatica.ai.service import AiService
from airautomatica.models.state import AircraftState

logger = logging.getLogger(__name__)


class LmStudioAiService(AiService):
    """Local inference via LM Studio HTTP API. Simulates AI HAT-like outputs for dev.

    Deprecated. Use Ollama or mock instead. Kept for backward compatibility.
    """

    def __init__(self, base_url: str, model: str, timeout_sec: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = httpx.Timeout(timeout_sec)

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
                    return create_error_fallback(
                        "Invalid JSON response",
                        {"parse_error": "json"},
                        "lmstudio",
                    )
                choices = data.get("choices") or []
                first = choices[0] if choices else {}
                first = first if isinstance(first, dict) else {}
                msg = first.get("message")
                msg = msg if isinstance(msg, dict) else {}
                content = (msg.get("content") or "").strip()
                parsed = extract_json(content)
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
            return create_error_fallback(
                str(e),
                {"error": True, "error_type": "timeout"},
                "lmstudio",
            )
        except httpx.HTTPStatusError as e:
            logger.warning("LM Studio HTTP error: %s", e)
            return create_error_fallback(
                str(e),
                {"error": True, "error_type": "http"},
                "lmstudio",
            )
        except httpx.RequestError as e:
            logger.warning("LM Studio request failed: %s", e)
            return create_error_fallback(
                str(e),
                {"error": True, "error_type": "network"},
                "lmstudio",
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
