"""Test environment bootstrap.

Env vars are set before any backend import so pydantic-settings resolves
test configuration (env vars take priority over the developer's .env).
"""

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="sentinel-tests-")
os.environ["GROQ_API_KEY"] = "test-key-not-real"
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["CHROMA_PERSIST_DIR"] = f"{_TMP}/chroma"
os.environ["REPORTS_DIR"] = _TMP

import pytest

from backend.core.config import get_settings
from backend.core.llm import FakeLLMClient, set_llm_client
from backend.db.base import get_engine, get_session_factory, init_db


@pytest.fixture()
def fake_llm():
    client = FakeLLMClient()
    set_llm_client(client)
    yield client
    set_llm_client(None)


@pytest.fixture(autouse=True)
def _fresh_evidence_backend():
    from backend.modules.scamwatch.evidence import set_evidence_backend

    set_evidence_backend(None)
    yield
    set_evidence_backend(None)


@pytest.fixture()
def db_session():
    get_settings()
    init_db()
    factory = get_session_factory()
    session = factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(autouse=True)
def _clean_db():
    yield
    engine = get_engine()
    from backend.db.models import Base

    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
