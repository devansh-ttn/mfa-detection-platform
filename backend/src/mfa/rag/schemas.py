"""RAG response schemas per docs/RAG.md."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RAGConfidence = Literal["high", "medium", "low", "insufficient"]
RecommendedAction = Literal["block", "allow", "recheck", "human_review"]


class Citation(BaseModel):
    source: str
    id: str
    excerpt: str


class SignalContribution(BaseModel):
    name: str
    value: float | int | bool | None = None
    contribution: float | None = None


class RAGResponse(BaseModel):
    answer: str
    confidence: RAGConfidence
    citations: list[Citation]
    top_signals: list[SignalContribution]
    recommended_action: RecommendedAction
    limitations: str = ""


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    url_id: str | None = None
    domain: str | None = None


class EvidenceChunk(BaseModel):
    chunk_id: str
    doc_type: str
    content: dict[str, Any]
    excerpt: str
