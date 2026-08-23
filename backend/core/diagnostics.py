"""
core/diagnostics.py — Startup diagnostics for DocuMind AI.

Checks every critical subsystem at startup and reports a structured
summary.  Each check is non-fatal — the server starts regardless so that
the /health and /readiness endpoints can reflect partial availability.

Usage (main.py)
---------------
    from core.diagnostics import run_diagnostics, DiagnosticReport
    report = await run_diagnostics()
    if report.has_critical_failures:
        logger.warning("Starting in degraded mode: %s", report.summary)
"""

from __future__ import annotations

import importlib
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from core.logging import get_logger

logger = get_logger(__name__)


# ── Status enum ──────────────────────────────────────────────────────────────

class CheckStatus(str, Enum):
    OK       = "ok"
    WARN     = "warn"
    FAIL     = "fail"
    SKIP     = "skip"


# ── Individual check result ──────────────────────────────────────────────────

@dataclass
class CheckResult:
    name:    str
    status:  CheckStatus
    message: str
    detail:  Optional[str]  = None
    elapsed_ms: float       = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name":       self.name,
            "status":     self.status.value,
            "message":    self.message,
            "detail":     self.detail,
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


# ── Aggregate report ─────────────────────────────────────────────────────────

@dataclass
class DiagnosticReport:
    checks:     List[CheckResult] = field(default_factory=list)
    started_at: float             = field(default_factory=time.time)

    @property
    def total_elapsed_ms(self) -> float:
        return round((time.time() - self.started_at) * 1000, 1)

    @property
    def has_critical_failures(self) -> bool:
        return any(c.status == CheckStatus.FAIL for c in self.checks)

    @property
    def summary(self) -> str:
        ok   = sum(1 for c in self.checks if c.status == CheckStatus.OK)
        warn = sum(1 for c in self.checks if c.status == CheckStatus.WARN)
        fail = sum(1 for c in self.checks if c.status == CheckStatus.FAIL)
        skip = sum(1 for c in self.checks if c.status == CheckStatus.SKIP)
        return f"ok={ok} warn={warn} fail={fail} skip={skip}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary":          self.summary,
            "total_elapsed_ms": self.total_elapsed_ms,
            "has_failures":     self.has_critical_failures,
            "checks":           [c.to_dict() for c in self.checks],
        }


# ── Individual check functions ───────────────────────────────────────────────

def _time_check(name: str, fn: Callable[[], CheckResult]) -> CheckResult:
    """Run fn(), inject elapsed time, return result."""
    start = time.perf_counter()
    try:
        result = fn()
    except Exception as e:
        result = CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message=f"Unexpected error: {e}",
        )
    result.elapsed_ms = (time.perf_counter() - start) * 1000
    return result


def check_python_version() -> CheckResult:
    v = sys.version_info
    if v >= (3, 10):
        return CheckResult("python_version", CheckStatus.OK,
                           f"Python {v.major}.{v.minor}.{v.micro}")
    if v >= (3, 9):
        return CheckResult("python_version", CheckStatus.WARN,
                           f"Python {v.major}.{v.minor}.{v.micro} — 3.10+ recommended")
    return CheckResult("python_version", CheckStatus.FAIL,
                       f"Python {v.major}.{v.minor}.{v.micro} — 3.9+ required")


def check_env_file() -> CheckResult:
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        return CheckResult("env_file", CheckStatus.OK, ".env file found")
    return CheckResult("env_file", CheckStatus.WARN,
                       ".env file not found — using environment variables only")


def check_critical_env_vars() -> CheckResult:
    missing: List[str] = []
    recommended = [
        "HUGGINGFACE_API_KEY",
        "FIREBASE_CREDENTIALS_PATH",
    ]
    for var in recommended:
        if not os.getenv(var):
            missing.append(var)
    if not missing:
        return CheckResult("env_vars", CheckStatus.OK, "All recommended env vars set")
    return CheckResult(
        "env_vars", CheckStatus.WARN,
        f"{len(missing)} recommended env var(s) not set",
        detail=", ".join(missing),
    )


def check_faiss() -> CheckResult:
    try:
        import faiss  # noqa: F401
        return CheckResult("faiss", CheckStatus.OK, "faiss-cpu importable")
    except ImportError as e:
        return CheckResult("faiss", CheckStatus.FAIL,
                           "faiss-cpu not installed", detail=str(e))


def check_sentence_transformers() -> CheckResult:
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
        return CheckResult("sentence_transformers", CheckStatus.OK,
                           "sentence-transformers importable")
    except ImportError as e:
        return CheckResult("sentence_transformers", CheckStatus.FAIL,
                           "sentence-transformers not installed", detail=str(e))


def check_tesseract() -> CheckResult:
    tesseract_cmd = os.getenv("TESSERACT_CMD", "tesseract")
    binary = shutil.which(tesseract_cmd) or shutil.which("tesseract")
    if binary:
        return CheckResult("tesseract", CheckStatus.OK,
                           f"Tesseract binary found: {binary}")
    return CheckResult("tesseract", CheckStatus.WARN,
                       "Tesseract binary not found in PATH — OCR will fall back to EasyOCR",
                       detail=f"TESSERACT_CMD={tesseract_cmd}")


def check_ollama() -> CheckResult:
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            return CheckResult("ollama", CheckStatus.OK,
                               f"Ollama available — models: {models or 'none pulled'}")
        return CheckResult("ollama", CheckStatus.WARN,
                           f"Ollama reachable but returned {resp.status_code}")
    except Exception:
        return CheckResult("ollama", CheckStatus.WARN,
                           "Ollama not running — will use HuggingFace fallback")


def check_spacy() -> CheckResult:
    try:
        import spacy  # noqa: F401
        try:
            spacy.load("en_core_web_sm")
            return CheckResult("spacy", CheckStatus.OK,
                               "spaCy + en_core_web_sm available")
        except OSError:
            return CheckResult("spacy", CheckStatus.WARN,
                               "spaCy installed but en_core_web_sm not downloaded",
                               detail="Run: python -m spacy download en_core_web_sm")
    except ImportError as e:
        return CheckResult("spacy", CheckStatus.WARN,
                           "spaCy not installed — KG NER disabled", detail=str(e))


def check_firebase() -> CheckResult:
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
    if not cred_path:
        return CheckResult("firebase", CheckStatus.SKIP,
                           "FIREBASE_CREDENTIALS_PATH not set — Firebase disabled")
    if not os.path.exists(cred_path):
        return CheckResult("firebase", CheckStatus.WARN,
                           f"Firebase credentials file not found: {cred_path}")
    try:
        import firebase_admin  # noqa: F401
        return CheckResult("firebase", CheckStatus.OK,
                           "firebase-admin importable; credentials file exists")
    except ImportError as e:
        return CheckResult("firebase", CheckStatus.WARN,
                           "firebase-admin not installed", detail=str(e))


def check_neo4j() -> CheckResult:
    neo4j_uri = os.getenv("NEO4J_URI", "")
    if not neo4j_uri or not os.getenv("NEO4J_PASSWORD"):
        return CheckResult("neo4j", CheckStatus.SKIP,
                           "NEO4J_URI / NEO4J_PASSWORD not set — using in-memory KG")
    try:
        from neo4j import GraphDatabase  # noqa: F401
        return CheckResult("neo4j", CheckStatus.OK,
                           "neo4j driver importable")
    except ImportError as e:
        return CheckResult("neo4j", CheckStatus.WARN,
                           "neo4j driver not installed", detail=str(e))


def check_disk_space() -> CheckResult:
    try:
        import shutil as _sh
        total, used, free = _sh.disk_usage(".")
        free_gb = free / (1024 ** 3)
        if free_gb < 1.0:
            return CheckResult("disk_space", CheckStatus.FAIL,
                               f"Low disk space: {free_gb:.1f} GB free")
        if free_gb < 5.0:
            return CheckResult("disk_space", CheckStatus.WARN,
                               f"Disk space: {free_gb:.1f} GB free")
        return CheckResult("disk_space", CheckStatus.OK,
                           f"Disk space: {free_gb:.1f} GB free")
    except Exception as e:
        return CheckResult("disk_space", CheckStatus.WARN,
                           "Could not check disk space", detail=str(e))


def check_routes_module() -> CheckResult:
    try:
        import routes.routes  # noqa: F401
        return CheckResult("routes_module", CheckStatus.OK, "routes.routes importable")
    except Exception as e:
        return CheckResult("routes_module", CheckStatus.FAIL,
                           "routes.routes failed to import", detail=str(e))


# ── Main runner ──────────────────────────────────────────────────────────────

async def run_diagnostics() -> DiagnosticReport:
    """
    Run all startup checks and return a DiagnosticReport.

    Async to allow future async checks (e.g. DB ping) without a refactor.
    """
    report = DiagnosticReport()

    checks = [
        ("python_version",        check_python_version),
        ("env_file",              check_env_file),
        ("env_vars",              check_critical_env_vars),
        ("faiss",                 check_faiss),
        ("sentence_transformers", check_sentence_transformers),
        ("tesseract",             check_tesseract),
        ("ollama",                check_ollama),
        ("spacy",                 check_spacy),
        ("firebase",              check_firebase),
        ("neo4j",                 check_neo4j),
        ("disk_space",            check_disk_space),
        ("routes_module",         check_routes_module),
    ]

    for name, fn in checks:
        result = _time_check(name, fn)
        report.checks.append(result)

        icon = {"ok": "✓", "warn": "⚠", "fail": "✗", "skip": "○"}.get(
            result.status.value, "?"
        )
        log_fn = {
            CheckStatus.OK:   logger.info,
            CheckStatus.WARN: logger.warning,
            CheckStatus.FAIL: logger.error,
            CheckStatus.SKIP: logger.info,
        }[result.status]
        log_fn(
            "  %s [%-22s] %s%s",
            icon,
            name,
            result.message,
            f" — {result.detail}" if result.detail else "",
        )

    logger.info(
        "Startup diagnostics complete in %.0f ms: %s",
        report.total_elapsed_ms,
        report.summary,
    )

    return report
