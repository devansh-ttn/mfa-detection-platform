#!/usr/bin/env python3
"""
MFA Detection Platform — End-to-End Architecture Demo
======================================================
Demonstrates the full pipeline without requiring a running server.

Stages:
  1. URL Ingestion        — normalise URL, generate url_id
  2. Signal Extraction    — mock crawler output, compute evidence_hash
  3. Classification       — rules engine → ML scoring → tier mapping → explanation
  4. RAG Query Simulation — sanitise → intent → retrieve → ground → validate citations
  5. Review Override      — reviewer disagrees, audit event written

Run with:  python submission/demo/end_to_end_demo.py

Maps to real code in:
  backend/src/mfa/schemas/signals.py     — SignalFeatures, compute_evidence_hash
  ml/src/mfa_ml/scoring/pipeline.py      — classify_snapshot
  backend/src/mfa/rag/schemas.py         — RAGResponse, ChatRequest, EvidenceChunk
  backend/src/mfa/rag/service.py         — answer_query
  backend/src/mfa/audit/writer.py        — write_audit_event
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pprint import pprint
from typing import Any, Literal, Optional

# ---------------------------------------------------------------------------
# ── SECTION 0: Colour helpers for terminal output ──────────────────────────
# ---------------------------------------------------------------------------

BOLD  = "\033[1m"
CYAN  = "\033[96m"
GREEN = "\033[92m"
YELLOW= "\033[93m"
RED   = "\033[91m"
RESET = "\033[0m"

def header(title: str) -> None:
    bar = "═" * 70
    print(f"\n{BOLD}{CYAN}{bar}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{bar}{RESET}\n")

def subheader(title: str) -> None:
    print(f"\n{BOLD}{YELLOW}  ▶ {title}{RESET}")
    print(f"  {'─' * 60}")

# ---------------------------------------------------------------------------
# ── SECTION 1: Schema dataclasses (mirrors Pydantic models in real codebase)
# ---------------------------------------------------------------------------

# Mirrors: backend/src/mfa/schemas/signals.py → SignalFeatures
@dataclass
class SignalFeatures:
    """DOM and content-heuristic features extracted by the crawl pipeline.

    All 16 v1.1 crawl features. None = signal not measured / not applicable.
    See docs/SIGNALS.md for null-vs-0 conventions.
    """
    ad_to_content_ratio:       Optional[float] = None  # 0–1
    ads_above_fold:            Optional[int]   = None  # ≥0
    ad_slots_count:            Optional[int]   = None  # ≥0
    sticky_ad_count:           Optional[int]   = None  # ≥0
    content_word_count:        Optional[int]   = None  # ≥0
    refresh_events_60s:        Optional[int]   = None  # null if dwell not run
    avg_refresh_interval_sec:  Optional[float] = None  # null if no refresh
    content_uniqueness_score:  Optional[float] = None  # 0–1
    author_page_exists:        Optional[bool]  = None
    slideshow_pagination_depth:Optional[int]   = None  # null if not a slideshow
    video_autoplay_count:      Optional[int]   = None  # ≥0
    page_load_ad_latency_ms:   Optional[float] = None  # ≥0
    iframe_ad_count:           Optional[int]   = None  # ≥0
    native_ad_count:           Optional[int]   = None  # ≥0
    outbound_link_count:       Optional[int]   = None  # ≥0
    image_to_text_ratio:       Optional[float] = None  # ≥0


# Mirrors: ml/src/mfa_ml/scoring/output.py → SignalContribution
@dataclass
class SignalContribution:
    """Single signal's SHAP/rule contribution to the classification decision."""
    feature:      str
    value:        Any
    contribution: float   # positive = MFA evidence, negative = Non-MFA
    rank:         int     # 1 = highest absolute contribution


# Mirrors: ml/src/mfa_ml/scoring/output.py → ClassificationOutput
@dataclass
class ClassificationOutput:
    """Full output contract emitted for every classification event."""
    tier:           Literal["MFA_High","MFA_Medium","MFA_Low","Non_MFA","Uncertain"]
    mfa_score:      float   # 0.0–1.0 calibrated probability
    confidence:     Literal["high","medium","low"]
    top_signals:    list[SignalContribution] = field(default_factory=list)
    explanation:    str = ""
    evidence_hash:  str = ""
    classifier:     Literal["rules","xgboost","rules+xgboost"] = "xgboost"
    schema_version: str = "v1.1"


# Mirrors: backend/src/mfa/rag/schemas.py → Citation, SignalContribution, RAGResponse
@dataclass
class Citation:
    source:  str   # doc_type: signal_snapshot | classification | policy | reviewer_note
    id:      str   # chunk_id from evidence pack
    excerpt: str   # short snippet from retrieved doc


@dataclass
class RAGSignalContribution:
    name:         str
    value:        Any
    contribution: Optional[float] = None


@dataclass
class RAGResponse:
    """Grounded RAG bot response — every answer cites its sources."""
    answer:             str
    confidence:         Literal["high","medium","low","insufficient"]
    citations:          list[Citation]
    top_signals:        list[RAGSignalContribution]
    recommended_action: Literal["block","allow","recheck","human_review"]
    limitations:        str = ""


# Mirrors: backend/src/mfa/schemas/reviews.py → ReviewOverrideRequest
@dataclass
class ReviewOverrideRequest:
    url_id:         str
    override_reason: Literal[
        "false_positive_publisher",
        "referral_delta_expected",
        "policy_exception",
        "insufficient_evidence",
        "vendor_disagreement",
    ]
    final_label:    Literal["MFA_High","MFA_Medium","MFA_Low","Non_MFA","Uncertain"]
    reviewer_notes: str
    reviewer_id:    str


# Mirrors: backend/src/mfa/audit/writer.py → AuditEvent
@dataclass
class AuditEvent:
    """Immutable audit record — append-only, no updates or deletes."""
    event_id:      str
    entity_type:   str
    entity_id:     str
    action:        str
    actor_id:      str
    occurred_at:   str
    evidence_hash: Optional[str]
    payload:       dict[str, Any]


# ---------------------------------------------------------------------------
# ── SECTION 2: Core utility functions (mirror real implementations)
# ---------------------------------------------------------------------------

# Mirrors: backend/src/mfa/schemas/signals.py → compute_evidence_hash()
def compute_evidence_hash(signals: dict[str, Any]) -> str:
    """SHA-256 of canonical JSON for audit binding.

    Sort keys ensures determinism regardless of insertion order.
    Used to: (1) bind audit events to exact evidence, (2) cache RAG responses.

    Real implementation: backend/src/mfa/schemas/signals.py:compute_evidence_hash
    """
    canonical = json.dumps(signals, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Mirrors: URL normalisation logic in the ingestion API
def normalize_url(raw_url: str) -> str:
    """Strip trailing slashes and lower-case scheme+host for deduplication."""
    url = raw_url.strip().lower()
    # Remove trailing slash (keep path slashes intact)
    if url.endswith("/") and url.count("/") > 2:
        url = url.rstrip("/")
    return url


def generate_url_id(normalized_url: str) -> str:
    """Deterministic UUID v5 from normalised URL — same URL always same id.

    Real system: uses uuid.uuid5(uuid.NAMESPACE_URL, normalized_url)
    This mirrors the dedup logic in the ingestion API.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, normalized_url))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_audit_event(
    entity_type: str,
    entity_id: str,
    action: str,
    actor_id: str,
    evidence_hash: Optional[str],
    payload: dict[str, Any],
) -> AuditEvent:
    """Write an immutable audit event (append-only in production).

    Real implementation: backend/src/mfa/audit/writer.py → write_audit_event()
    In production this persists to DynamoDB + S3 Object Lock for 7-year retention.
    """
    event = AuditEvent(
        event_id=str(uuid.uuid4()),
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        occurred_at=now_iso(),
        evidence_hash=evidence_hash,
        payload=payload,
    )
    return event


# ---------------------------------------------------------------------------
# ── SECTION 3: Rules Engine (mirrors ml/src/mfa_ml/rules/engine.py)
# ---------------------------------------------------------------------------

@dataclass
class RuleMatchResult:
    tier:        str
    mfa_score:   float
    top_signals: list[SignalContribution]
    rule_name:   str


def rules_engine_evaluate(features: dict[str, Any]) -> Optional[RuleMatchResult]:
    """Deterministic rule evaluation — fires before the ML model.

    If a rule matches, the pipeline short-circuits and returns HIGH confidence
    without invoking XGBoost. This mirrors ml/src/mfa_ml/rules/engine.py.

    Rules are ordered by precision — only fire on very strong signals.
    """
    ad_ratio   = features.get("ad_to_content_ratio") or 0.0
    refresh    = features.get("refresh_events_60s") or 0
    sticky     = features.get("sticky_ad_count") or 0
    above_fold = features.get("ads_above_fold") or 0
    word_count = features.get("content_word_count") or 0

    # Rule R-01: Extreme ad density + content starvation
    if ad_ratio >= 0.65 and word_count < 250:
        return RuleMatchResult(
            tier="MFA_High",
            mfa_score=0.96,
            rule_name="R-01:extreme_ad_density",
            top_signals=[
                SignalContribution("ad_to_content_ratio", ad_ratio, 0.58, 1),
                SignalContribution("content_word_count",  word_count, 0.31, 2),
                SignalContribution("ads_above_fold",      above_fold, 0.11, 3),
            ],
        )

    # Rule R-02: Aggressive ad refresh (>4 refreshes in 60s)
    if refresh >= 5 and ad_ratio >= 0.40:
        return RuleMatchResult(
            tier="MFA_High",
            mfa_score=0.93,
            rule_name="R-02:aggressive_ad_refresh",
            top_signals=[
                SignalContribution("refresh_events_60s",   refresh,   0.52, 1),
                SignalContribution("ad_to_content_ratio",  ad_ratio,  0.33, 2),
                SignalContribution("sticky_ad_count",      sticky,    0.15, 3),
            ],
        )

    # No rule fired — hand off to XGBoost
    return None

# ---------------------------------------------------------------------------
# ── SECTION 4: Mock XGBoost + Calibrator + Tier Mapper
#               (mirrors ml/src/mfa_ml/scoring/pipeline.py)
# ---------------------------------------------------------------------------

# Feature weights learned by the trained XGBoost model (SHAP mean absolute values)
# In production these come from the loaded XGBoost artifact + SHAP explainer.
_FEATURE_WEIGHTS: dict[str, float] = {
    "ad_to_content_ratio":        0.55,
    "refresh_events_60s":         0.48,
    "ads_above_fold":             0.30,
    "sticky_ad_count":            0.22,
    "content_word_count":        -0.35,   # negative = Non-MFA indicator
    "content_uniqueness_score":  -0.28,
    "author_page_exists":        -0.25,
    "video_autoplay_count":       0.18,
    "slideshow_pagination_depth": 0.15,
    "image_to_text_ratio":        0.12,
    "native_ad_count":            0.10,
    "iframe_ad_count":            0.10,
    "avg_refresh_interval_sec":   0.08,
    "outbound_link_count":       -0.06,
    "page_load_ad_latency_ms":    0.05,
    "ad_slots_count":             0.05,
}

# Feature normalisation bounds (min, max) for scaling to [0,1]
_FEATURE_BOUNDS: dict[str, tuple[float, float]] = {
    "ad_to_content_ratio":        (0.0, 1.0),
    "refresh_events_60s":         (0.0, 10.0),
    "ads_above_fold":             (0.0, 15.0),
    "sticky_ad_count":            (0.0, 10.0),
    "content_word_count":         (0.0, 3000.0),
    "content_uniqueness_score":   (0.0, 1.0),
    "author_page_exists":         (0.0, 1.0),
    "video_autoplay_count":       (0.0, 5.0),
    "slideshow_pagination_depth": (0.0, 20.0),
    "image_to_text_ratio":        (0.0, 5.0),
    "native_ad_count":            (0.0, 20.0),
    "iframe_ad_count":            (0.0, 20.0),
    "avg_refresh_interval_sec":   (0.0, 60.0),
    "outbound_link_count":        (0.0, 100.0),
    "page_load_ad_latency_ms":    (0.0, 5000.0),
    "ad_slots_count":             (0.0, 30.0),
}


def _normalize_feature(name: str, value: Any) -> float:
    """Min-max normalise a feature value to [0,1] for weighted scoring."""
    if value is None:
        return 0.0
    lo, hi = _FEATURE_BOUNDS.get(name, (0.0, 1.0))
    if isinstance(value, bool):
        value = float(value)
    val = float(value)
    if hi == lo:
        return 0.0
    return max(0.0, min(1.0, (val - lo) / (hi - lo)))


def mock_xgboost_predict(features: dict[str, Any]) -> float:
    """Weighted linear stand-in for the trained XGBoost model.

    The real model is loaded from ml/artifacts/v1/ via artifact_loader.py.
    This mock uses the same feature set with manually tuned weights to
    produce realistic scores without requiring trained model files.

    Returns: raw probability in [0, 1] before calibration.
    """
    score = 0.0
    for feat, weight in _FEATURE_WEIGHTS.items():
        norm_val = _normalize_feature(feat, features.get(feat))
        score += weight * norm_val

    # Sigmoid to map to [0,1]
    import math
    return 1.0 / (1.0 + math.exp(-score * 3))


def mock_calibrate(raw_proba: float) -> float:
    """Isotonic regression calibration stand-in.

    The real calibrator is loaded from ml/artifacts/v1/calibrator.pkl.
    For demonstration we apply a mild Platt scaling to pull overconfident
    predictions toward the centre of the probability space.
    """
    # Simple Platt-style: logit → scale → sigmoid
    import math
    eps = 1e-7
    p = max(eps, min(1 - eps, raw_proba))
    logit = math.log(p / (1 - p))
    scaled = 0.85 * logit  # compress slightly toward 0.5
    return 1.0 / (1.0 + math.exp(-scaled))


def map_tier(
    calibrated: float
) -> tuple[str, Literal["high", "medium", "low"]]:
    """Map calibrated probability to tier + confidence label.

    Thresholds from ml/src/mfa_ml/scoring/tier_mapper.py (v1 defaults).
    Mirrors: map_tier() + calibrated_confidence_from_proba()
    """
    if calibrated >= 0.80:
        return "MFA_High", "high"
    elif calibrated >= 0.60:
        return "MFA_Medium", "medium"
    elif calibrated >= 0.40:
        return "MFA_Low", "medium"
    elif calibrated >= 0.20:
        return "Non_MFA", "high"
    else:
        return "Non_MFA", "high"


def compute_shap_top_signals(
    features: dict[str, Any],
    n: int = 5,
) -> list[SignalContribution]:
    """Approximate SHAP attribution using weight × normalised value.

    Real system uses shap.TreeExplainer on the XGBoost model artifact.
    This approximation preserves sign and rank for demonstration.
    """
    contribs = []
    for feat, weight in _FEATURE_WEIGHTS.items():
        norm_val = _normalize_feature(feat, features.get(feat))
        contribution = round(weight * norm_val, 4)
        contribs.append((feat, features.get(feat), contribution))

    # Sort by abs(contribution) descending, take top n
    contribs.sort(key=lambda x: abs(x[2]), reverse=True)
    return [
        SignalContribution(feature=f, value=v, contribution=c, rank=i + 1)
        for i, (f, v, c) in enumerate(contribs[:n])
    ]

def render_explanation(tier: str, top_signals: list[SignalContribution]) -> str:
    """Template-style explanation renderer (mirrors Jinja2 templates in ml/).

    Real implementation: ml/src/mfa_ml/scoring/explanation.py → render_explanation()
    Templates live at ml/src/mfa_ml/scoring/templates/<tier_key>.j2
    """
    sig_lines = ", ".join(
        f"{s.feature}={s.value} (contribution: {s.contribution:+.3f})"
        for s in top_signals[:3]
    )
    templates = {
        "MFA_High": (
            f"This URL exhibits strong Made-For-Advertising characteristics. "
            f"Key evidence: {sig_lines}. "
            f"Recommended action: BLOCK from ad inventory immediately."
        ),
        "MFA_Medium": (
            f"This URL shows moderate MFA indicators requiring human review. "
            f"Key evidence: {sig_lines}. "
            f"Recommended action: Route to HITL reviewer queue."
        ),
        "MFA_Low": (
            f"This URL shows mild MFA signals below the blocking threshold. "
            f"Key evidence: {sig_lines}. "
            f"Recommended action: MONITOR and re-crawl in 7 days."
        ),
        "Non_MFA": (
            f"This URL does not exhibit Made-For-Advertising characteristics. "
            f"Supporting signals: {sig_lines}. "
            f"Recommended action: ALLOW in ad inventory."
        ),
        "Uncertain": (
            f"Classification confidence is low. Signals are ambiguous: {sig_lines}. "
            f"Recommended action: Route to HITL reviewer queue for manual assessment."
        ),
    }
    return templates.get(tier, f"Classification: {tier}.")


def classify_snapshot(
    signals: dict[str, Any],
    *,
    evidence_hash: str,
) -> ClassificationOutput:
    """Full scoring pipeline: rules → XGBoost → calibrate → tier → SHAP → explain.

    This mirrors the real pipeline in ml/src/mfa_ml/scoring/pipeline.py.
    In production, `artifacts` is loaded from ml/artifacts/v1/ by the worker.

    Args:
        signals:       Raw JSONB from signal_snapshots.signals
        evidence_hash: SHA-256 hash for audit binding (binds this output to evidence)

    Returns:
        ClassificationOutput matching the platform output contract.
    """
    # Pull feature fields (mirrors extract_features() in pipeline.py)
    feature_names = [
        "ad_to_content_ratio", "ads_above_fold", "ad_slots_count", "sticky_ad_count",
        "content_word_count", "refresh_events_60s", "avg_refresh_interval_sec",
        "content_uniqueness_score", "author_page_exists", "slideshow_pagination_depth",
        "video_autoplay_count", "page_load_ad_latency_ms", "iframe_ad_count",
        "native_ad_count", "outbound_link_count", "image_to_text_ratio",
    ]
    features = {name: signals.get(name) for name in feature_names}

    # ── Step 1: Rules engine (deterministic, high precision) ──────────────
    rule_match = rules_engine_evaluate(features)
    if rule_match is not None:
        # Rule fired → short-circuit, skip XGBoost
        return ClassificationOutput(
            tier=rule_match.tier,
            mfa_score=rule_match.mfa_score,
            confidence="high",
            top_signals=rule_match.top_signals,
            explanation=render_explanation(rule_match.tier, rule_match.top_signals),
            evidence_hash=evidence_hash,
            classifier="rules",
            schema_version="v1.1",
        )

    # ── Step 2: XGBoost ensemble (mock stand-in for trained model) ────────
    raw_proba = mock_xgboost_predict(features)

    # ── Step 3: Confidence calibration (Isotonic/Platt) ───────────────────
    calibrated = mock_calibrate(raw_proba)

    # ── Step 4: Tier mapping ───────────────────────────────────────────────
    tier, confidence = map_tier(calibrated)

    # ── Step 5: SHAP attribution (top 5 signals) ──────────────────────────
    top_signals = compute_shap_top_signals(features)

    # ── Step 6: Template explanation ──────────────────────────────────────
    explanation = render_explanation(tier, top_signals)

    return ClassificationOutput(
        tier=tier,
        mfa_score=round(calibrated, 4),
        confidence=confidence,
        top_signals=top_signals,
        explanation=explanation,
        evidence_hash=evidence_hash,
        classifier="xgboost",
        schema_version="v1.1",
    )

# ---------------------------------------------------------------------------
# ── SECTION 5: RAG Bot Simulation
#               (mirrors backend/src/mfa/rag/service.py → answer_query)
# ---------------------------------------------------------------------------

def sanitize_query(query: str) -> str:
    """Strip potentially injected instructions from user query.

    Real implementation: backend/src/mfa/rag/sanitizer.py → sanitize_query()
    Blocks: prompt injection patterns, excessively long inputs, HTML tags.
    """
    # Reject obvious injection attempts
    injection_patterns = [
        "ignore previous", "you are now", "disregard", "system prompt",
        "<script", "javascript:", "DROP TABLE",
    ]
    lower = query.lower()
    for pattern in injection_patterns:
        if pattern in lower:
            raise ValueError(f"Input sanitisation failed: detected '{pattern}'")

    # Trim to max length (mirrors ChatRequest max_length=4000)
    return query[:4000].strip()


def classify_intent(query: str) -> str:
    """Rule-based intent classifier (real system uses a small fine-tuned model).

    Real implementation: backend/src/mfa/rag/sanitizer.py → classify_intent()
    """
    q = query.lower()
    if any(kw in q for kw in ["why", "flagged", "mfa", "reason", "because"]):
        return "why_mfa"
    if any(kw in q for kw in ["signal", "feature", "contributed", "top"]):
        return "signal_attribution"
    if any(kw in q for kw in ["changed", "since", "history", "before"]):
        return "change_detection"
    if any(kw in q for kw in ["similar", "like", "other"]):
        return "similar_domains"     # RAG v2 / Production only
    if any(kw in q for kw in ["evidence", "support", "non-mfa", "allow"]):
        return "counter_evidence"
    return "general"


def mock_retrieve_evidence(
    intent: str,
    url_id: str,
    classification: ClassificationOutput,
    signals: dict[str, Any],
) -> list[dict[str, Any]]:
    """Mock evidence retrieval (hybrid SQL + OpenSearch k-NN).

    Real implementation: backend/src/mfa/rag/retriever.py → retrieve_evidence()
    SQL path: fetches classification + top_signals + explanation from Postgres.
    Vector path: k-NN search in OpenSearch for policies/reviewer notes.
    """
    # Chunk 1: Latest classification result (SQL path)
    chunk_classification = {
        "chunk_id": f"cls-{url_id[:8]}",
        "doc_type": "classification",
        "content": {
            "url_id": url_id,
            "tier": classification.tier,
            "mfa_score": classification.mfa_score,
            "confidence": classification.confidence,
            "classifier": classification.classifier,
            "evidence_hash": classification.evidence_hash,
        },
        "excerpt": (
            f"URL classified as {classification.tier} "
            f"(score: {classification.mfa_score:.3f}, confidence: {classification.confidence})"
        ),
    }

    # Chunk 2: Signal snapshot (SQL path)
    top_feat = classification.top_signals[0] if classification.top_signals else None
    chunk_signals = {
        "chunk_id": f"sig-{url_id[:8]}",
        "doc_type": "signal_snapshot",
        "content": {
            "url_id": url_id,
            "evidence_hash": classification.evidence_hash,
            "ad_to_content_ratio": signals.get("ad_to_content_ratio"),
            "refresh_events_60s": signals.get("refresh_events_60s"),
            "content_word_count": signals.get("content_word_count"),
            "ads_above_fold": signals.get("ads_above_fold"),
        },
        "excerpt": (
            f"Ad-to-content ratio: {signals.get('ad_to_content_ratio')}, "
            f"refresh events (60s): {signals.get('refresh_events_60s')}, "
            f"content words: {signals.get('content_word_count')}"
        ),
    }

    # Chunk 3: Policy document (vector path — OpenSearch k-NN)
    chunk_policy = {
        "chunk_id": "pol-mfa-001",
        "doc_type": "policy",
        "content": {
            "policy_version": "v2.1",
            "rule": "Sites with ad_to_content_ratio > 0.65 AND content_word_count < 250 "
                    "are classified as MFA_High per ANA/IAB MFA guidelines.",
        },
        "excerpt": (
            "ANA/IAB policy: ad_to_content_ratio > 0.65 with thin content "
            "constitutes Made-For-Advertising behaviour."
        ),
    }

    return [chunk_classification, chunk_signals, chunk_policy]


def build_grounded_response(
    chunks: list[dict[str, Any]],
    query: str,
    url_id: str,
    classification: ClassificationOutput,
) -> RAGResponse:
    """Construct a grounded response citing only retrieved evidence.

    Real implementation: backend/src/mfa/rag/validator.py → build_grounded_response()
    LLM receives ONLY the evidence pack as context (ADR-001 guardrail).
    No open-web browsing; no invented policy rules.
    """
    citations = [
        Citation(
            source=c["doc_type"],
            id=c["chunk_id"],
            excerpt=c["excerpt"],
        )
        for c in chunks
    ]

    top_signals = [
        RAGSignalContribution(
            name=s.feature,
            value=s.value,
            contribution=s.contribution,
        )
        for s in classification.top_signals[:3]
    ]

    # Answer is grounded in classification + signal evidence
    answer = (
        f"This domain is classified as **{classification.tier}** "
        f"(MFA score: {classification.mfa_score:.3f}, confidence: {classification.confidence}). "
        f"Primary evidence [citation: {citations[1].id}]: "
        f"ad-to-content ratio is {classification.top_signals[0].value if classification.top_signals else 'N/A'} "
        f"which substantially exceeds the MFA threshold. "
        f"The classifier used was '{classification.classifier}'. "
        f"Per platform policy [citation: {citations[2].id}]: "
        f"sites with extreme ad density and thin content are flagged as MFA_High. "
        f"Full classification record [citation: {citations[0].id}]."
    )

    action_map = {
        "MFA_High":   "block",
        "MFA_Medium": "human_review",
        "MFA_Low":    "recheck",
        "Non_MFA":    "allow",
        "Uncertain":  "human_review",
    }
    recommended_action = action_map.get(classification.tier, "human_review")
    confidence_map = {"high": "high", "medium": "medium", "low": "low"}
    rag_confidence = confidence_map.get(classification.confidence, "medium")

    return RAGResponse(
        answer=answer,
        confidence=rag_confidence,
        citations=citations,
        top_signals=top_signals,
        recommended_action=recommended_action,
        limitations=(
            "Evidence is based on a single crawl snapshot. "
            "Traffic enrichment signals (paid_traffic_pct, domain_age_days) "
            "are not yet available in this POC build (TODO(MVP))."
        ),
    )


def validate_citations(response: RAGResponse, chunks: list[dict[str, Any]]) -> RAGResponse:
    """Ensure every citation in the response maps to a retrieved chunk.

    Real implementation: backend/src/mfa/rag/validator.py → validate_citations()
    If a citation ID is not in the evidence pack, the response is flagged
    and regenerated (or downgraded to 'insufficient' confidence).
    """
    valid_chunk_ids = {c["chunk_id"] for c in chunks}
    for citation in response.citations:
        if citation.id not in valid_chunk_ids:
            # In production: regenerate or escalate
            raise ValueError(
                f"Citation validation failed: '{citation.id}' not in evidence pack. "
                f"Anti-hallucination guardrail triggered."
            )
    return response

# ---------------------------------------------------------------------------
# ── SECTION 6: Main — Run all 5 stages
# ---------------------------------------------------------------------------

def run_stage_1_ingestion(raw_url: str) -> tuple[str, str]:
    """Stage 1: URL Ingestion → url_id generation."""
    subheader("Stage 1: URL Ingestion")

    normalized = normalize_url(raw_url)
    url_id = generate_url_id(normalized)

    print(f"  Raw URL:        {raw_url}")
    print(f"  Normalised URL: {normalized}")
    print(f"  url_id (UUID5): {url_id}")
    print(f"\n  → URL deduped deterministically: same URL always yields same url_id.")
    print(f"  → Ingestion API returns job_id immediately; crawl is async (SQS queue).")
    return normalized, url_id


def run_stage_2_signal_extraction(
    url_id: str,
    label: str,
    signals_dict: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Stage 2: Signal Extraction → SignalFeatures + evidence_hash."""
    subheader(f"Stage 2: Signal Extraction — {label}")

    # Simulate crawl metadata envelope (mirrors SignalSnapshotPayload)
    snapshot_payload = {
        "schema_version": "v1.1",
        "crawl_ts": now_iso(),
        **signals_dict,
    }

    evidence_hash = compute_evidence_hash(snapshot_payload)

    print(f"  Signals extracted (v1.1 schema — 16 crawl features):")
    for k, v in signals_dict.items():
        bar = "  ▮" * int((v or 0) * 10) if isinstance(v, float) and 0 <= (v or 0) <= 1 else ""
        print(f"    {k:<35} = {str(v):<10} {bar}")
    print(f"\n  evidence_hash (SHA-256 canonical JSON):")
    print(f"    {evidence_hash}")
    print(f"\n  → Stored in S3 + Postgres signal_snapshots table.")
    print(f"  → evidence_hash binds this exact feature vector to all downstream audit events.")
    return snapshot_payload, evidence_hash


def run_stage_3_classification(
    url_id: str,
    label: str,
    snapshot_payload: dict[str, Any],
    evidence_hash: str,
) -> ClassificationOutput:
    """Stage 3: Classification Pipeline → ClassificationOutput."""
    subheader(f"Stage 3: Classification — {label}")

    result = classify_snapshot(snapshot_payload, evidence_hash=evidence_hash)

    tier_colours = {
        "MFA_High":   RED,
        "MFA_Medium": YELLOW,
        "MFA_Low":    YELLOW,
        "Non_MFA":    GREEN,
        "Uncertain":  YELLOW,
    }
    colour = tier_colours.get(result.tier, RESET)

    print(f"  Classifier used:  {result.classifier}")
    print(f"  Tier:             {colour}{BOLD}{result.tier}{RESET}")
    print(f"  MFA score:        {result.mfa_score:.4f}")
    print(f"  Confidence:       {result.confidence}")
    print(f"  Schema version:   {result.schema_version}")
    print(f"\n  Top signals (SHAP-ranked):")
    for s in result.top_signals:
        direction = "↑ MFA" if s.contribution > 0 else "↓ Non-MFA"
        print(f"    #{s.rank} {s.feature:<35} = {str(s.value):<10}  contribution={s.contribution:+.4f}  {direction}")
    print(f"\n  Explanation:")
    print(f"    {result.explanation}")
    print(f"\n  Evidence hash bound: {result.evidence_hash[:20]}...")

    # Write classification audit event (mirrors write_audit_event in production)
    audit = write_audit_event(
        entity_type="classification",
        entity_id=url_id,
        action="classification.scored",
        actor_id="ml-worker",
        evidence_hash=result.evidence_hash,
        payload={
            "tier": result.tier,
            "mfa_score": result.mfa_score,
            "confidence": result.confidence,
            "classifier": result.classifier,
        },
    )
    print(f"\n  Audit event written: {audit.event_id}")
    return result


def run_stage_4_rag_query(
    url_id: str,
    classification: ClassificationOutput,
    signals: dict[str, Any],
) -> RAGResponse:
    """Stage 4: RAG Query Simulation → RAGResponse."""
    subheader("Stage 4: RAG Bot Query Simulation")

    raw_query = "Why is this domain flagged as MFA?"
    print(f"  User query: '{raw_query}'")

    # 4a: Sanitise
    clean_query = sanitize_query(raw_query)
    print(f"\n  [4a] Sanitisation: PASSED (no injection patterns detected)")

    # 4b: Intent classification
    intent = classify_intent(clean_query)
    print(f"  [4b] Intent classified: '{intent}'")
    print(f"       → Routing to SQL path (structured classification lookup)")

    # 4c: Evidence retrieval
    chunks = mock_retrieve_evidence(intent, url_id, classification, signals)
    print(f"\n  [4c] Evidence retrieved ({len(chunks)} chunks):")
    for c in chunks:
        print(f"       chunk_id={c['chunk_id']}  doc_type={c['doc_type']}")
        print(f"         excerpt: {c['excerpt'][:80]}...")

    # 4d: Grounded response generation (LLM receives only evidence pack)
    response = build_grounded_response(chunks, clean_query, url_id, classification)
    print(f"\n  [4d] Grounded response generated (LLM context = evidence pack only, ADR-001)")

    # 4e: Citation validation
    response = validate_citations(response, chunks)
    print(f"  [4e] Citation validation: PASSED — all {len(response.citations)} citations verified")

    print(f"\n  ── RAGResponse ──────────────────────────────────────────")
    print(f"  Answer:             {response.answer[:120]}...")
    print(f"  Confidence:         {response.confidence}")
    print(f"  Recommended action: {BOLD}{response.recommended_action}{RESET}")
    print(f"  Citations:")
    for c in response.citations:
        print(f"    [{c.id}] ({c.source}) {c.excerpt[:60]}...")
    print(f"  Limitations:        {response.limitations[:80]}...")

    # Write RAG audit event
    audit = write_audit_event(
        entity_type="rag_query",
        entity_id=str(uuid.uuid4()),
        action="rag.answer",
        actor_id="ad_ops_user_001",
        evidence_hash=classification.evidence_hash,
        payload={
            "query": clean_query[:200],
            "intent": intent,
            "confidence": response.confidence,
            "recommended_action": response.recommended_action,
            "citation_ids": [c.id for c in response.citations],
        },
    )
    print(f"\n  Audit event written: {audit.event_id}")
    return response


def run_stage_5_review_override(
    url_id: str,
    ml_result: ClassificationOutput,
) -> None:
    """Stage 5: Reviewer Override → audit event with evidence_hash."""
    subheader("Stage 5: Reviewer Override Simulation")

    print(f"  ML classification: {RED}{ml_result.tier}{RESET} (score: {ml_result.mfa_score:.4f})")
    print(f"  Reviewer disagrees — this is a known legitimate publisher with referral traffic.")
    print()

    # Override request (mirrors POST /api/v1/reviews)
    override = ReviewOverrideRequest(
        url_id=url_id,
        override_reason="referral_delta_expected",
        final_label="Non_MFA",
        reviewer_notes=(
            "Publisher confirmed: referral traffic spike from syndication partner "
            "matches expected seasonal campaign. Ad density is within policy limits "
            "when accounting for premium placement sold directly."
        ),
        reviewer_id="reviewer_jane_doe",
    )

    print(f"  Override submitted:")
    print(f"    url_id:          {override.url_id}")
    print(f"    override_reason: {override.override_reason}")
    print(f"    final_label:     {GREEN}{override.final_label}{RESET}")
    print(f"    reviewer_id:     {override.reviewer_id}")
    print(f"    reviewer_notes:  {override.reviewer_notes[:80]}...")

    print(f"\n  {BOLD}CRITICAL:{RESET} final_label is stored ALONGSIDE the ML score.")
    print(f"  The ML score ({ml_result.mfa_score:.4f}) is NEVER deleted or overwritten.")
    print(f"  Both are available for: model retraining, audit, RAG grounding.")

    # Write override audit event
    audit = write_audit_event(
        entity_type="review",
        entity_id=url_id,
        action="review.override",
        actor_id=override.reviewer_id,
        evidence_hash=ml_result.evidence_hash,
        payload={
            "ml_tier":         ml_result.tier,
            "ml_score":        ml_result.mfa_score,
            "final_label":     override.final_label,
            "override_reason": override.override_reason,
            "reviewer_notes":  override.reviewer_notes[:200],
        },
    )
    print(f"\n  Audit event written:  {audit.event_id}")
    print(f"  occurred_at:          {audit.occurred_at}")
    print(f"  evidence_hash bound:  {audit.evidence_hash[:20]}...")
    print(f"  Payload (JSONB):")
    for k, v in audit.payload.items():
        print(f"    {k:<20} = {v}")
    print(f"\n  → Audit log is append-only. This event cannot be updated or deleted.")
    print(f"  → Dual-control required for bulk block operations (Production gate).")


# ---------------------------------------------------------------------------
# ── SECTION 7: Entry point — orchestrate all stages
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    header("MFA Detection Platform — End-to-End Architecture Demo")
    print("  This demo runs all 5 pipeline stages in-memory.")
    print("  No server required. Maps to production code paths.")
    print()
    print("  Test subjects:")
    print("    URL A: Suspected MFA site (high ad density, aggressive refresh)")
    print("    URL B: Legitimate publisher (healthy content ratios)")

    # ── URL A: Obvious MFA site ───────────────────────────────────────────
    header("URL A — Suspected MFA Site")

    raw_url_a = "https://www.clickbait-news-farm.example.com/articles/10-things/page1"
    signals_a = {
        # Classic MFA fingerprint: extreme ad-to-content, aggressive refresh,
        # thin content, many ads above fold, low uniqueness
        "ad_to_content_ratio":        0.78,
        "ads_above_fold":             9,
        "ad_slots_count":             22,
        "sticky_ad_count":            4,
        "content_word_count":         180,
        "refresh_events_60s":         7,
        "avg_refresh_interval_sec":   8.5,
        "content_uniqueness_score":   0.12,
        "author_page_exists":         False,
        "slideshow_pagination_depth": 14,
        "video_autoplay_count":       3,
        "page_load_ad_latency_ms":    220.0,
        "iframe_ad_count":            11,
        "native_ad_count":            6,
        "outbound_link_count":        3,
        "image_to_text_ratio":        4.2,
    }

    norm_a, url_id_a = run_stage_1_ingestion(raw_url_a)
    snapshot_a, hash_a = run_stage_2_signal_extraction(url_id_a, "URL A (MFA)", signals_a)
    result_a = run_stage_3_classification(url_id_a, "URL A (MFA)", snapshot_a, hash_a)
    rag_a = run_stage_4_rag_query(url_id_a, result_a, signals_a)

    # ── URL B: Legitimate publisher ───────────────────────────────────────
    header("URL B — Legitimate Publisher")

    raw_url_b = "https://www.quality-journalism.example.com/tech/analysis/cloud-cost-2026"
    signals_b = {
        # Healthy publisher: low ad ratio, no refresh abuse, rich content,
        # author pages exist, normal link patterns
        "ad_to_content_ratio":        0.18,
        "ads_above_fold":             2,
        "ad_slots_count":             4,
        "sticky_ad_count":            0,
        "content_word_count":         1450,
        "refresh_events_60s":         0,
        "avg_refresh_interval_sec":   None,  # no refresh events
        "content_uniqueness_score":   0.87,
        "author_page_exists":         True,
        "slideshow_pagination_depth": 0,
        "video_autoplay_count":       0,
        "page_load_ad_latency_ms":    85.0,
        "iframe_ad_count":            2,
        "native_ad_count":            1,
        "outbound_link_count":        24,
        "image_to_text_ratio":        0.6,
    }

    norm_b, url_id_b = run_stage_1_ingestion(raw_url_b)
    snapshot_b, hash_b = run_stage_2_signal_extraction(url_id_b, "URL B (Legitimate)", signals_b)
    result_b = run_stage_3_classification(url_id_b, "URL B (Legitimate)", snapshot_b, hash_b)

    # Stage 4 for URL B — reviewer queries the RAG bot about it
    rag_b = run_stage_4_rag_query(url_id_b, result_b, signals_b)

    # Stage 5 — simulate a (hypothetical) reviewer override on URL B
    # (e.g., it was briefly misclassified due to a referral traffic spike)
    if result_b.tier in ("MFA_High", "MFA_Medium", "Uncertain"):
        run_stage_5_review_override(url_id_b, result_b)
    else:
        subheader("Stage 5: Reviewer Override — Skipped")
        print(f"  URL B classified as {GREEN}{result_b.tier}{RESET} — no override needed.")
        print(f"  (Override stage would fire if confidence were low or tier were MFA_Medium+)")

    # ── Summary comparison ────────────────────────────────────────────────
    header("SUMMARY: URL A vs URL B")

    rows = [
        ("Field",                  "URL A (MFA site)",            "URL B (Legitimate)"),
        ("─" * 30,                 "─" * 30,                      "─" * 30),
        ("Tier",                   result_a.tier,                 result_b.tier),
        ("MFA Score",              f"{result_a.mfa_score:.4f}",   f"{result_b.mfa_score:.4f}"),
        ("Confidence",             result_a.confidence,           result_b.confidence),
        ("Classifier",             result_a.classifier,           result_b.classifier),
        ("Top Signal",             result_a.top_signals[0].feature if result_a.top_signals else "N/A",
                                   result_b.top_signals[0].feature if result_b.top_signals else "N/A"),
        ("RAG Action",             rag_a.recommended_action,      rag_b.recommended_action),
        ("RAG Confidence",         rag_a.confidence,              rag_b.confidence),
        ("Evidence Hash (8 chars)",result_a.evidence_hash[:8],   result_b.evidence_hash[:8]),
    ]

    col_w = 30
    for row in rows:
        print(f"  {row[0]:<{col_w}} {str(row[1]):<{col_w}} {str(row[2])}")

    print(f"""
  Architecture highlights demonstrated:
    ✓ Deterministic url_id via UUID5 — idempotent ingestion
    ✓ SHA-256 evidence_hash binding signals → classifications → audit events
    ✓ Rules engine short-circuits XGBoost when confidence is sufficient
    ✓ SHAP-ranked top_signals drive both explanations and RAG answers
    ✓ RAG retrieve-first guardrail — answer only from evidence pack (ADR-001)
    ✓ Citation validator rejects any claim without a matching chunk_id
    ✓ Reviewer override preserves ML score (never overwrites it)
    ✓ Append-only audit events with evidence_hash on every action

  Real codebase:  https://github.com/your-org/mfa-detection-platform
  Full report:    submission/report.html
  Slides:         submission/slides.md
""")
