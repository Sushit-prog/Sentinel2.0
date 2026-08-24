"""Risk scoring engine for SCAMWatch."""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class RiskScorer:
    """
    Converts classifier signals into a numeric risk score.
    Score range: 0.0 (safe) to 1.0 (critical threat).
    """

    SEVERITY_BASE_SCORES = {
        "CRITICAL": 0.85,
        "HIGH": 0.65,
        "MEDIUM": 0.45,
        "LOW": 0.25,
    }

    def score(self, classification: Dict, llm_assessment: str) -> Dict:
        base_score = 0.1

        if classification["matched_scam_type"]:
            severity = classification["pattern_data"].get("severity", "LOW")
            base_score = self.SEVERITY_BASE_SCORES.get(severity, 0.25)

        keyword_boost = min(classification["keyword_match_count"] * 0.05, 0.20)
        urgency_boost = min(len(classification["urgency_signals"]) * 0.05, 0.15)
        authority_boost = min(len(classification["authority_signals"]) * 0.05, 0.10)
        url_boost = 0.05 if classification["has_url"] else 0.0
        otp_boost = 0.08 if classification["has_otp_request"] else 0.0
        money_boost = 0.08 if classification["has_money_request"] else 0.0

        llm_lower = llm_assessment.lower()
        llm_boost = 0.0
        if any(word in llm_lower for word in ["critical", "very high", "extremely"]):
            llm_boost = 0.10
        elif any(word in llm_lower for word in ["high risk", "dangerous", "scam"]):
            llm_boost = 0.07
        elif any(word in llm_lower for word in ["medium", "suspicious", "caution"]):
            llm_boost = 0.03
        elif any(word in llm_lower for word in ["low risk", "safe", "legitimate"]):
            llm_boost = -0.10

        final_score = min(
            base_score
            + keyword_boost
            + urgency_boost
            + authority_boost
            + url_boost
            + otp_boost
            + money_boost
            + llm_boost,
            1.0,
        )

        if final_score >= 0.80:
            risk_level = "CRITICAL"
        elif final_score >= 0.60:
            risk_level = "HIGH"
        elif final_score >= 0.35:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "risk_score": round(final_score, 3),
            "risk_level": risk_level,
            "score_breakdown": {
                "base": round(base_score, 3),
                "keyword_boost": round(keyword_boost, 3),
                "urgency_boost": round(urgency_boost, 3),
                "authority_boost": round(authority_boost, 3),
                "url_boost": round(url_boost, 3),
                "otp_boost": round(otp_boost, 3),
                "money_boost": round(money_boost, 3),
                "llm_boost": round(llm_boost, 3),
            },
        }
