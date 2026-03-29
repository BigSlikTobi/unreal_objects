"""Shared internal authentication middleware for Unreal Objects services.

When ``INTERNAL_API_KEY`` is set, every non-safe (POST/PUT/PATCH/DELETE) request
must carry a matching ``X-Internal-Key`` header.  GET, HEAD, OPTIONS and requests
to health endpoints are always allowed.

In production (``ENVIRONMENT=production``), the service refuses to start if
``INTERNAL_API_KEY`` is not configured.
"""

import os

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

_INTERNAL_API_KEY: str | None = os.getenv("INTERNAL_API_KEY")

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_HEALTH_PATHS = {"/v1/health", "/health", "/api/v1/status"}


def check_production_api_key() -> None:
    """Call at module import time in each service.

    Raises ``SystemExit`` if we are in production without an API key.
    """
    if os.getenv("ENVIRONMENT") == "production" and not os.getenv("INTERNAL_API_KEY"):
        raise SystemExit(
            "INTERNAL_API_KEY must be set when ENVIRONMENT=production"
        )


class InternalAuthMiddleware(BaseHTTPMiddleware):
    """Reject non-safe requests that lack a valid ``X-Internal-Key`` header."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Re-read at request time so tests can patch the env var
        api_key = os.getenv("INTERNAL_API_KEY")

        # If no key is configured, allow everything (local dev)
        if not api_key:
            return await call_next(request)

        # Safe methods and health probes are always allowed
        if request.method in _SAFE_METHODS:
            return await call_next(request)
        if request.url.path in _HEALTH_PATHS:
            return await call_next(request)

        provided = request.headers.get("x-internal-key")
        if provided != api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )

        return await call_next(request)


def internal_headers() -> dict[str, str]:
    """Return headers dict to attach to outbound httpx requests."""
    key = os.getenv("INTERNAL_API_KEY")
    if key:
        return {"X-Internal-Key": key}
    return {}
