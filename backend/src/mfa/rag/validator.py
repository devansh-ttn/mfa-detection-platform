"""Citation validator — every claim must map to retrieved chunk IDs."""

from __future__ import annotations

from mfa.rag.schemas import Citation, EvidenceChunk, RAGResponse, SignalContribution


def validate_citations(response: RAGResponse, chunks: list[EvidenceChunk]) -> RAGResponse:
    valid_ids = {c.chunk_id for c in chunks}
    validated: list[Citation] = []
    for cite in response.citations:
        if cite.id in valid_ids:
            validated.append(cite)
    if not validated and chunks:
        validated = [
            Citation(source=chunks[0].doc_type, id=chunks[0].chunk_id, excerpt=chunks[0].excerpt[:200])
        ]
    if len(validated) < len(response.citations):
        return response.model_copy(
            update={
                "citations": validated,
                "confidence": "medium" if validated else "insufficient",
                "limitations": (response.limitations + " Some citations were removed as ungrounded.").strip(),
            }
        )
    return response


def build_grounded_response(chunks: list[EvidenceChunk], query: str) -> RAGResponse:
    if not chunks:
        return RAGResponse(
            answer="Insufficient evidence to answer this question. Please escalate to human review.",
            confidence="insufficient",
            citations=[],
            top_signals=[],
            recommended_action="human_review",
            limitations="No matching classification or signal data found.",
        )

    primary = chunks[0]
    tier = primary.content.get("tier", "Uncertain")
    top_signals_raw = primary.content.get("top_signals", [])
    top_signals = [
        SignalContribution(
            name=s.get("name", ""),
            value=s.get("value"),
            contribution=s.get("contribution"),
        )
        for s in top_signals_raw[:5]
        if isinstance(s, dict)
    ]

    citations = [
        Citation(source=c.doc_type, id=c.chunk_id, excerpt=c.excerpt[:200]) for c in chunks[:5]
    ]

    answer_parts = [f"Based on retrieved evidence for your query: {query[:100]}"]
    if "tier" in primary.content:
        answer_parts.append(
            f"The URL is classified as {primary.content['tier']} "
            f"(score={primary.content.get('mfa_score', 'n/a')}, "
            f"confidence={primary.content.get('confidence', 'n/a')})."
        )
    if primary.content.get("explanation"):
        answer_parts.append(primary.content["explanation"])

    action = _recommended_action(tier)
    confidence = _confidence_from_tier(tier, len(chunks))

    return RAGResponse(
        answer=" ".join(answer_parts),
        confidence=confidence,
        citations=citations,
        top_signals=top_signals,
        recommended_action=action,
        limitations="",
    )


def _recommended_action(tier: str) -> str:
    if tier == "MFA_High":
        return "block"
    if tier in {"MFA_Medium", "Uncertain"}:
        return "human_review"
    if tier == "Non_MFA":
        return "allow"
    return "recheck"


def _confidence_from_tier(tier: str, chunk_count: int) -> str:
    if chunk_count >= 3:
        return "high"
    if chunk_count >= 1:
        return "medium"
    return "low"
