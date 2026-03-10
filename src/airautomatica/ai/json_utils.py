"""Shared JSON extraction for LLM responses. Handles markdown code blocks."""

import json
import re


def extract_json(content: str) -> dict | None:
    """Extract dict from raw LLM content. Handles markdown code blocks."""
    content = (content or "").strip()
    if not content:
        return None
    try:
        out = json.loads(content)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    if match:
        try:
            out = json.loads(match.group(1).strip())
            return out if isinstance(out, dict) else None
        except json.JSONDecodeError:
            pass
    return None
