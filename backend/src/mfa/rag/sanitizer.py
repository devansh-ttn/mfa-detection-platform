"""Input sanitizer for RAG queries — prompt injection defence."""

from __future__ import annotations

import re

_MAX_QUERY_LEN = 4000
_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.I),
    re.compile(r"system\s*:\s*", re.I),
    re.compile(r"<\s*/?\s*script", re.I),
)


def sanitize_query(query: str) -> str:
    cleaned = query.strip()[:_MAX_QUERY_LEN]
    for pattern in _INJECTION_PATTERNS:
        cleaned = pattern.sub("[filtered]", cleaned)
    return cleaned


def classify_intent(query: str) -> str:
    q = query.lower()
    if "similar" in q and "mfa" in q:
        return "similar_sites"
    if "changed" in q or "since last" in q:
        return "change_since_review"
    if "non-mfa" in q or "non mfa" in q or "not mfa" in q:
        return "non_mfa_evidence"
    if "signal" in q and ("contribut" in q or "top" in q):
        return "signal_attribution"
    if "why" in q or "marked" in q or "classified" in q:
        return "explain_classification"
    return "explain_classification"
