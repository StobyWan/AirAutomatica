"""Ollama AI service for local inference via POST /api/generate."""

import json
import logging
from datetime import datetime, timezone

import httpx

from airautomatica.ai.json_utils import extract_json
from airautomatica.ai.models import AiResult, create_error_fallback
from airautomatica.ai.service import AiService
from airautomatica.models.state import AircraftState

logger = logging.getLogger(__name__)


class OllamaAiService(AiService):
    """Local inference via Ollama HTTP API (POST /api/generate)."""

    def __init__(self, base_url: str, model: str, timeout_sec: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = httpx.Timeout(timeout_sec)

    async def generate_raw(self, prompt: str) -> str:
        """POST to /api/generate, return raw response content. Raises on failure."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            r.raise_for_status()
            data = r.json()
            content = data.get("response", "") or ""
            return content.strip()

    async def infer(self, state: AircraftState | None) -> AiResult:
        """Call Ollama /api/generate. Returns normalized AiResult."""
        prompt = self._build_prompt(state)
        try:
            content = await self.generate_raw(prompt)
        except httpx.TimeoutException as e:
            logger.warning("Ollama inference timeout: %s", e)
            return create_error_fallback(
                str(e),
                {"error": True, "error_type": "timeout"},
                "ollama",
            )
        except httpx.HTTPStatusError as e:
            logger.warning("Ollama HTTP error: %s", e)
            return create_error_fallback(
                str(e),
                {"error": True, "error_type": "http"},
                "ollama",
            )
        except httpx.RequestError as e:
            logger.warning("Ollama request failed: %s", e)
            return create_error_fallback(
                str(e),
                {"error": True, "error_type": "network"},
                "ollama",
            )
        except json.JSONDecodeError as e:
            logger.warning("Ollama returned invalid JSON: %s", e)
            return create_error_fallback(
                "Invalid JSON response",
                {"parse_error": "json"},
                "ollama",
            )
        parsed = extract_json(content)
        if parsed is not None and isinstance(parsed, dict):
            result = AiResult.from_dict(parsed, "ollama")
            meta = dict(result.metadata or {})
            meta["raw_length"] = len(content)
            return AiResult(
                label=result.label,
                confidence=result.confidence,
                summary=result.summary,
                source_backend="ollama",
                timestamp=result.timestamp,
                bbox=result.bbox,
                action=result.action,
                metadata=meta,
            )
        return AiResult(
            label="ollama",
            confidence=0.0,
            summary=content[:200] if content else "No response",
            source_backend="ollama",
            timestamp=datetime.now(timezone.utc),
            metadata={"raw_length": len(content)},
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
