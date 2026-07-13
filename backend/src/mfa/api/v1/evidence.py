"""Evidence artifact proxy — signed-URL style local path (MVP-4)."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.auth.rbac import Role, require_role
from mfa.core.errors import NotFoundError
from mfa.db.models import SignalSnapshot, Url
from mfa.db.session import get_db_session
from mfa.schemas.errors import COMMON_ERROR_RESPONSES
from mfa.storage.evidence_store import get_evidence_store
from pydantic import BaseModel

router = APIRouter(tags=["evidence"])

EVIDENCE_KEY_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/\d+/"
    r"(screenshot\.png|page\.html|dom_metrics\.json)$"
)

CONTENT_TYPES = {
    "screenshot.png": "image/png",
    "page.html": "text/html; charset=utf-8",
    "dom_metrics.json": "application/json",
}


class EvidenceArtifactItem(BaseModel):
    version: int
    persona: str
    screenshot_url: str
    page_html_url: str
    dom_metrics_url: str


class EvidenceArtifactListResponse(BaseModel):
    url_id: uuid.UUID
    artifacts: list[EvidenceArtifactItem]


def _artifact_urls(url_id: uuid.UUID, version: int) -> dict[str, str]:
    base = f"/api/v1/evidence/{url_id}/{version}"
    return {
        "screenshot_url": f"{base}/screenshot.png",
        "page_html_url": f"{base}/page.html",
        "dom_metrics_url": f"{base}/dom_metrics.json",
    }


@router.get(
    "/urls/{url_id}/evidence",
    response_model=EvidenceArtifactListResponse,
    responses=COMMON_ERROR_RESPONSES,
)
async def list_evidence_artifacts(
    url_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    _actor: str = Depends(
        require_role(Role.REVIEWER, Role.ADMIN, Role.AD_OPS, Role.AUDITOR),
    ),
) -> EvidenceArtifactListResponse:
    url_exists = await session.scalar(select(Url.id).where(Url.id == url_id))
    if url_exists is None:
        raise NotFoundError(f"URL not found: {url_id}", code="url_not_found")

    rows = await session.scalars(
        select(SignalSnapshot)
        .where(SignalSnapshot.url_id == url_id)
        .order_by(SignalSnapshot.version.desc())
        .limit(5)
    )

    artifacts: list[EvidenceArtifactItem] = []
    store = get_evidence_store()
    for row in rows:
        urls = _artifact_urls(url_id, row.version)
        # Only include versions with a screenshot on disk / store
        key = f"{url_id}/{row.version}/screenshot.png"
        screenshot_path = Path(getattr(store, "base_dir", Path("backend/evidence"))) / key
        if hasattr(store, "base_dir") and not screenshot_path.is_file():
            continue
        artifacts.append(
            EvidenceArtifactItem(
                version=row.version,
                persona=row.persona,
                screenshot_url=urls["screenshot_url"],
                page_html_url=urls["page_html_url"],
                dom_metrics_url=urls["dom_metrics_url"],
            )
        )

    return EvidenceArtifactListResponse(url_id=url_id, artifacts=artifacts)


@router.get(
    "/evidence/{artifact_path:path}",
    responses={404: COMMON_ERROR_RESPONSES[404]},
)
async def get_evidence_artifact(
    artifact_path: str,
    _actor: str = Depends(
        require_role(Role.REVIEWER, Role.ADMIN, Role.AD_OPS, Role.AUDITOR),
    ),
) -> FileResponse:
    if not EVIDENCE_KEY_RE.fullmatch(artifact_path):
        raise NotFoundError("evidence artifact not found", code="evidence_not_found")

    store = get_evidence_store()
    if not hasattr(store, "base_dir"):
        raise NotFoundError("evidence store not available", code="evidence_not_found")

    file_path = (store.base_dir / artifact_path).resolve()
    base_resolved = store.base_dir.resolve()
    if not str(file_path).startswith(str(base_resolved)):
        raise NotFoundError("evidence artifact not found", code="evidence_not_found")
    if not file_path.is_file():
        raise NotFoundError("evidence artifact not found", code="evidence_not_found")

    filename = file_path.name
    return FileResponse(
        file_path,
        media_type=CONTENT_TYPES.get(filename, "application/octet-stream"),
        filename=filename,
    )
