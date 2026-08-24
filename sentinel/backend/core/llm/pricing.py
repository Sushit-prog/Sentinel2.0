"""Estimated token pricing (USD per 1M tokens, Groq published list prices).

Figures are for cost accounting only; free-tier usage bills at zero.
Numbers must be refreshed when providers change list prices.
"""

from backend.core.llm.schemas import Route

PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
}

FALLBACK_PRICE = (1.0, 1.0)


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pin, pout = PRICES_PER_MTOK.get(model, FALLBACK_PRICE)
    return (prompt_tokens * pin + completion_tokens * pout) / 1_000_000


def route_model(route: Route, strong: str, fast: str) -> str:
    return strong if route is Route.STRONG else fast
