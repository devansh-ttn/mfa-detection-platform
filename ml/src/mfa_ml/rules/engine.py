"""Rules engine v1 — deterministic high-confidence MFA patterns.

Applies before the XGBoost model.  URLs that match a rule skip the
ensemble and receive a fixed tier with high confidence.

Available crawl features (5 populated in POC):
    ad_to_content_ratio, ads_above_fold, ad_slots_count,
    sticky_ad_count, content_word_count

Refresh-based rules (refresh_events_60s, avg_refresh_interval_sec) are
deferred until 60s dwell is wired — TODO(MVP).

See docs/SIGNALS.md for feature definitions and null conventions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from mfa_ml.scoring.output import SignalContribution, Tier

logger = structlog.get_logger(__name__)


@dataclass
class RuleMatch:
    """Outcome of a single rule firing."""

    rule_id: str
    tier: Tier
    mfa_score: float
    top_signals: list[SignalContribution]
    explanation_hint: str


def _sig(feature: str, value: Any, contribution: float, rank: int) -> SignalContribution:
    return SignalContribution(
        feature=feature, value=value, contribution=contribution, rank=rank
    )


class RulesEngine:
    """Stateless rules engine.  Call ``evaluate`` for each URL.

    Rules are evaluated in priority order; the first match wins.
    A ``None`` return means no rule fired — pass the URL to XGBoost.
    """

    def evaluate(self, features: dict[str, Any]) -> RuleMatch | None:
        """Evaluate all rules against the extracted feature dict.

        Missing / null features are treated as not matching the condition
        rather than raising — the XGBoost model handles imputed nulls.

        Args:
            features: Flat dict of SignalFeatures field names → values.

        Returns:
            ``RuleMatch`` if a rule fires, ``None`` otherwise.
        """
        match = (
            self._r1_high_ad_density(features)
            or self._r2_ads_above_fold(features)
            or self._r3_thin_content_heavy_ads(features)
            or self._r4_clean_publisher(features)
        )
        if match:
            logger.debug(
                "rules_engine_match",
                rule_id=match.rule_id,
                tier=match.tier,
            )
        return match

    # ------------------------------------------------------------------
    # Individual rules
    # ------------------------------------------------------------------

    def _r1_high_ad_density(self, f: dict[str, Any]) -> RuleMatch | None:
        """R1 — Very high ad density + many ad slots → MFA_High.

        Condition: ad_to_content_ratio > 0.40 AND ad_slots_count >= 8
        """
        ratio = f.get("ad_to_content_ratio")
        slots = f.get("ad_slots_count")
        if ratio is None or slots is None:
            return None
        if ratio > 0.40 and slots >= 8:
            return RuleMatch(
                rule_id="R1",
                tier="MFA_High",
                mfa_score=0.92,
                top_signals=[
                    _sig("ad_to_content_ratio", ratio, 0.55, 1),
                    _sig("ad_slots_count", slots, 0.40, 2),
                ],
                explanation_hint=(
                    f"Extremely high ad-to-content ratio ({ratio:.2f}) with "
                    f"{slots} ad slots detected."
                ),
            )
        return None

    def _r2_ads_above_fold(self, f: dict[str, Any]) -> RuleMatch | None:
        """R2 — Multiple ads above the fold + elevated density → MFA_Medium.

        Condition: ads_above_fold >= 3 AND ad_to_content_ratio > 0.25
        """
        above_fold = f.get("ads_above_fold")
        ratio = f.get("ad_to_content_ratio")
        if above_fold is None or ratio is None:
            return None
        if above_fold >= 3 and ratio > 0.25:
            return RuleMatch(
                rule_id="R2",
                tier="MFA_Medium",
                mfa_score=0.68,
                top_signals=[
                    _sig("ads_above_fold", above_fold, 0.45, 1),
                    _sig("ad_to_content_ratio", ratio, 0.35, 2),
                ],
                explanation_hint=(
                    f"{above_fold} ads above the fold with "
                    f"ad density {ratio:.2f} suggests MFA layout."
                ),
            )
        return None

    def _r3_thin_content_heavy_ads(self, f: dict[str, Any]) -> RuleMatch | None:
        """R3 — Very thin content with many ad slots → MFA_High.

        Condition: content_word_count < 50 AND ad_slots_count >= 5
        """
        words = f.get("content_word_count")
        slots = f.get("ad_slots_count")
        if words is None or slots is None:
            return None
        if words < 50 and slots >= 5:
            return RuleMatch(
                rule_id="R3",
                tier="MFA_High",
                mfa_score=0.88,
                top_signals=[
                    _sig("content_word_count", words, 0.50, 1),
                    _sig("ad_slots_count", slots, 0.42, 2),
                ],
                explanation_hint=(
                    f"Sparse content ({words} words) with {slots} ad slots "
                    f"is a strong MFA signal."
                ),
            )
        return None

    def _r4_clean_publisher(self, f: dict[str, Any]) -> RuleMatch | None:
        """R4 — Low ad ratio with rich content → Non_MFA high-confidence.

        Condition: ad_to_content_ratio < 0.05 AND content_word_count > 500
        """
        ratio = f.get("ad_to_content_ratio")
        words = f.get("content_word_count")
        if ratio is None or words is None:
            return None
        if ratio < 0.05 and words > 500:
            return RuleMatch(
                rule_id="R4",
                tier="Non_MFA",
                mfa_score=0.06,
                top_signals=[
                    _sig("ad_to_content_ratio", ratio, -0.55, 1),
                    _sig("content_word_count", words, -0.40, 2),
                ],
                explanation_hint=(
                    f"Minimal ad density ({ratio:.3f}) and rich content "
                    f"({words} words) indicate a legitimate publisher."
                ),
            )
        return None
