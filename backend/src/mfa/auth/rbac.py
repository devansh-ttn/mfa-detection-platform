"""RBAC — Cognito JWT (MVP-4.6) with dev header fallback for local."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException

from mfa.auth.principal import resolve_principal
from mfa.auth.roles import VALID_ROLES, Role, auth_strict

__all__ = ["Role", "VALID_ROLES", "auth_strict", "require_role"]


def require_role(*allowed: Role):
    allowed_values = {r.value for r in allowed} | {Role.ADMIN.value}

    async def _dependency(
        authorization: Annotated[str | None, Header()] = None,
        x_mfa_role: Annotated[str | None, Header(alias="X-MFA-Role")] = None,
        x_mfa_actor: Annotated[str | None, Header(alias="X-MFA-Actor")] = None,
    ) -> str:
        principal = resolve_principal(
            authorization=authorization,
            x_mfa_role=x_mfa_role,
            x_mfa_actor=x_mfa_actor,
        )
        if principal.role not in allowed_values:
            raise HTTPException(
                status_code=403,
                detail={"error": "insufficient role", "code": "forbidden"},
            )
        return principal.actor_id

    return _dependency
