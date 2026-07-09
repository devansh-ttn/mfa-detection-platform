"""Jinja2 template-based explanation renderer for MFA classifications.

Templates live at ``./templates/<tier_key>.j2``.  Shared by the scoring
pipeline (ml-worker) and the backend API — no LLM (ADR-001).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(disabled_extensions=("j2",)),
    trim_blocks=True,
    lstrip_blocks=True,
)

_TIER_TEMPLATE: dict[str, str] = {
    "MFA_High": "mfa_high.j2",
    "MFA_Medium": "mfa_medium.j2",
    "MFA_Low": "mfa_low.j2",
    "Non_MFA": "non_mfa.j2",
    "Uncertain": "uncertain.j2",
}


def render_explanation(tier: str, top_signals: list[Any]) -> str:
    """Render a plain-text explanation for a classification."""
    template_name = _TIER_TEMPLATE.get(tier)
    if not template_name:
        return f"Classification: {tier}. No template available for this tier."

    try:
        tmpl = _env.get_template(template_name)
        return tmpl.render(tier=tier, top_signals=top_signals).strip()
    except Exception as exc:
        return f"Classification: {tier}. (Template render error: {exc})"
