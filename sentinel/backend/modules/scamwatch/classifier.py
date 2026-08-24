"""Scam pattern classifier for SCAMWatch."""

import logging
from typing import Dict
from backend.modules.scamwatch.patterns import (
    SCAM_PATTERNS,
    URGENCY_PHRASES,
    AUTHORITY_IMPERSONATION_TERMS,
)

logger = logging.getLogger(__name__)


class ScamClassifier:
    """
    Rule-based pre-classifier that runs before the LLM agent.
    Fast, deterministic, zero API cost.
    Identifies scam type and extracts signal features.
    """

    def classify(self, text: str) -> Dict:
        text_lower = text.lower()

        matched_type = None
        matched_keywords = []
        max_matches = 0

        for scam_type, pattern_data in SCAM_PATTERNS.items():
            matches = [
                kw for kw in pattern_data["keywords"] if kw.lower() in text_lower
            ]
            if len(matches) > max_matches:
                max_matches = len(matches)
                matched_type = scam_type
                matched_keywords = matches

        urgency_signals = [
            phrase for phrase in URGENCY_PHRASES if phrase.lower() in text_lower
        ]

        authority_signals = [
            term for term in AUTHORITY_IMPERSONATION_TERMS if term.lower() in text_lower
        ]

        has_url = any(
            indicator in text_lower
            for indicator in ["http", "www.", ".com", "click here", "link"]
        )

        has_otp_request = any(
            phrase in text_lower
            for phrase in ["otp", "one time password", "verification code", "pin"]
        )

        has_money_request = any(
            phrase in text_lower
            for phrase in [
                "transfer",
                "send money",
                "pay",
                "deposit",
                "upi",
                "neft",
                "rtgs",
                "wallet",
            ]
        )

        return {
            "matched_scam_type": matched_type,
            "matched_keywords": matched_keywords,
            "keyword_match_count": max_matches,
            "urgency_signals": urgency_signals,
            "authority_signals": authority_signals,
            "has_url": has_url,
            "has_otp_request": has_otp_request,
            "has_money_request": has_money_request,
            "pattern_data": SCAM_PATTERNS.get(matched_type, {}) if matched_type else {},
        }
