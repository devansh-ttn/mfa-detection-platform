"""Resolve authenticated principal from Bearer JWT or dev headers."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from mfa.auth.cognito import cognito_enabled, verify_cognito_jwt
from mfa.auth.roles import VALID_ROLES, auth_strict


@dataclass(frozen=True)
class AuthPrincipal:
    actor_id: str
    role: str


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def resolve_principal(
    *,
    authorization: str | None,
    x_mfa_role: str | None,
    x_mfa_actor: str | None,
) -> AuthPrincipal:
    """Authenticate request via Cognito JWT or (local only) dev role headers."""
    token = extract_bearer_token(authorization)
    if token:
        try:
            claims = verify_cognito_jwt(token)
        except ValueError as exc:
            raise HTTPException(
                status_code=401,
                detail={"error": str(exc), "code": "unauthorized"},
            ) from exc
        return AuthPrincipal(actor_id=claims.actor_id, role=claims.role)

    if auth_strict() or cognito_enabled():
        raise HTTPException(
            status_code=401,
            detail={"error": "authentication required", "code": "unauthorized"},
        )

    role = (x_mfa_role or "reviewer").lower()
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=403,
            detail={"error": "invalid role", "code": "forbidden"},
        )
    return AuthPrincipal(actor_id=x_mfa_actor or "anonymous", role=role)
