"""Jinja2 template-based explanation renderer for MFA classifications.

Re-exports from ``mfa_ml.scoring.explanation`` so the backend and ml-worker
share one template source.
"""

from mfa_ml.scoring.explanation import render_explanation

__all__ = ["render_explanation"]
