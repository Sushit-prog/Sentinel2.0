"""Deterministic pre-screen. Zero API cost. Decides how much model the input gets."""

import logging

from backend.modules.scamwatch.patterns import (
    AUTHORITY_IMPERSONATION_TERMS,
    SCAM_PATTERNS,
    URGENCY_PHRASES,
)
from backend.modules.scamwatch.schemas import (
    PrescreenResult,
    PrescreenSignals,
    Route,
    ScamType,
)

logger = logging.getLogger(__name__)

_SEVERITY_BASE = {"CRITICAL": 0.60, "HIGH": 0.45, "MEDIUM": 0.30}

_URL_MARKERS = ("http", "www.", ".com", ".in/", "click here", "bit.ly", "tinyurl")
_OTP_PHRASES = ("otp", "one time password", "verification code", "cvv", "upi pin")
_MONEY_PHRASES = (
    "transfer",
    "send money",
    "pay ",
    "processing fee",
    "registration fee",
    "deposit",
    "upi",
    "neft",
    "rtgs",
)


def _match_keywords(text_lower: str) -> tuple[ScamType | None, list[str], int]:
    best_type: ScamType | None = None
    best_hits: list[str] = []
    for key, data in SCAM_PATTERNS.items():
        hits = [kw for kw in data["keywords"] if kw.lower() in text_lower]
        if len(hits) > len(best_hits):
            best_type = ScamType(key)
            best_hits = hits
    return best_type, best_hits, len(best_hits)


def prescreen(text: str) -> PrescreenResult:
    text_lower = text.lower()

    matched_type, keyword_hits, hit_count = _match_keywords(text_lower)
    urgency_hits = [p for p in URGENCY_PHRASES if p.lower() in text_lower]
    authority_hits = [
        t for t in AUTHORITY_IMPERSONATION_TERMS if t.lower() in text_lower
    ]
    signals = PrescreenSignals(
        urgency_hits=urgency_hits[:5],
        authority_hits=authority_hits[:5],
        keyword_hits=keyword_hits[:5],
        has_url=any(m in text_lower for m in _URL_MARKERS),
        requests_otp=any(p in text_lower for p in _OTP_PHRASES),
        requests_money=any(p in text_lower for p in _MONEY_PHRASES),
    )

    base = (
        _SEVERITY_BASE.get(
            SCAM_PATTERNS.get(matched_type.value, {}).get("severity", ""), 0.0
        )
        if matched_type
        else 0.0
    )
    score = min(
        base
        + min(hit_count * 0.05, 0.15)
        + min(len(urgency_hits) * 0.04, 0.12)
        + min(len(authority_hits) * 0.03, 0.09)
        + (0.06 if signals.has_url else 0)
        + (0.10 if signals.requests_otp else 0)
        + (0.08 if signals.requests_money else 0),
        1.0,
    )

    high_signal = hit_count >= 2 or (
        hit_count >= 1 and (signals.requests_otp or signals.requests_money)
    )
    any_signal = (
        hit_count >= 1
        or urgency_hits
        or authority_hits
        or signals.requests_otp
        or signals.requests_money
    )

    if high_signal:
        route, reason = Route.STRONG, "multiple corroborating scam signals"
    elif any_signal:
        route, reason = Route.FAST, "weak or isolated signals need confirmation"
    else:
        route, reason = Route.RULES_ONLY, "no scam signals detected"

    logger.info(
        "prescreen route=%s score=%.2f type=%s", route.value, score, matched_type
    )
    return PrescreenResult(
        matched_type=matched_type,
        signals=signals,
        rule_score=round(score, 3),
        route=route,
        reason=reason,
    )


def rules_only_risk(score: float) -> tuple[str, float]:
    """Conservative bands for the zero-LLM path. Never claims CRITICAL
    without model confirmation."""
    if score >= 0.75:
        return "HIGH", score
    if score >= 0.40:
        return "MEDIUM", score
    return "LOW", min(score, 0.35)
