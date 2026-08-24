"""Typed contracts for the model layer."""

from dataclasses import dataclass, field
from enum import Enum


class Route(str, Enum):
    FAST = "fast"
    STRONG = "strong"


@dataclass(frozen=True)
class Usage:
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    est_cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "latency_ms": self.latency_ms,
            "est_cost_usd": round(self.est_cost_usd, 6),
        }


@dataclass(frozen=True)
class LLMResult:
    text: str
    usage: Usage
    finish_reason: str = "stop"
    repaired: bool = False


@dataclass
class TokenBudget:
    daily_token_budget: int
    _spent: int = field(default=0)

    @property
    def spent(self) -> int:
        return self._spent

    @property
    def remaining(self) -> int:
        return max(self.daily_token_budget - self._spent, 0)

    def can_spend(self, estimated: int) -> bool:
        return self._spent + estimated <= self.daily_token_budget

    def record(self, tokens: int) -> None:
        self._spent += tokens
