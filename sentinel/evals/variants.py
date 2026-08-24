"""Pipeline variants compared by the benchmark.

rules_only      - prescreen thresholds, zero model calls
single_prompt   - one raw LLM verdict call (naive baseline)
hybrid_noverify - full pipeline without verification sampling
hybrid_full     - the shipped pipeline (extraction + evidence + verification)
"""

import time

from sqlalchemy.orm import Session

from backend.core.llm import Route, get_llm_client
from backend.modules.scamwatch.pipeline import ScamPipeline
from backend.modules.scamwatch.prescreen import prescreen
from backend.modules.scamwatch.schemas import RiskLevel


def _predict_from_risk(risk: str) -> tuple[int, float]:
    score_map = {"CRITICAL": 0.9, "HIGH": 0.7, "MEDIUM": 0.45, "LOW": 0.15}
    score = score_map.get(risk, 0.2)
    return (1 if risk in ("HIGH", "CRITICAL") else 0), score


def run_rules_only(text: str, session: Session | None = None) -> dict:
    started = time.monotonic()
    pre = prescreen(text)
    level = (
        "HIGH"
        if pre.rule_score >= 0.75
        else ("MEDIUM" if pre.rule_score >= 0.40 else "LOW")
    )
    predicted, score = _predict_from_risk(level)
    return {
        "predicted": predicted,
        "score": score,
        "latency_ms": int((time.monotonic() - started) * 1000),
        "cost_usd": 0.0,
        "calls": 0,
    }


def run_single_prompt(text: str, session: Session) -> dict:
    from backend.modules.scamwatch.schemas import Verdict

    client = get_llm_client()
    started = time.monotonic()
    try:
        result = client.complete(
            f"Is this message a scam? Answer with JSON fields is_scam (bool), confidence (0-1).\nMESSAGE:\n{text[:3000]}",
            system="You are a fraud detector. Reply only with JSON.",
            route=Route.STRONG,
            json_mode=True,
            temperature=0.1,
            max_tokens=200,
        )
        import json as _json

        data = _json.loads(
            result.text[result.text.find("{") : result.text.rfind("}") + 1]
        )
        predicted = 1 if data.get("is_scam") else 0
        score = float(data.get("confidence", 0.5))
        cost = result.usage.est_cost_usd
        latency = int((time.monotonic() - started) * 1000)
        return {
            "predicted": predicted,
            "score": score,
            "latency_ms": latency,
            "cost_usd": round(cost, 6),
            "calls": 1,
        }
    except Exception as exc:
        # honest reporting: a rules fallback is NOT a model measurement
        fallback = run_rules_only(text)
        return {**fallback, "fallback_reason": type(exc).__name__}


def run_hybrid(text: str, session: Session, verify: bool = True) -> dict:
    from backend.core.config import Settings

    settings = Settings(
        groq_api_key="unused",
        app_env="test",
        database_url="sqlite:///:memory:",
        llm_verification_samples=3 if verify else 0,
    )
    pipeline = ScamPipeline(settings=settings)
    response = pipeline.analyze(
        # variant tag in channel keeps digests distinct so hybrid_full
        # never replays hybrid_noverify's stored case during benchmarks
        text=text,
        channel=f"eval-{('noverify' if not verify else 'full')}",
        language="en",
        session=session,
    )
    predicted = 1 if response.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL) else 0
    score = response.risk_score if predicted else min(response.risk_score, 0.49)
    return {
        "predicted": predicted,
        "score": score,
        "confidence": response.confidence,
        "degraded": response.degraded,
        "needs_review": response.verification.needs_review,
        "latency_ms": response.latency_ms,
        "cost_usd": round(sum(u.est_cost_usd for u in response.usage), 6),
        "calls": len([u for u in response.usage]),
    }


VARIANTS = {
    "rules_only": run_rules_only,
    "single_prompt": run_single_prompt,
    "hybrid_noverify": lambda text, session: run_hybrid(text, session, verify=False),
    "hybrid_full": lambda text, session: run_hybrid(text, session, verify=True),
}
