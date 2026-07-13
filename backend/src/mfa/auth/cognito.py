"""Cognito JWT verification and role resolution (MVP-4.6)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from mfa.auth.roles import ROLE_PRIORITY, VALID_ROLES


@dataclass(frozen=True)
class CognitoSettings:
    user_pool_id: str
    region: str
    app_client_id: str

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"


@dataclass(frozen=True)
class TokenClaims:
    subject: str
    actor_id: str
    role: str
    token_use: str
    groups: tuple[str, ...]


def cognito_enabled() -> bool:
    return get_cognito_settings() is not None


def clear_cognito_cache() -> None:
    """Clear cached JWKS/settings (tests only)."""
    get_cognito_settings.cache_clear()
    _jwks_client.cache_clear()


@lru_cache
def get_cognito_settings() -> CognitoSettings | None:
    pool_id = os.getenv("COGNITO_USER_POOL_ID", "").strip()
    client_id = os.getenv("COGNITO_APP_CLIENT_ID", "").strip()
    if not pool_id or not client_id:
        return None
    region = os.getenv("COGNITO_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    return CognitoSettings(user_pool_id=pool_id, region=region, app_client_id=client_id)


@lru_cache
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def resolve_role_from_groups(groups: list[str] | tuple[str, ...]) -> str | None:
    """Pick the highest-priority MFA role from Cognito group membership."""
    normalized = {g.lower() for g in groups}
    for role in ROLE_PRIORITY:
        if role in normalized:
            return role
    return None


def _actor_from_claims(claims: dict[str, Any]) -> str:
    for key in ("email", "username", "cognito:username", "sub"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown"


def verify_cognito_jwt(token: str) -> TokenClaims:
    """Validate a Cognito ID or access token and extract MFA role + actor."""
    settings = get_cognito_settings()
    if settings is None:
        raise ValueError("Cognito is not configured")

    try:
        signing_key = _jwks_client(settings.jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.issuer,
            options={
                "verify_aud": False,
                "require": ["exp", "iss", "sub", "token_use"],
            },
        )
    except InvalidTokenError as exc:
        raise ValueError("invalid token") from exc

    token_use = str(claims.get("token_use", ""))
    if token_use not in {"id", "access"}:
        raise ValueError("unsupported token_use")

    if token_use == "id":
        aud = claims.get("aud")
        if aud != settings.app_client_id:
            raise ValueError("invalid audience")
    else:
        client_id = claims.get("client_id")
        if client_id != settings.app_client_id:
            raise ValueError("invalid client_id")

    groups_raw = claims.get("cognito:groups") or []
    if isinstance(groups_raw, str):
        groups = (groups_raw,)
    else:
        groups = tuple(str(g) for g in groups_raw)

    role = resolve_role_from_groups(groups)
    if role is None or role not in VALID_ROLES:
        raise ValueError("no valid MFA role in cognito:groups")

    return TokenClaims(
        subject=str(claims["sub"]),
        actor_id=_actor_from_claims(claims),
        role=role,
        token_use=token_use,
        groups=groups,
    )
