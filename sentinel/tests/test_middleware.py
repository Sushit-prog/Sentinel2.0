import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware import (
    ApiKeyMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
)
from backend.core.config import Settings


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(ApiKeyMiddleware)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/api/thing")
    def thing():
        return {"ok": True}

    return app


@pytest.fixture()
def client():
    return TestClient(_app())


def _settings(keys: str = "", **overrides) -> Settings:
    return Settings(
        groq_api_key="test-key-not-real",
        app_env="development",
        api_keys=keys,
        database_url="sqlite:///./nonexistent.db",
        **overrides,
    )


def test_request_id_generated_when_missing(client):
    r = client.get("/health")
    assert r.headers.get("X-Request-ID")


def test_request_id_passthrough(client):
    r = client.get("/health", headers={"X-Request-ID": "my-rid-123"})
    assert r.headers["X-Request-ID"] == "my-rid-123"


def test_auth_open_in_dev_without_keys(client, monkeypatch):
    monkeypatch.setattr("backend.api.middleware.get_settings", lambda: _settings(""))
    assert client.get("/api/thing").status_code == 200


def test_auth_rejects_missing_key(client, monkeypatch):
    monkeypatch.setattr(
        "backend.api.middleware.get_settings", lambda: _settings("secret-key-1")
    )
    r = client.get("/api/thing")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_auth_accepts_valid_key_only(client, monkeypatch):
    monkeypatch.setattr(
        "backend.api.middleware.get_settings",
        lambda: _settings("secret-key-1,secret-key-2"),
    )
    assert client.get("/api/thing", headers={"X-API-Key": "nope"}).status_code == 401
    assert (
        client.get("/api/thing", headers={"X-API-Key": "secret-key-2"}).status_code
        == 200
    )


def test_health_stays_open_with_auth_enabled(client, monkeypatch):
    monkeypatch.setattr("backend.api.middleware.get_settings", lambda: _settings("k1"))
    assert client.get("/health").status_code == 200


def test_rate_limiter_blocks_after_limit():
    limiter = RateLimitMiddleware(app=None)
    for _ in range(3):
        allowed, _remaining = limiter._allow("ip:test", 3)
        assert allowed
    allowed, retry_after = limiter._allow("ip:test", 3)
    assert not allowed
    assert retry_after > 0


def test_rate_limiter_keys_are_isolated():
    limiter = RateLimitMiddleware(app=None)
    for _ in range(3):
        assert limiter._allow("ip:a", 3)[0]
    assert limiter._allow("ip:b", 3)[0]


def test_production_requires_api_keys():
    with pytest.raises(ValueError):
        Settings(groq_api_key="x", app_env="production", api_keys="")


def test_production_rejects_sqlite():
    with pytest.raises(ValueError):
        Settings(
            groq_api_key="x",
            app_env="production",
            api_keys="k",
            database_url="sqlite:///./x.db",
        )
