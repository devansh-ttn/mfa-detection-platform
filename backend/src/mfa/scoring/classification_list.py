"""Query helpers for listing latest classifications across URLs."""

from __future__ import annotations

from sqlalchemy import Select, and_, func, select

from mfa.db.models import Classification, Url

VALID_TIERS = frozenset({"MFA_High", "MFA_Medium", "MFA_Low", "Non_MFA", "Uncertain"})
VALID_CONFIDENCES = frozenset({"high", "medium", "low"})


def parse_tier_filter(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    expanded: list[str] = []
    for value in values:
        expanded.extend(part.strip() for part in value.split(",") if part.strip())
    invalid = [value for value in expanded if value not in VALID_TIERS]
    if invalid:
        raise ValueError(f"Invalid tier filter: {', '.join(invalid)}")
    return expanded


def parse_confidence_filter(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    expanded: list[str] = []
    for value in values:
        expanded.extend(part.strip() for part in value.split(",") if part.strip())
    invalid = [value for value in expanded if value not in VALID_CONFIDENCES]
    if invalid:
        raise ValueError(f"Invalid confidence filter: {', '.join(invalid)}")
    return expanded


def latest_classification_ids_stmt(
    *,
    tier: list[str] | None = None,
    domain: str | None = None,
    confidence: list[str] | None = None,
) -> Select:
    """Return statement selecting classification IDs (latest per url_id) with filters."""
    latest = (
        select(
            Classification.url_id,
            func.max(Classification.created_at).label("max_created_at"),
        )
        .group_by(Classification.url_id)
        .subquery()
    )

    stmt = (
        select(Classification.id)
        .join(Url, Classification.url_id == Url.id)
        .join(
            latest,
            and_(
                Classification.url_id == latest.c.url_id,
                Classification.created_at == latest.c.max_created_at,
            ),
        )
    )

    if tier:
        stmt = stmt.where(Classification.tier.in_(tier))
    if confidence:
        stmt = stmt.where(Classification.confidence.in_(confidence))
    if domain is not None:
        stmt = stmt.where(Url.domain == domain)

    return stmt.order_by(Classification.created_at.desc())


def classification_index_stmt(
    classification_ids: Select,
) -> Select:
    """Load full classification + URL rows for the given ID subquery."""
    return (
        select(Classification, Url)
        .join(Url, Classification.url_id == Url.id)
        .where(Classification.id.in_(classification_ids))
        .order_by(Classification.created_at.desc())
    )
