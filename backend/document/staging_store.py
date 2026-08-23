"""
In-memory staging store for the two-step upload -> review -> confirm/discard
flow.

Documents are OCR'd, classified, and field-extracted immediately on upload,
but are held in a temporary, *unindexed* staging area until the user
explicitly confirms them. This lets a citizen review what the system
detected (title, dates, issuing authority, reference numbers, etc.) before
it becomes part of their permanent document record, and cheaply discard +
retry if the wrong file was picked or OCR quality looks poor -- without
leaving half-processed documents in the RAG index / knowledge graph.

Entries are held for a limited time (default 30 minutes) and are purged
lazily whenever the store is touched.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

DEFAULT_TTL_SECONDS = 30 * 60  # 30 minutes


@dataclass
class StagedDocument:
    document_id: str
    filename: str
    ext: str
    chunks: List[str]
    chunk_metadata: List[Dict[str, Any]]
    document_type: str
    classification_confidence: float
    extracted_fields: List[Dict[str, Any]]
    cloudinary_file: Dict[str, Any]
    build_kg: bool = True
    start_time: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)


class StagingStore:
    """Thread-safe in-memory store with lazy TTL expiry."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._store: Dict[str, StagedDocument] = {}

    @property
    def ttl_seconds(self) -> int:
        return self._ttl

    def put(self, staged: StagedDocument) -> None:
        with self._lock:
            self._purge_expired_locked()
            self._store[staged.document_id] = staged

    def get(self, document_id: str) -> Optional[StagedDocument]:
        with self._lock:
            self._purge_expired_locked()
            return self._store.get(document_id)

    def pop(self, document_id: str) -> Optional[StagedDocument]:
        with self._lock:
            self._purge_expired_locked()
            return self._store.pop(document_id, None)

    def _purge_expired_locked(self) -> None:
        now = time.time()
        expired = [
            doc_id
            for doc_id, doc in self._store.items()
            if now - doc.created_at > self._ttl
        ]
        for doc_id in expired:
            self._store.pop(doc_id, None)


staging_store = StagingStore()
