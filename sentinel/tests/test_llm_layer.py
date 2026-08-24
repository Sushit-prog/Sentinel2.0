import threading

import pytest
from pydantic import BaseModel

from backend.core.llm import (
    FakeLLMClient,
    LLMError,
    Route,
    StructuredOutputError,
    set_llm_client,
)
from backend.core.llm.client import LLMClient, ProviderUnavailable, SlidingWindowLimiter
from backend.core.llm.pricing import estimate_cost_usd
from backend.core.llm.schemas import TokenBudget


class Verdict(BaseModel):
    label: str
    score: float


def test_fake_client_queues_and_parses_json():
    client = FakeLLMClient()
    client.extract_responses = ['{"label": "SCAM", "score": 0.9}']
    parsed, result = client.extract(Verdict, "irrelevant")
    assert parsed.label == "SCAM"
    assert parsed.score == 0.9
    assert result.usage.total_tokens > 0


def test_fake_client_raises_scripted_errors():
    client = FakeLLMClient()
    client.complete_responses = [ProviderUnavailable("down")]
    with pytest.raises(LLMError):
        client.complete("hello")


def test_fake_client_records_call_metadata():
    client = FakeLLMClient()
    client.complete_responses = ["ok"]
    client.complete("analyze this", route=Route.FAST, json_mode=True)
    assert client.calls[0]["route"] == str(Route.FAST)
    assert client.calls[0]["json_mode"] is True


def test_set_llm_client_swap_and_reset():
    fake = FakeLLMClient()
    set_llm_client(fake)
    from backend.core.llm import get_llm_client

    assert get_llm_client() is fake
    set_llm_client(None)


def test_parse_strips_markdown_fences():
    text = '```json\n{"label": "OK", "score": 0.5}\n```'
    parsed = LLMClient._parse(Verdict, text)
    assert parsed.label == "OK"


def test_parse_extracts_json_from_surrounding_prose():
    parsed = LLMClient._parse(
        Verdict, 'Here you go: {"label": "X", "score": 0.1} hope that helps'
    )
    assert parsed.score == 0.1


def test_sliding_window_limiter_blocks_over_limit():
    limiter = SlidingWindowLimiter(max_events=3, window_s=60.0)
    for _ in range(3):
        assert limiter.acquire() == 0.0
    blocked = limiter._events
    assert len(blocked) == 3


def test_limiter_is_thread_safe_under_capacity():
    limiter = SlidingWindowLimiter(max_events=200, window_s=60.0)

    def hammer():
        for _ in range(20):
            limiter.acquire()

    threads = [threading.Thread(target=hammer) for _ in range(4)]
    [t.start() for t in threads]
    [t.join(timeout=10) for t in threads]
    assert all(not t.is_alive() for t in threads)
    assert len(limiter._events) == 80


def test_token_budget_guards():
    budget = TokenBudget(daily_token_budget=100)
    assert budget.can_spend(60)
    budget.record(60)
    assert not budget.can_spend(60)
    assert budget.can_spend(40)
    assert budget.remaining == 40


def test_cost_estimation_uses_model_table():
    strong = estimate_cost_usd("openai/gpt-oss-120b", 1_000_000, 0)
    fast = estimate_cost_usd("openai/gpt-oss-20b", 1_000_000, 0)
    assert strong > fast
    unknown = estimate_cost_usd("mystery-model", 1_000_000, 0)
    assert unknown == 1.0


def test_structured_output_error_carries_raw_text():
    err = StructuredOutputError("bad json", last_raw="oops")
    assert err.last_raw == "oops"
