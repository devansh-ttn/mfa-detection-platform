"""Backward-compatible re-export; prefer mfa_common.logging in new code."""

from mfa_common.logging import configure_logging

__all__ = ["configure_logging"]
