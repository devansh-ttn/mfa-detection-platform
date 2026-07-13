"""RAG orchestration service."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from mfa.audit.writer import write_audit_event
from mfa.cache.redis_cache import get_rag_cache
from mfa.rag.retriever import retrieve_evidence
from mfa.rag.sanitizer import classify_intent, sanitize_query
from mfa.rag.schemas import ChatRequest, RAGResponse
from mfa.rag.validator import build_grounded_response, validate_citations


def _resolve_evidence_hash(chunks) -> str | None:
    for chunk in chunks:
        if chunk.doc_type == "classification":
            eh = chunk.content.get("evidence_hash")
            if eh:
                return str(eh)
        if chunk.doc_type == "signal_snapshot":
            eh = chunk.content.get("evidence_hash")
            if eh:
                return str(eh)
    return None


async def answer_query(
    session: AsyncSession,
    request: ChatRequest,
    *,
    actor_id: str = "anonymous",
) -> RAGResponse:
    query = sanitize_query(request.query)
    intent = classify_intent(query)

    parsed_url_id: uuid.UUID | None = None
    if request.url_id:
        try:
            parsed_url_id = uuid.UUID(request.url_id)
        except ValueError:
            pass

    chunks = await retrieve_evidence(
        session,
        intent=intent,
        query=query,
        url_id=parsed_url_id,
        domain=request.domain,
    )

    evidence_hash = _resolve_evidence_hash(chunks)
    cache = get_rag_cache()
    if evidence_hash:
        cached = cache.get(evidence_hash)
        if cached:
            return RAGResponse.model_validate(cached)

    response = build_grounded_response(chunks, query)
    response = validate_citations(response, chunks)

    if evidence_hash:
        cache.set(evidence_hash, response.model_dump(mode="json"))

    await write_audit_event(
        session,
        entity_type="rag_query",
        entity_id=str(uuid.uuid4()),
        action="rag.answer",
        actor_id=actor_id,
        evidence_hash=evidence_hash,
        payload={
            "query": query[:200],
            "intent": intent,
            "confidence": response.confidence,
            "recommended_action": response.recommended_action,
            "citation_ids": [c.id for c in response.citations],
        },
    )

    return response
