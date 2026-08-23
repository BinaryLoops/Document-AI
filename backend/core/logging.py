"""
core/logging.py — Centralised structured logging for DocuMind AI.

Usage
-----
    from core.logging import get_logger, configure_logging

    # Call once at startup (main.py does this automatically)
    configure_logging()

    # In every module — replaces logging.getLogger(__name__)
    logger = get_logger(__name__)

Design
------
- JSON formatter in production  (LOG_FORMAT=json)
- Human-readable formatter in development / testing
- Request-ID injected automatically by core.middleware when available
- Sensitive field masking so API keys never reach log sinks
- Rotating file handler when LOG_FILE is set
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import json
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# ── Module-level sentinel so configure_logging() is idempotent ──────────────
_configured: bool = False

# ── Thread-local / context var for request ID ───────────────────────────────
try:
    from contextvars import ContextVar
    _request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
except ImportError:
    _request_id_var = None  # type: ignore[assignment]


def set_request_id(request_id: str) -> None:
    """Set the current request ID (called by RequestIDMiddleware)."""
    if _request_id_var is not None:
        _request_id_var.set(request_id)


def get_request_id() -> str:
    """Return the current request ID, or '-' if not set."""
    if _request_id_var is not None:
        return _request_id_var.get()
    return "-"


# ── Sensitive field masking ──────────────────────────────────────────────────
_SENSITIVE_KEYS = frozenset({
    "api_key", "apikey", "api-key",
    "password", "passwd", "secret",
    "token", "access_token", "refresh_token",
    "authorization", "auth",
    "openai_api_key", "huggingface_api_key",
    "firebase_credentials_path",
    "neo4j_password",
})

_MASK = "***REDACTED***"


def _mask_sensitive(record: logging.LogRecord) -> logging.LogRecord:
    """Replace sensitive values in log message and args."""
    msg = str(record.getMessage())
    for key in _SENSITIVE_KEYS:
        # mask "KEY=value" and "KEY: value" patterns (case-insensitive)
        import re
        msg = re.sub(
            rf'(?i)({re.escape(key)}\s*[=:]\s*)[^\s,\'"]+',
            rf'\1{_MASK}',
            msg,
        )
    record.msg = msg
    record.args = ()
    return record


# ── JSON formatter ───────────────────────────────────────────────────────────

class _JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        _mask_sensitive(record)
        log_obj: Dict[str, Any] = {
            "ts":         datetime.now(timezone.utc).isoformat(),
            "level":      record.levelname,
            "logger":     record.name,
            "request_id": get_request_id(),
            "message":    record.getMessage(),
            "module":     record.module,
            "func":       record.funcName,
            "line":       record.lineno,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            log_obj["stack"] = self.formatStack(record.stack_info)
        return json.dumps(log_obj, ensure_ascii=False)


# ── Human-readable formatter ─────────────────────────────────────────────────

class _HumanFormatter(logging.Formatter):
    """Coloured, human-readable formatter for development / testing."""

    _COLORS = {
        "DEBUG":    "\033[36m",   # Cyan
        "INFO":     "\033[32m",   # Green
        "WARNING":  "\033[33m",   # Yellow
        "ERROR":    "\033[31m",   # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        _mask_sensitive(record)
        # formatTime must be called BEFORE accessing record.asctime
        record.asctime = self.formatTime(record, datefmt="%Y-%m-%d %H:%M:%S")
        color   = self._COLORS.get(record.levelname, "")
        reset   = self._RESET
        rid     = get_request_id()
        rid_str = f" [{rid}]" if rid != "-" else ""
        base    = (
            f"{color}{record.asctime} "
            f"{record.levelname:<8}{reset} "
            f"{record.name}{rid_str} - {record.getMessage()}"
        )
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


# ── Public API ───────────────────────────────────────────────────────────────

def configure_logging(
    level:       Optional[str] = None,
    fmt:         Optional[str] = None,
    log_file:    Optional[str] = None,
    max_bytes:   int = 10 * 1024 * 1024,   # 10 MB
    backup_count: int = 5,
) -> None:
    """
    Configure the root logger.  Call once at application startup.

    Parameters
    ----------
    level : str, optional
        Override LOG_LEVEL env var (e.g. "DEBUG", "INFO", "WARNING").
    fmt : str, optional
        Override LOG_FORMAT env var ("json" | "human").
    log_file : str, optional
        Override LOG_FILE env var.  Enables rotating file handler.
    max_bytes : int
        Max size of each log file (default 10 MB).
    backup_count : int
        Number of backup log files to keep (default 5).
    """
    global _configured
    if _configured:
        return
    _configured = True

    # ── Force UTF-8 on stdout/stderr ───────────────────────────
    # On Windows, sys.stdout/stderr default to the console's legacy codepage
    # (cp1252) unless PYTHONUTF8=1 is set externally. Since this codebase
    # logs Unicode symbols (✓ ✗ ⚠) everywhere, an un-reconfigured stream
    # causes `UnicodeEncodeError` *inside* the logging module itself on
    # every such line -- this silently floods stderr with tracebacks
    # instead of raising (logging swallows handler errors by design),
    # which is easy to miss until a real `uvicorn` run is inspected.
    # Reconfiguring here makes logging robust regardless of how the
    # process is launched (uvicorn CLI, systemd, Docker, IDE, etc.).
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass  # stream doesn't support reconfigure (e.g. captured/mocked) -- non-fatal

    # ── Resolve settings ────────────────────────────────────────────────
    log_level_str = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    log_fmt       = (fmt   or os.getenv("LOG_FORMAT", "human")).lower()
    log_file_path = log_file or os.getenv("LOG_FILE", "")

    numeric_level = getattr(logging, log_level_str, logging.INFO)

    # ── Formatter ───────────────────────────────────────────────────────
    formatter: logging.Formatter
    if log_fmt == "json":
        formatter = _JSONFormatter()
    else:
        formatter = _HumanFormatter(
            fmt="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # ── Handlers ────────────────────────────────────────────────────────
    handlers: list[logging.Handler] = []

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(numeric_level)
    handlers.append(console)

    if log_file_path:
        os.makedirs(os.path.dirname(log_file_path) or ".", exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(numeric_level)
        handlers.append(file_handler)

    # ── Root logger ─────────────────────────────────────────────────────
    root = logging.getLogger()
    root.setLevel(numeric_level)
    # Remove any existing handlers (e.g. from basicConfig)
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)

    # Quiet noisy third-party loggers
    for noisy in ("urllib3", "httpx", "httpcore", "sentence_transformers",
                  "transformers", "PIL", "fitz", "easyocr", "faiss"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.debug(
        "Logging configured: level=%s, format=%s, file=%s",
        log_level_str, log_fmt, log_file_path or "none",
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a module-level logger.

    Drop-in replacement for ``logging.getLogger(__name__)`` that ensures
    the centralised configuration is respected.

    Usage
    -----
        from core.logging import get_logger
        logger = get_logger(__name__)
    """
    return logging.getLogger(name)
