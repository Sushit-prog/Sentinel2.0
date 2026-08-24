"""Deterministic in-memory LLM client for tests and offline runs."""

from typing import Type, TypeVar

from pydantic import BaseModel

from backend.core.llm.schemas import LLMResult, Route, Usage
from backend.core.llm.client import (
    BudgetExceeded,
    LLMError,
    ProviderUnavailable,
    StructuredOutputError,
)

T = TypeVar("T", bound=BaseModel)

_USAGE = Usage(model="fake", prompt_tokens=10, completion_tokens=10, latency_ms=1)


class FakeLLMClient:
    """Queues scripted responses; raises what you tell it to raise.

    complete_responses entries may be strings, Exception instances, or
    (text, repaired: bool) tuples. extract() parses queued dicts/strings
    against the requested schema like the real client would.
    """

    def __init__(self):
        self.complete_responses: list = []
        self.extract_responses: list = []
        self.calls: list[dict] = []
        self.budget = None

    def _pop(self, queue: list) -> object:
        if not queue:
            raise AssertionError("FakeLLMClient queue empty - script more responses")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def complete(
        self,
        user: str,
        *,
        system: str | None = None,
        route: Route | str = Route.STRONG,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResult:
        self.calls.append(
            {
                "user": user,
                "system": system,
                "route": str(route),
                "json_mode": json_mode,
            }
        )
        item = self._pop(self.complete_responses)
        text, repaired = item if isinstance(item, tuple) else (item, False)
        return LLMResult(text=text, usage=_USAGE, repaired=repaired)

    def extract(
        self,
        schema: Type[T],
        user: str,
        *,
        system: str | None = None,
        route: Route | str = Route.STRONG,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> tuple[T, LLMResult]:
        self.calls.append(
            {
                "user": user,
                "system": system,
                "route": str(route),
                "schema": schema.__name__,
            }
        )
        parsed = self._pop(self.extract_responses)
        if isinstance(parsed, Exception):
            raise parsed
        if isinstance(parsed, str):
            return schema.model_validate_json(parsed), LLMResult(
                text=parsed, usage=_USAGE
            )
        if isinstance(parsed, dict):
            model = schema.model_validate(parsed)
            import json as _json

            return model, LLMResult(text=_json.dumps(parsed), usage=_USAGE)
        return parsed, LLMResult(text=parsed.model_dump_json(), usage=_USAGE)


__all__ = [
    "BudgetExceeded",
    "FakeLLMClient",
    "LLMError",
    "ProviderUnavailable",
    "StructuredOutputError",
]
