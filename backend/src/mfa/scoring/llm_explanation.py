"""LLM explanation generator with template fallback (MVP-2.4, ADR-001)."""

from __future__ import annotations

import json
import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def generate_llm_explanation(
    *,
    tier: str,
    mfa_score: float,
    top_signals: list[dict[str, Any]],
    signals_snapshot: dict[str, Any],
    template_explanation: str,
) -> str:
    """Generate explanation citing signals only. Falls back to template when LLM unavailable."""
    if not os.getenv("BEDROCK_ENABLED", "").lower() in {"1", "true", "yes"}:
        return template_explanation

    try:
        return _bedrock_explain(
            tier=tier,
            mfa_score=mfa_score,
            top_signals=top_signals,
            signals_snapshot=signals_snapshot,
        )
    except Exception:
        logger.warning("llm_explanation_fallback", tier=tier)
        return template_explanation


def _bedrock_explain(
    *,
    tier: str,
    mfa_score: float,
    top_signals: list[dict[str, Any]],
    signals_snapshot: dict[str, Any],
) -> str:
    import boto3

    client = boto3.client(
        "bedrock-runtime",
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )
    evidence = {
        "tier": tier,
        "mfa_score": mfa_score,
        "top_signals": top_signals,
        "signals": signals_snapshot,
    }
    prompt = (
        "You are an MFA detection analyst. Explain the classification using ONLY "
        "the JSON evidence below. Cite signal names and values. Do not invent facts.\n\n"
        f"Evidence:\n{json.dumps(evidence, default=str)[:6000]}"
    )
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 512,
            "messages": [{"role": "user", "content": prompt}],
        }
    )
    response = client.invoke_model(modelId=model_id, body=body)
    payload = json.loads(response["body"].read())
    content = payload.get("content", [])
    if content and isinstance(content[0], dict):
        return str(content[0].get("text", ""))
    return str(payload)
