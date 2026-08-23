"""
core/middleware.py — Production-grade ASGI middleware for DocuMind AI.

Middleware stack (order matters — outermost first in main.py):
    1. RequestIDMiddleware   — injects X-Request-ID on every request/response
    2. ExceptionMiddleware   — catches unhandled exceptions, returns structured
                               JSON error, logs full traceback server-side

Usage (main.py)
---------------
    from core.middleware import add_middleware
    add_middleware(app)
"""

from __future__ import annotations

import json
import logging
import time
import traceback
import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from core.logging import get_logger, get_request_id, set_request_id

logger = get_logger(__name__)


# ── 1. Request-ID Middleware ─────────────────────────────────────────────────

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Attach a unique X-Request-ID to every request and response.

    - Reuses the incoming header if the client already provides one.
    - Stores the ID in a ContextVar so it appears in every log line.
    - Always echoes the ID back in the response headers.
    """

    _HEADER = "X-Request-ID"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Use incoming ID or generate a new one
        request_id = request.headers.get(self._HEADER) or str(uuid.uuid4())

        # Store in context so logger picks it up automatically
        set_request_id(request_id)

        # Time the request
        start = time.perf_counter()

        # Store on request state for downstream handlers
        request.state.request_id = request_id

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        # Add headers to response
        response.headers[self._HEADER] = request_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)

        # Access log
        logger.info(
            "%s %s %s %dms rid=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )

        return response


# ── 2. Exception Middleware ──────────────────────────────────────────────────

class ExceptionMiddleware(BaseHTTPMiddleware):
    """
    Catch any unhandled exception that escapes FastAPI's own exception handler.

    - Logs the full traceback server-side (never sent to the client).
    - Returns a generic JSON error body with the request ID for correlation.
    - Preserves HTTPExceptions (they are already handled by FastAPI).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            request_id = getattr(request.state, "request_id", get_request_id())

            # Full traceback to server logs — NEVER to client
            logger.error(
                "Unhandled exception on %s %s rid=%s",
                request.method,
                request.url.path,
                request_id,
                exc_info=True,
            )

            return JSONResponse(
                status_code=500,
                content={
                    "error":      "internal_server_error",
                    "message":    "An unexpected error occurred. Check server logs.",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )


# ── 3. Security Headers Middleware ───────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add basic security headers to every response.
    Lightweight alternative to installing helmet-style packages.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options",  "nosniff")
        response.headers.setdefault("X-Frame-Options",          "DENY")
        response.headers.setdefault("Referrer-Policy",          "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        return response


# ── Convenience installer ────────────────────────────────────────────────────

def add_middleware(app: FastAPI, cors_origins: list[str] | None = None) -> None:
    """
    Register the full middleware stack on the FastAPI app.

    Call this **before** any route registration.

    Parameters
    ----------
    app : FastAPI
        The application instance.
    cors_origins : list[str], optional
        Allowed CORS origins.  Defaults to ["*"] (development).
        Always override this in production with explicit origins.
    """
    import os

    # Resolve CORS origins
    if cors_origins is None:
        env_origins = os.getenv("CORS_ORIGINS", "*")
        if env_origins.strip() == "*":
            cors_origins = ["*"]
        else:
            cors_origins = [o.strip() for o in env_origins.split(",") if o.strip()]

    # NOTE: Starlette applies middleware in REVERSE registration order,
    # so we add outermost last.

    # Security headers (innermost — wraps the app response)
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS
    allow_credentials = "*" not in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time-Ms"],
    )

    # Exception handler (wraps everything below)
    app.add_middleware(ExceptionMiddleware)

    # Request ID (outermost — first to run)
    app.add_middleware(RequestIDMiddleware)

    logger.debug(
        "Middleware stack registered: RequestID → Exception → CORS → SecurityHeaders"
    )
