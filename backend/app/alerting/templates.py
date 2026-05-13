"""Minimal HTML email templates for each alert event type.

Per CLAUDE.md global rule: minimal HTML with <p> tags only.
No CSS frameworks, no complex inline styles, no max-width divs.
"""
import json
from typing import Any


def render_email_html(event_type: str, payload: dict[str, Any] | None) -> str:
    """Return minimal HTML email body for the given event type.

    All templates use only <p> tags (per CLAUDE.md global rule).
    payload is included as a formatted JSON block for operational detail.
    """
    payload_str = json.dumps(payload or {}, indent=2, default=str)
    event_label = event_type.replace("_", " ").title()

    return (
        f"<p><strong>PEAD Alert: {event_label}</strong></p>"
        f"<p>Event type: {event_type}</p>"
        f"<p>Details:</p>"
        f"<pre>{payload_str}</pre>"
    )


def render_slack_text(event_type: str, payload: dict[str, Any] | None) -> str:
    """Return plain text Slack message for the given event type."""
    event_label = event_type.replace("_", " ").upper()
    payload_summary = json.dumps(payload or {}, default=str)
    return f"[PEAD] {event_label} | {payload_summary}"
