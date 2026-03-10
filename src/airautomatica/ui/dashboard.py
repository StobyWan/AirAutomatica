"""Dashboard HTML and helpers."""

from pathlib import Path


def get_dashboard_html() -> str:
    """Load and return the dashboard HTML template."""
    template_path = Path(__file__).parent / "templates" / "dashboard.html"
    return template_path.read_text(encoding="utf-8")


def get_session_detail_html() -> str:
    """Load and return the session detail HTML template."""
    template_path = Path(__file__).parent / "templates" / "session_detail.html"
    return template_path.read_text(encoding="utf-8")
