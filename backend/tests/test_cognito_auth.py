"""Tests for Cognito JWT role resolution."""

from __future__ import annotations

import pytest

from mfa.auth.cognito import resolve_role_from_groups


def test_resolve_role_prefers_admin_over_reviewer() -> None:
    assert resolve_role_from_groups(["reviewer", "admin"]) == "admin"


def test_resolve_role_from_single_group() -> None:
    assert resolve_role_from_groups(["ad_ops"]) == "ad_ops"


def test_resolve_role_unknown_groups() -> None:
    assert resolve_role_from_groups(["marketing", "guest"]) is None


def test_resolve_role_case_insensitive() -> None:
    assert resolve_role_from_groups(["Reviewer"]) == "reviewer"
