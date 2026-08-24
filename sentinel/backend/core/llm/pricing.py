"""Estimated token pricing (USD per 1M tokens, Groq published list prices).

Figures are for cost accounting only; free-tier usage bills at zero.
Model catalog verified 2026-08; refresh when providers change.
"""

from backend.core.llm.schemas import Route

PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "openai/gpt-oss-120b": (0.15, 0.75),
    "openai/gpt-oss-20b": (0.10, 0.50),
}

FALLBACK_PRICE = (1.0, 1.0)


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pin, pout = PRICES_PER_MTOK.get(model, FALLBACK_PRICE)
    return (prompt_tokens * pin + completion_tokens * pout) / 1_000_000


def route_model(route: Route, strong: str, fast: str) -> str:
    return strong if route is Route.STRONG else fast
