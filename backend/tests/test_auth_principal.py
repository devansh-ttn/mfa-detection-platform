"""Tests for auth principal resolution."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mfa.auth.cognito import clear_cognito_cache
from mfa.auth.principal import resolve_principal


@pytest.fixture(autouse=True)
def _clear_cognito_cache():
    clear_cognito_cache()
    yield
    clear_cognito_cache()


def test_dev_headers_when_not_strict(monkeypatch) -> None:
    monkeypatch.delenv("MFA_REQUIRE_AUTH", raising=False)
    monkeypatch.setenv("ENV", "local")
    monkeypatch.delenv("COGNITO_USER_POOL_ID", raising=False)
    monkeypatch.delenv("COGNITO_APP_CLIENT_ID", raising=False)

    principal = resolve_principal(
        authorization=None,
        x_mfa_role="auditor",
        x_mfa_actor="dev-user",
    )
    assert principal.role == "auditor"
    assert principal.actor_id == "dev-user"


def test_strict_requires_bearer(monkeypatch) -> None:
    monkeypatch.setenv("MFA_REQUIRE_AUTH", "1")
    monkeypatch.setenv("ENV", "local")

    with pytest.raises(HTTPException) as exc:
        resolve_principal(
            authorization=None,
            x_mfa_role="reviewer",
            x_mfa_actor="dev-user",
        )
    assert exc.value.status_code == 401


def test_cognito_config_blocks_dev_headers(monkeypatch) -> None:
    monkeypatch.delenv("MFA_REQUIRE_AUTH", raising=False)
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-east-1_TestPool")
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", "testclient")

    with pytest.raises(HTTPException) as exc:
        resolve_principal(
            authorization=None,
            x_mfa_role="reviewer",
            x_mfa_actor="dev-user",
        )
    assert exc.value.status_code == 401
