"""
Document processing status tracking.
Implements the complete status lifecycle for P1.
"""

from enum import Enum
from typing import Optional
from datetime import datetime


class DocumentStatus(str, Enum):
    """Document processing status enum."""
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    OCR = "OCR"
    CLASSIFYING = "CLASSIFYING"
    EXTRACTING = "EXTRACTING"
    INDEXING = "INDEXING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DocumentMetadata:
    """Complete document metadata tracking."""
    
    def __init__(
        self,
        document_id: str,
        filename: str,
        source: str,
        upload_time: Optional[datetime] = None,
        page_count: Optional[int] = None,
        doc_type: Optional[str] = None,
        status: DocumentStatus = DocumentStatus.UPLOADED
    ):
        self.document_id = document_id
        self.filename = filename
        self.source = source
        self.upload_time = upload_time or datetime.utcnow()
        self.page_count = page_count
        self.doc_type = doc_type
        self.status = status
        self.status_history = [(status, datetime.utcnow())]
        self.error_message = None
        
    def update_status(self, new_status: DocumentStatus, error_message: Optional[str] = None):
        """Update document status with timestamp."""
        self.status = new_status
        self.status_history.append((new_status, datetime.utcnow()))
        if error_message:
            self.error_message = error_message
            
    def to_dict(self):
        """Convert to dictionary for storage."""
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "source": self.source,
            "upload_time": self.upload_time.isoformat(),
            "page_count": self.page_count,
            "doc_type": self.doc_type,
            "status": self.status.value,
            "status_history": [
                {"status": s.value, "timestamp": t.isoformat()} 
                for s, t in self.status_history
            ],
            "error_message": self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary."""
        doc = cls(
            document_id=data["document_id"],
            filename=data["filename"],
            source=data["source"],
            upload_time=datetime.fromisoformat(data["upload_time"]),
            page_count=data.get("page_count"),
            doc_type=data.get("doc_type"),
            status=DocumentStatus(data["status"])
        )
        doc.error_message = data.get("error_message")
        return doc
