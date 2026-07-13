"""Shared RBAC role definitions."""

from __future__ import annotations

import os
from enum import Enum

VALID_ROLES = frozenset({"admin", "reviewer", "ad_ops", "auditor", "read_only"})

ROLE_PRIORITY: tuple[str, ...] = (
    "admin",
    "reviewer",
    "ad_ops",
    "auditor",
    "read_only",
)


class Role(str, Enum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    AD_OPS = "ad_ops"
    AUDITOR = "auditor"
    READ_ONLY = "read_only"


def auth_strict() -> bool:
    env = os.getenv("ENV", "local").lower()
    if env == "prod":
        return True
    return os.getenv("MFA_REQUIRE_AUTH", "").lower() in {"1", "true", "yes"}
