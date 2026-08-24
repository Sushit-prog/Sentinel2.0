"""Model layer public API.

from backend.core.llm import get_llm_client, Route
"""

from functools import lru_cache

from backend.core.config import get_settings
from backend.core.llm.client import (
    BudgetExceeded,
    LLMClient,
    LLMError,
    ProviderUnavailable,
    StructuredOutputError,
)
from backend.core.llm.fake import FakeLLMClient
from backend.core.llm.router import resolve_auto
from backend.core.llm.schemas import LLMResult, Route, Usage

_client: LLMClient | FakeLLMClient | None = None


@lru_cache(maxsize=1)
def _build_client() -> LLMClient:
    return LLMClient(get_settings())


def get_llm_client() -> LLMClient | FakeLLMClient:
    global _client
    if _client is not None:
        return _client
    return _build_client()


def set_llm_client(client: LLMClient | FakeLLMClient | None) -> None:
    """Swap the process-wide client (tests inject FakeLLMClient here)."""
    global _client
    _client = client


__all__ = [
    "BudgetExceeded",
    "FakeLLMClient",
    "LLMClient",
    "LLMError",
    "LLMResult",
    "ProviderUnavailable",
    "Route",
    "StructuredOutputError",
    "Usage",
    "get_llm_client",
    "resolve_auto",
    "set_llm_client",
]
