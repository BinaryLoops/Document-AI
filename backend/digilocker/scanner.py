"""
digilocker/scanner.py — Pluggable malware scanning for uploaded documents.

Provides:
  - MockScanner    — always passes (development mode)
  - ClamAVScanner  — connects to clamd daemon for real scanning
  - create_scanner() factory — picks implementation from MALWARE_SCANNER env var
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Result of a malware scan."""
    is_clean: bool
    engine: str
    detail: str = ""


class MalwareScanner(ABC):
    """Abstract base class for malware scanners."""

    @abstractmethod
    def scan(self, file_bytes: bytes, filename: str = "") -> ScanResult:
        """
        Scan file bytes for malware.

        Args:
            file_bytes: Raw file content.
            filename:   Original filename (for logging).

        Returns:
            ScanResult with is_clean=True if safe.
        """


class MockScanner(MalwareScanner):
    """
    Development-mode scanner — always passes.
    Logs a warning so it's obvious this is not production-grade.
    """

    def scan(self, file_bytes: bytes, filename: str = "") -> ScanResult:
        logger.warning(
            "MockScanner: file '%s' (%d bytes) — PASSED (mock, no real scan)",
            filename, len(file_bytes),
        )
        return ScanResult(
            is_clean=True,
            engine="mock",
            detail="Mock scanner — no real malware check performed",
        )


class ClamAVScanner(MalwareScanner):
    """
    Production scanner using ClamAV via the pyclamd library.

    Requires:
      - ClamAV daemon (clamd) running
      - pip install pyclamd
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 3310,
        unix_socket: Optional[str] = None,
    ):
        try:
            import pyclamd
        except ImportError:
            raise ImportError(
                "pyclamd is not installed. Install with: pip install pyclamd"
            )

        if unix_socket:
            self._clam = pyclamd.ClamdUnixSocket(filename=unix_socket)
        else:
            self._clam = pyclamd.ClamdNetworkSocket(host=host, port=port)

        # Verify connection
        try:
            if not self._clam.ping():
                raise ConnectionError("ClamAV daemon did not respond to ping")
            version = self._clam.version()
            logger.info("ClamAV scanner connected: %s", version)
        except Exception as e:
            raise ConnectionError(f"Cannot connect to ClamAV daemon: {e}")

    def scan(self, file_bytes: bytes, filename: str = "") -> ScanResult:
        try:
            result = self._clam.scan_stream(file_bytes)

            if result is None:
                # No threat found
                logger.info("ClamAV: file '%s' — CLEAN", filename)
                return ScanResult(is_clean=True, engine="clamav", detail="Clean")

            # result format: {'stream': ('FOUND', 'Eicar-Signature')}
            status, threat = result.get("stream", ("UNKNOWN", "unknown"))
            logger.warning(
                "ClamAV: file '%s' — THREAT DETECTED: %s", filename, threat
            )
            return ScanResult(
                is_clean=False,
                engine="clamav",
                detail=f"Threat detected: {threat}",
            )

        except Exception as e:
            logger.error("ClamAV scan error for '%s': %s", filename, e)
            # Fail-safe: reject files that can't be scanned
            return ScanResult(
                is_clean=False,
                engine="clamav",
                detail=f"Scan error: {e}",
            )


def create_scanner() -> MalwareScanner:
    """
    Factory function — create the appropriate scanner based on environment.

    Set MALWARE_SCANNER env var:
      - "mock"   → MockScanner  (default for development)
      - "clamav" → ClamAVScanner
    """
    scanner_type = os.environ.get("MALWARE_SCANNER", "mock").lower()

    if scanner_type == "clamav":
        host = os.environ.get("CLAMAV_HOST", "127.0.0.1")
        port = int(os.environ.get("CLAMAV_PORT", "3310"))
        socket = os.environ.get("CLAMAV_SOCKET")
        return ClamAVScanner(host=host, port=port, unix_socket=socket)

    # Default: mock
    logger.info("Using MockScanner (set MALWARE_SCANNER=clamav for production)")
    return MockScanner()
