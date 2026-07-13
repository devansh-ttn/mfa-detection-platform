"""RAG chat API (MVP-3.6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.auth.rbac import Role, require_role
from mfa.db.session import get_db_session
from mfa.rag.schemas import ChatRequest, RAGResponse
from mfa.rag.service import answer_query
from mfa.schemas.errors import COMMON_ERROR_RESPONSES

router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=RAGResponse,
    responses=COMMON_ERROR_RESPONSES,
)
async def chat(
    body: ChatRequest,
    session: AsyncSession = Depends(get_db_session),
    actor_id: str = Depends(require_role(Role.REVIEWER, Role.AD_OPS, Role.ADMIN, Role.READ_ONLY)),
) -> RAGResponse:
    response = await answer_query(session, body, actor_id=actor_id)
    await session.commit()
    return response
