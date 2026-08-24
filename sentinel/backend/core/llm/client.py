"""Groq provider adapter.

Owns retry/backoff, per-call timeout, request-rate limiting and a daily token
budget guard. The rest of the codebase depends only on the LLMClient
interface, never on this module or the groq SDK.
"""

import json
import logging
import random
import threading
import time
from typing import Type, TypeVar

from groq import Groq, RateLimitError as GroqRateLimitError
from groq import APIConnectionError, APITimeoutError, InternalServerError
from pydantic import BaseModel, ValidationError

from backend.core.config import Settings
from backend.core.llm.pricing import estimate_cost_usd, route_model
from backend.core.llm.schemas import LLMResult, Route, TokenBudget, Usage

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_RETRYABLE = (
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
    GroqRateLimitError,
)


class LLMError(Exception):
    pass


class ProviderUnavailable(LLMError):
    pass


class BudgetExceeded(LLMError):
    pass


class StructuredOutputError(LLMError):
    def __init__(self, message: str, last_raw: str):
        super().__init__(message)
        self.last_raw = last_raw


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_s: float = 60.0):
        self._max = max_events
        self._window = window_s
        self._events: list[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> float:
        while True:
            with self._lock:
                now = time.monotonic()
                self._events = [t for t in self._events if now - t < self._window]
                if len(self._events) < self._max:
                    self._events.append(now)
                    return 0.0
                wait = self._window - (now - self._events[0]) + 0.01
            time.sleep(wait)


class LLMClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = Groq(
            api_key=settings.groq_api_key.get_secret_value(),
            timeout=settings.llm_timeout_s,
            max_retries=0,
        )
        self._strong = settings.llm_strong_model
        self._fast = settings.llm_fast_model
        self._limiter = SlidingWindowLimiter(
            max_events=max(settings.rate_limit_per_minute // 2, 5)
        )
        self.budget = TokenBudget(daily_token_budget=settings.daily_token_budget)

    @property
    def models(self) -> dict[str, str]:
        return {"strong": self._strong, "fast": self._fast}

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
        model = self._resolve(route)
        est = len(user) // 3 + 256
        if not self.budget.can_spend(est):
            raise BudgetExceeded(
                f"daily token budget exhausted ({self.budget.spent}/{self.budget.daily_token_budget})"
            )

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        kwargs: dict = {"response_format": {"type": "json_object"}} if json_mode else {}
        delay = 1.0
        last_exc: Exception | None = None
        for attempt in range(self._settings.llm_max_retries + 1):
            self._limiter.acquire()
            start = time.monotonic()
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                usage = resp.usage
                u = Usage(
                    model=model,
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    latency_ms=int((time.monotonic() - start) * 1000),
                )
                cost = estimate_cost_usd(model, u.prompt_tokens, u.completion_tokens)
                usage_with_cost = Usage(
                    u.model, u.prompt_tokens, u.completion_tokens, u.latency_ms, cost
                )
                self.budget.record(usage_with_cost.total_tokens)
                choice = resp.choices[0]
                logger.info(
                    "llm_call",
                    extra={
                        "model": model,
                        "prompt_tokens": u.prompt_tokens,
                        "completion_tokens": u.completion_tokens,
                        "latency_ms": u.latency_ms,
                        "finish_reason": choice.finish_reason,
                    },
                )
                return LLMResult(
                    text=choice.message.content or "",
                    usage=usage_with_cost,
                    finish_reason=choice.finish_reason or "stop",
                )
            except _RETRYABLE as exc:
                last_exc = exc
                retry_after = getattr(exc, "retry_after", None)
                sleep_s = (
                    float(retry_after)
                    if retry_after
                    else delay * (1 + random.random() * 0.3)
                )
                logger.warning(
                    "llm_retry attempt=%d sleep=%.1fs error=%s",
                    attempt + 1,
                    sleep_s,
                    type(exc).__name__,
                )
                if attempt < self._settings.llm_max_retries:
                    time.sleep(sleep_s)
                    delay *= 2
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "llm_nonretryable attempt=%d error=%s",
                    attempt + 1,
                    type(exc).__name__,
                )
                break
        raise ProviderUnavailable(
            f"provider unavailable after retries: {last_exc}"
        ) from last_exc

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
        schema_hint = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        base_system = (
            f"{system or 'You are a precise data extraction engine.'}\n\n"
            "Return ONLY one JSON object conforming to this schema. "
            "No markdown fences, no commentary.\n"
            f"Schema:\n{schema_hint}"
        )
        result = self.complete(
            user,
            system=base_system,
            route=route,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        try:
            return self._parse(schema, result.text), result
        except (ValidationError, ValueError) as first_err:
            repair_prompt = (
                f"The following JSON failed validation:\n{result.text[:4000]}\n\n"
                f"Validation error:\n{_first_line(first_err)}\n\n"
                "Return ONLY the corrected JSON object."
            )
            repaired = self.complete(
                repair_prompt,
                system=base_system,
                route=route,
                temperature=0.0,
                max_tokens=max_tokens,
                json_mode=True,
            )
            try:
                parsed = self._parse(schema, repaired.text)
                fixed = LLMResult(
                    text=repaired.text,
                    usage=repaired.usage,
                    finish_reason=repaired.finish_reason,
                    repaired=True,
                )
                return parsed, fixed
            except (ValidationError, ValueError) as second_err:
                raise StructuredOutputError(
                    f"schema validation failed after repair: {_first_line(second_err)}",
                    last_raw=repaired.text,
                ) from second_err

    @staticmethod
    def _parse(schema: Type[T], text: str) -> T:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("```")[1]
            if stripped.startswith("json"):
                stripped = stripped[4:]
        start, end = stripped.find("{"), stripped.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("no JSON object found in output")
        return schema.model_validate_json(stripped[start : end + 1])

    def _resolve(self, route: Route | str) -> str:
        if isinstance(route, str):
            route = Route(route)
        return route_model(route, self._strong, self._fast)


def _first_line(err: Exception) -> str:
    return str(err).split("\n")[0][:500]
