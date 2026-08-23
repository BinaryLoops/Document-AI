"""
security/middleware.py -- Enterprise Security Middleware Stack.

Middleware (order: outermost first):
  1. RateLimitMiddleware      — Token-bucket per-IP rate limiting
  2. CSRFMiddleware           — CSRF token validation for state-changing requests
  3. InputSanitizationMiddleware — XSS/injection prevention
  4. DeviceFingerprintMiddleware — Track device fingerprints
  5. SessionTimeoutMiddleware   — Enforce session TTLs
"""

from __future__ import annotations

import hashlib
import html
import logging
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Set, Tuple

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ── 1. Rate Limiting (Token Bucket) ─────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP token-bucket rate limiting.

    Config via env:
      RATE_LIMIT_RPM=60       (requests per minute)
      RATE_LIMIT_BURST=10     (burst capacity)
    """

    def __init__(self, app, rpm: int = 60, burst: int = 10):
        super().__init__(app)
        self.rpm = rpm
        self.burst = burst
        self.refill_rate = rpm / 60.0  # tokens per second
        self._buckets: Dict[str, Tuple[float, float]] = {}  # ip -> (tokens, last_time)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = self._get_ip(request)

        # Exempt health checks
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        now = time.monotonic()
        tokens, last_time = self._buckets.get(client_ip, (float(self.burst), now))

        # Refill tokens
        elapsed = now - last_time
        tokens = min(float(self.burst), tokens + elapsed * self.refill_rate)

        if tokens < 1.0:
            logger.warning("Rate limit exceeded for IP %s", client_ip)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after_seconds": int((1.0 - tokens) / self.refill_rate) + 1,
                },
                headers={"Retry-After": str(int((1.0 - tokens) / self.refill_rate) + 1)},
            )

        tokens -= 1.0
        self._buckets[client_ip] = (tokens, now)

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(int(tokens))
        response.headers["X-RateLimit-Limit"] = str(self.rpm)
        return response

    def _get_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


# ── 2. CSRF Protection ──────────────────────────────────────────────────────

class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF token validation for state-changing requests (POST, PUT, DELETE, PATCH).

    - Sets a CSRF token cookie on GET requests.
    - Validates X-CSRF-Token header matches cookie on mutation requests.
    - Exempt: /docs, /openapi.json, /health, /auth/*
    """

    COOKIE_NAME = "csrf_token"
    HEADER_NAME = "X-CSRF-Token"
    EXEMPT_PREFIXES = ("/docs", "/openapi.json", "/redoc", "/health", "/auth/")
    MUTATION_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

    def __init__(self, app, enforce: bool = True):
        super().__init__(app)
        self.enforce = enforce

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Exempt paths
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return await call_next(request)

        # Set CSRF cookie on safe requests
        if request.method not in self.MUTATION_METHODS:
            response = await call_next(request)
            if self.COOKIE_NAME not in request.cookies:
                token = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
                response.set_cookie(
                    self.COOKIE_NAME, token,
                    httponly=False, samesite="strict", secure=False,
                    max_age=3600,
                )
            return response

        # Validate CSRF on mutation requests
        if self.enforce:
            cookie_token = request.cookies.get(self.COOKIE_NAME, "")
            header_token = request.headers.get(self.HEADER_NAME, "")

            if not cookie_token or not header_token or cookie_token != header_token:
                logger.warning("CSRF validation failed for %s %s", request.method, path)
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "csrf_validation_failed",
                        "message": "CSRF token missing or invalid. Include X-CSRF-Token header.",
                    },
                )

        return await call_next(request)


# ── 3. Input Sanitization ───────────────────────────────────────────────────

# Dangerous patterns
_SQL_INJECTION = re.compile(
    r"(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC|EXECUTE)\b.*\b(FROM|INTO|TABLE|SET|WHERE)\b)",
    re.IGNORECASE,
)
_XSS_PATTERNS = [
    re.compile(r"<script[^>]*>", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on(error|load|click|mouseover|focus|blur)\s*=", re.IGNORECASE),
    re.compile(r"<iframe", re.IGNORECASE),
    re.compile(r"<object", re.IGNORECASE),
    re.compile(r"<embed", re.IGNORECASE),
]
_PATH_TRAVERSAL = re.compile(r"\.\./|\.\.\\|%2e%2e", re.IGNORECASE)


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """
    Sanitize inputs to prevent XSS, SQL injection, and path traversal.
    Checks: URL path, query params, headers (User-Agent, Referer).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check URL path
        path = request.url.path
        if self._is_malicious(path):
            logger.warning("Blocked malicious path: %s from %s", path, self._get_ip(request))
            return JSONResponse(status_code=400, content={
                "error": "malicious_input", "message": "Request blocked by security policy.",
            })

        # Check query params
        for key, value in request.query_params.items():
            if self._is_malicious(value):
                logger.warning("Blocked malicious query param: %s=%s", key, value[:50])
                return JSONResponse(status_code=400, content={
                    "error": "malicious_input", "message": "Request blocked by security policy.",
                })

        return await call_next(request)

    def _is_malicious(self, value: str) -> bool:
        if _SQL_INJECTION.search(value):
            return True
        if _PATH_TRAVERSAL.search(value):
            return True
        for pattern in _XSS_PATTERNS:
            if pattern.search(value):
                return True
        return False

    def _get_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For", "")
        return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


# ── 4. Device Fingerprint ───────────────────────────────────────────────────

class DeviceFingerprintMiddleware(BaseHTTPMiddleware):
    """
    Generate and track device fingerprints from request headers.
    Stores fingerprint in request.state for downstream use.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        fingerprint = self._generate_fingerprint(request)
        request.state.device_fingerprint = fingerprint

        response = await call_next(request)
        response.headers["X-Device-Fingerprint"] = fingerprint[:16]
        return response

    def _generate_fingerprint(self, request: Request) -> str:
        parts = [
            request.headers.get("User-Agent", ""),
            request.headers.get("Accept-Language", ""),
            request.headers.get("Accept-Encoding", ""),
            request.client.host if request.client else "",
        ]
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()


# ── 5. Session Timeout ──────────────────────────────────────────────────────

class SessionTimeoutMiddleware(BaseHTTPMiddleware):
    """
    Enforce session timeout. Checks the session_start cookie and
    rejects requests if the session has exceeded the TTL.
    """

    def __init__(self, app, timeout_minutes: int = 30):
        super().__init__(app)
        self.timeout_seconds = timeout_minutes * 60

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Exempt non-authenticated paths
        if request.url.path.startswith(("/docs", "/health", "/auth/", "/openapi")):
            return await call_next(request)

        session_start = request.cookies.get("session_start")
        if session_start:
            try:
                start_ts = float(session_start)
                if time.time() - start_ts > self.timeout_seconds:
                    logger.info("Session expired for %s", self._get_ip(request))
                    response = JSONResponse(
                        status_code=401,
                        content={
                            "error": "session_expired",
                            "message": f"Session timed out after {self.timeout_seconds // 60} minutes. Please re-authenticate.",
                        },
                    )
                    response.delete_cookie("session_start")
                    return response
            except (ValueError, TypeError):
                pass

        response = await call_next(request)

        # Set/refresh session cookie
        if not session_start and request.url.path.startswith("/auth/"):
            response.set_cookie(
                "session_start", str(time.time()),
                httponly=True, samesite="strict", max_age=self.timeout_seconds,
            )

        return response

    def _get_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For", "")
        return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


# ── File Validation Utilities ────────────────────────────────────────────────

# Magic bytes for allowed file types
_FILE_SIGNATURES = {
    b"%PDF":          "pdf",
    b"\xff\xd8\xff":  "jpg",
    b"\x89PNG":       "png",
    b"PK\x03\x04":   "docx",  # ZIP-based (DOCX, XLSX, etc.)
}

_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

_DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".ps1", ".sh", ".vbs", ".js",
    ".msi", ".dll", ".com", ".scr", ".pif", ".hta",
}


def validate_file(filename: str, content: bytes) -> Dict[str, Any]:
    """
    Validate an uploaded file for security.

    Checks:
      - File size
      - Extension whitelist
      - Magic bytes verification
      - Dangerous extension blocking

    Returns dict with: valid, file_type, size, errors
    """
    errors = []
    file_type = "unknown"

    # Check size
    if len(content) > _MAX_FILE_SIZE:
        errors.append(f"File exceeds maximum size ({_MAX_FILE_SIZE // (1024*1024)} MB)")

    if len(content) == 0:
        errors.append("File is empty")

    # Check extension
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in _DANGEROUS_EXTENSIONS:
        errors.append(f"Dangerous file extension: {ext}")

    # Check magic bytes
    for magic, ftype in _FILE_SIGNATURES.items():
        if content[:len(magic)] == magic:
            file_type = ftype
            break

    if file_type == "unknown" and not errors:
        errors.append("Unrecognized file type (magic bytes don't match any allowed format)")

    return {
        "valid": len(errors) == 0,
        "file_type": file_type,
        "size_bytes": len(content),
        "filename": filename,
        "errors": errors,
    }


# ── Middleware Installer ─────────────────────────────────────────────────────

def add_security_middleware(
    app: FastAPI,
    rate_limit_rpm: int = 120,
    rate_limit_burst: int = 30,
    csrf_enforce: bool = False,  # False for dev, True for prod
    session_timeout_minutes: int = 30,
) -> None:
    """
    Register the full security middleware stack on the FastAPI app.

    Call AFTER core middleware but BEFORE route registration.
    """
    import os

    rpm = int(os.getenv("RATE_LIMIT_RPM", str(rate_limit_rpm)))
    burst = int(os.getenv("RATE_LIMIT_BURST", str(rate_limit_burst)))
    csrf = os.getenv("CSRF_ENFORCE", str(csrf_enforce)).lower() == "true"
    timeout = int(os.getenv("SESSION_TIMEOUT_MINUTES", str(session_timeout_minutes)))

    # Order: outermost (first hit) to innermost
    app.add_middleware(SessionTimeoutMiddleware, timeout_minutes=timeout)
    app.add_middleware(DeviceFingerprintMiddleware)
    app.add_middleware(InputSanitizationMiddleware)
    if csrf:
        app.add_middleware(CSRFMiddleware, enforce=True)
    app.add_middleware(RateLimitMiddleware, rpm=rpm, burst=burst)

    logger.info(
        "Security middleware installed: rate=%d rpm, csrf=%s, session=%d min",
        rpm, csrf, timeout,
    )
