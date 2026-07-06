"""Jinja2 template-based explanation renderer for MFA classifications.

Renders human-readable explanation strings from tier + top_signals.
No LLM is used — ADR-001 reserves LLM for MVP+ explanations only.

Templates live at ./templates/<tier_key>.j2 (loaded once at module import).

Usage:
    from mfa.scoring.explanations.templates import render_explanation
    from mfa_ml.scoring.output import ClassificationOutput

    text = render_explanation(output.tier, output.top_signals)
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
    """Render a plain-text explanation for a classification.

    Args:
        tier: One of the five MFA tiers (e.g. ``"MFA_High"``).
        top_signals: List of ``SignalContribution`` objects or any objects
            with ``feature`` and ``value`` attributes.

    Returns:
        Rendered explanation string.  Falls back to a generic message if
        the tier is unrecognised or a template error occurs.
    """
    template_name = _TIER_TEMPLATE.get(tier)
    if not template_name:
        return f"Classification: {tier}. No template available for this tier."

    try:
        tmpl = _env.get_template(template_name)
        return tmpl.render(tier=tier, top_signals=top_signals).strip()
    except Exception as exc:
        return f"Classification: {tier}. (Template render error: {exc})"
