"""Ollama readiness check. Probes API and optionally verifies model presence."""

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urljoin

import httpx

OllamaReadinessReason = Literal[
    "ready", "unreachable", "model_missing", "http_error", "unknown"
]


@dataclass
class OllamaReadinessResult:
    """Result of Ollama readiness check."""

    ready: bool
    reason: OllamaReadinessReason
    detail: str | None = None


def check_ollama_ready(
    base_url: str,
    model: str | None = None,
    timeout_sec: float = 3.0,
) -> OllamaReadinessResult:
    """Probe Ollama API. Returns structured result; optionally verify model in /api/tags."""
    url = base_url.rstrip("/")
    tags_url = urljoin(url + "/", "api/tags")
    try:
        with httpx.Client(timeout=timeout_sec) as client:
            r = client.get(tags_url)
            r.raise_for_status()
            if model:
                data = r.json()
                models = data.get("models", [])
                names = [m.get("name", "") for m in models if isinstance(m, dict)]
                if model not in names:
                    return OllamaReadinessResult(
                        ready=False,
                        reason="model_missing",
                        detail=f"model {model!r} not in tags",
                    )
            return OllamaReadinessResult(ready=True, reason="ready", detail=None)
    except httpx.HTTPStatusError as e:
        return OllamaReadinessResult(
            ready=False,
            reason="http_error",
            detail=str(e),
        )
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
        return OllamaReadinessResult(
            ready=False,
            reason="unreachable",
            detail=str(e),
        )
    except Exception as e:
        return OllamaReadinessResult(
            ready=False,
            reason="unknown",
            detail=str(e),
        )


async def wait_for_ollama_ready(
    base_url: str,
    model: str | None = None,
    max_attempts: int = 5,
    interval_sec: float = 2.0,
    timeout_sec: float = 3.0,
) -> OllamaReadinessResult:
    """Wait for Ollama to be reachable. Retries with backoff. Returns structured result."""
    import asyncio

    url = base_url.rstrip("/") + "/api/tags"
    last_result: OllamaReadinessResult | None = None

    for _ in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                r = await client.get(url)
                r.raise_for_status()
                if model:
                    data = r.json()
                    models = data.get("models", [])
                    names = [m.get("name", "") for m in models if isinstance(m, dict)]
                    if model not in names:
                        last_result = OllamaReadinessResult(
                            ready=False,
                            reason="model_missing",
                            detail=f"model {model!r} not in tags",
                        )
                        await asyncio.sleep(interval_sec)
                        continue
                return OllamaReadinessResult(ready=True, reason="ready", detail=None)
        except httpx.HTTPStatusError as e:
            last_result = OllamaReadinessResult(
                ready=False,
                reason="http_error",
                detail=str(e),
            )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
            last_result = OllamaReadinessResult(
                ready=False,
                reason="unreachable",
                detail=str(e),
            )
        except Exception as e:
            last_result = OllamaReadinessResult(
                ready=False,
                reason="unknown",
                detail=str(e),
            )
        await asyncio.sleep(interval_sec)

    return last_result or OllamaReadinessResult(
        ready=False, reason="unknown", detail="retries exhausted"
    )
