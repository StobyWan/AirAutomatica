"""Dashboard HTML and helpers."""

import json
from pathlib import Path

from airautomatica.config import get_base_path


def get_dashboard_html() -> str:
    """Load and return the dashboard HTML template."""
    template_path = Path(__file__).parent / "templates" / "dashboard.html"
    html = template_path.read_text(encoding="utf-8")
    base_path = get_base_path()
    html = html.replace("__BASE_PATH_JSON__", json.dumps(base_path))
    return html


def get_session_detail_html() -> str:
    """Load and return the session detail HTML template."""
    template_path = Path(__file__).parent / "templates" / "session_detail.html"
    html = template_path.read_text(encoding="utf-8")
    base_path = get_base_path()
    html = html.replace("__BASE_PATH_JSON__", json.dumps(base_path))
    return html
