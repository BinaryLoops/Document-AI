"""
Case/Application bundle management.
P10 requirement: Case entity, document grouping, case workspace, scoped search.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class CaseManager:
    """
    Manage case bundles grouping multiple documents together.
    """
    
    def __init__(self, storage_backend=None):
        """
        Initialize case manager.
        
        Args:
            storage_backend: Optional storage backend (Firestore, MongoDB, etc.)
        """
        self.storage = storage_backend
        self.cases = {}  # In-memory cache
        logger.info("CaseManager initialized")
    
    def create_case(
        self,
        case_title: str,
        case_type: str,
        workflow: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new case bundle.
        
        Args:
            case_title: Title/name of the case
            case_type: Type of case (e.g., "Court Case", "Government Application")
            workflow: Workflow identifier
            metadata: Additional metadata
            
        Returns:
            Case ID
        """
        case_id = str(uuid.uuid4())
        
        case_data = {
            "case_id": case_id,
            "case_title": case_title,
            "case_type": case_type,
            "workflow": workflow,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "status": "OPEN",
            "document_ids": [],
            "document_count": 0,
            "metadata": metadata or {}
        }
        
        self.cases[case_id] = case_data
        
        # Persist to storage if available
        if self.storage:
            self._save_to_storage(case_id, case_data)
        
        logger.info(f"Created case: {case_id} - {case_title}")
        return case_id
    
    def add_document_to_case(
        self,
        case_id: str,
        document_id: str,
        document_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a document to a case bundle.
        
        Args:
            case_id: Case identifier
            document_id: Document identifier
            document_metadata: Optional document metadata
            
        Returns:
            Success status
        """
        if case_id not in self.cases:
            logger.error(f"Case not found: {case_id}")
            return False
        
        case = self.cases[case_id]
        
        if document_id not in case["document_ids"]:
            case["document_ids"].append(document_id)
            case["document_count"] = len(case["document_ids"])
            case["updated_at"] = datetime.utcnow().isoformat()
            
            # Add document metadata to case
            if document_metadata:
                if "documents" not in case:
                    case["documents"] = []
                case["documents"].append({
                    "document_id": document_id,
                    **document_metadata
                })
            
            # Persist changes
            if self.storage:
                self._save_to_storage(case_id, case)
            
            logger.info(f"Added document {document_id} to case {case_id}")
            return True
        
        logger.warning(f"Document {document_id} already in case {case_id}")
        return False
    
    def remove_document_from_case(
        self,
        case_id: str,
        document_id: str
    ) -> bool:
        """
        Remove a document from a case bundle.
        
        Args:
            case_id: Case identifier
            document_id: Document identifier
            
        Returns:
            Success status
        """
        if case_id not in self.cases:
            logger.error(f"Case not found: {case_id}")
            return False
        
        case = self.cases[case_id]
        
        if document_id in case["document_ids"]:
            case["document_ids"].remove(document_id)
            case["document_count"] = len(case["document_ids"])
            case["updated_at"] = datetime.utcnow().isoformat()
            
            # Remove from documents list
            if "documents" in case:
                case["documents"] = [
                    d for d in case["documents"] 
                    if d["document_id"] != document_id
                ]
            
            # Persist changes
            if self.storage:
                self._save_to_storage(case_id, case)
            
            logger.info(f"Removed document {document_id} from case {case_id}")
            return True
        
        logger.warning(f"Document {document_id} not in case {case_id}")
        return False
    
    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """
        Get case details.
        
        Args:
            case_id: Case identifier
            
        Returns:
            Case data or None
        """
        if case_id in self.cases:
            return self.cases[case_id].copy()
        
        # Try loading from storage
        if self.storage:
            case_data = self._load_from_storage(case_id)
            if case_data:
                self.cases[case_id] = case_data
                return case_data.copy()
        
        logger.warning(f"Case not found: {case_id}")
        return None
    
    def list_cases(
        self,
        status: Optional[str] = None,
        case_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all cases with optional filters.
        
        Args:
            status: Filter by status (OPEN, CLOSED, etc.)
            case_type: Filter by case type
            
        Returns:
            List of case summaries
        """
        cases = list(self.cases.values())
        
        # Apply filters
        if status:
            cases = [c for c in cases if c.get("status") == status]
        if case_type:
            cases = [c for c in cases if c.get("case_type") == case_type]
        
        # Sort by updated date
        cases.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
        
        return cases
    
    def update_case_status(
        self,
        case_id: str,
        new_status: str
    ) -> bool:
        """
        Update case status.
        
        Args:
            case_id: Case identifier
            new_status: New status (OPEN, UNDER_REVIEW, COMPLETED, CLOSED)
            
        Returns:
            Success status
        """
        if case_id not in self.cases:
            logger.error(f"Case not found: {case_id}")
            return False
        
        case = self.cases[case_id]
        case["status"] = new_status
        case["updated_at"] = datetime.utcnow().isoformat()
        
        if self.storage:
            self._save_to_storage(case_id, case)
        
        logger.info(f"Updated case {case_id} status to {new_status}")
        return True
    
    def delete_case(self, case_id: str) -> bool:
        """
        Delete a case bundle (does not delete documents).
        
        Args:
            case_id: Case identifier
            
        Returns:
            Success status
        """
        if case_id in self.cases:
            del self.cases[case_id]
            
            if self.storage:
                self._delete_from_storage(case_id)
            
            logger.info(f"Deleted case: {case_id}")
            return True
        
        logger.warning(f"Case not found: {case_id}")
        return False
    
    def get_case_statistics(self, case_id: str) -> Dict[str, Any]:
        """
        Get statistics for a case.
        
        Args:
            case_id: Case identifier
            
        Returns:
            Statistics dictionary
        """
        case = self.get_case(case_id)
        if not case:
            return {}
        
        return {
            "case_id": case_id,
            "document_count": case.get("document_count", 0),
            "created_at": case.get("created_at"),
            "updated_at": case.get("updated_at"),
            "status": case.get("status"),
            "case_type": case.get("case_type"),
            "workflow": case.get("workflow")
        }
    
    def _save_to_storage(self, case_id: str, case_data: Dict[str, Any]):
        """Save case to storage backend."""
        try:
            if hasattr(self.storage, 'collection'):
                # Firestore-style
                doc_ref = self.storage.collection("cases").document(case_id)
                doc_ref.set(case_data)
            elif hasattr(self.storage, 'insert_one'):
                # MongoDB-style
                self.storage.update_one(
                    {"case_id": case_id},
                    {"$set": case_data},
                    upsert=True
                )
        except Exception as e:
            logger.error(f"Failed to save case to storage: {e}")
    
    def _load_from_storage(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Load case from storage backend."""
        try:
            if hasattr(self.storage, 'collection'):
                # Firestore-style
                doc = self.storage.collection("cases").document(case_id).get()
                if doc.exists:
                    return doc.to_dict()
            elif hasattr(self.storage, 'find_one'):
                # MongoDB-style
                return self.storage.find_one({"case_id": case_id})
        except Exception as e:
            logger.error(f"Failed to load case from storage: {e}")
        return None
    
    def _delete_from_storage(self, case_id: str):
        """Delete case from storage backend."""
        try:
            if hasattr(self.storage, 'collection'):
                # Firestore-style
                self.storage.collection("cases").document(case_id).delete()
            elif hasattr(self.storage, 'delete_one'):
                # MongoDB-style
                self.storage.delete_one({"case_id": case_id})
        except Exception as e:
            logger.error(f"Failed to delete case from storage: {e}")
