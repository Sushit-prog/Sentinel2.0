"""API middleware: request IDs, API-key auth, per-identity rate limiting."""

import hashlib
import secrets
import threading
import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.core.config import get_settings
from backend.core.logging import request_id_var


def _client_identity(request: Request) -> str:
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return "key:" + hashlib.sha256(api_key.encode()).hexdigest()[:16]
    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )
    return "ip:" + ip


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or secrets.token_hex(8)
        token = request_id_var.set(rid)
        try:
            response: Response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response


class ApiKeyMiddleware(BaseHTTPMiddleware):
    OPEN_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.api_key_set:
            return await call_next(request)
        if request.url.path in self.OPEN_PATHS:
            return await call_next(request)
        provided = request.headers.get("X-API-Key", "")
        if not provided or not any(
            secrets.compare_digest(provided, k) for k in settings.api_key_set
        ):
            return JSONResponse(
                {
                    "error": {
                        "code": "unauthorized",
                        "message": "missing or invalid API key",
                    }
                },
                status_code=401,
            )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-process sliding-window limiter. Per-process only by design; a Redis-backed
    limiter slots in behind the same interface when deployed multi-node."""

    def __init__(self, app):
        super().__init__(app)
        self._events: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _allow(
        self, identity: str, limit: int, window_s: float = 60.0
    ) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            bucket = [t for t in self._events.get(identity, []) if now - t < window_s]
            remaining = max(limit - len(bucket) - 1, 0)
            if len(bucket) >= limit:
                retry_after = int(window_s - (now - bucket[0])) + 1
                self._events[identity] = bucket
                return False, retry_after
            bucket.append(now)
            self._events[identity] = bucket
            return True, remaining

    async def dispatch(self, request: Request, call_next):
        limit = get_settings().rate_limit_per_minute
        allowed, info = self._allow(_client_identity(request), limit)
        if not allowed:
            return JSONResponse(
                {"error": {"code": "rate_limited", "message": f"retry after {info}s"}},
                status_code=429,
                headers={"Retry-After": str(info)},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(info)
        return response
