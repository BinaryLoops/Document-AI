"""
Missing document checker with configurable requirements per workflow.
P8 requirement: Check required documents per workflow, output checklist with status.
"""

import logging
from typing import List, Dict, Any, Optional
import json
import os

logger = logging.getLogger(__name__)


class MissingDocumentChecker:
    """
    Check for missing required documents based on workflow configuration.
    """
    
    # Default workflow configurations
    DEFAULT_WORKFLOWS = {
        "GOVERNMENT_APPLICATION": {
            "name": "Government Application Verification",
            "required_documents": [
                "Application",
                "Identity Proof",
                "Address Proof"
            ],
            "optional_documents": [
                "Certificate",
                "Affidavit"
            ]
        },
        "COURT_CASE": {
            "name": "Court Case Bundle",
            "required_documents": [
                "Court Document",
                "Affidavit",
                "Identity Proof"
            ],
            "optional_documents": [
                "Address Proof",
                "Certificate"
            ]
        },
        "NOTARY_VERIFICATION": {
            "name": "Notary/Affidavit Verification",
            "required_documents": [
                "Affidavit",
                "Identity Proof",
                "Address Proof"
            ],
            "optional_documents": [
                "Certificate"
            ]
        },
        "CONTRACT_EXECUTION": {
            "name": "Contract Execution",
            "required_documents": [
                "Contract",
                "Identity Proof"
            ],
            "optional_documents": [
                "Address Proof",
                "Affidavit"
            ]
        },
        "FINANCIAL_TRANSACTION": {
            "name": "Financial Transaction Verification",
            "required_documents": [
                "Invoice",
                "Identity Proof",
                "Address Proof"
            ],
            "optional_documents": [
                "Receipt",
                "Contract"
            ]
        }
    }
    
    def __init__(self, custom_workflows: Optional[Dict[str, Any]] = None):
        """
        Initialize missing document checker.
        
        Args:
            custom_workflows: Optional custom workflow configurations
        """
        self.workflows = self.DEFAULT_WORKFLOWS.copy()
        
        if custom_workflows:
            self.workflows.update(custom_workflows)
        
        logger.info(f"MissingDocumentChecker initialized with {len(self.workflows)} workflows")
    
    def check_documents(
        self,
        document_types: List[str],
        workflow: str
    ) -> Dict[str, Any]:
        """
        Check if all required documents are present for a workflow.
        
        Args:
            document_types: List of document types present
            workflow: Workflow identifier
            
        Returns:
            Checklist report with status
        """
        if workflow not in self.workflows:
            logger.error(f"Unknown workflow: {workflow}")
            return self._create_error_report(workflow)
        
        workflow_config = self.workflows[workflow]
        required = workflow_config.get("required_documents", [])
        optional = workflow_config.get("optional_documents", [])
        
        # Normalize document types (handle case variations)
        document_types_normalized = [dt.strip().title() for dt in document_types]
        
        # Check required documents
        required_status = []
        missing_required = []
        
        for doc_type in required:
            is_present = doc_type in document_types_normalized
            required_status.append({
                "document_type": doc_type,
                "status": "PRESENT" if is_present else "MISSING",
                "required": True
            })
            if not is_present:
                missing_required.append(doc_type)
        
        # Check optional documents
        optional_status = []
        for doc_type in optional:
            is_present = doc_type in document_types_normalized
            optional_status.append({
                "document_type": doc_type,
                "status": "PRESENT" if is_present else "NOT_PROVIDED",
                "required": False
            })
        
        # Determine overall status
        if missing_required:
            overall_status = "INCOMPLETE"
            status_message = f"APPLICATION INCOMPLETE — Missing: {', '.join(missing_required)}"
        else:
            overall_status = "COMPLETE"
            status_message = "APPLICATION COMPLETE — All required documents present"
        
        # Calculate completeness percentage
        total_required = len(required)
        present_required = total_required - len(missing_required)
        completeness = (present_required / total_required * 100) if total_required > 0 else 0
        
        return {
            "workflow": workflow,
            "workflow_name": workflow_config.get("name", workflow),
            "overall_status": overall_status,
            "status_message": status_message,
            "completeness_percentage": round(completeness, 1),
            "required_documents": required_status,
            "optional_documents": optional_status,
            "missing_required": missing_required,
            "total_required": len(required),
            "present_required": present_required,
            "checklist": self._generate_checklist(required_status, optional_status)
        }
    
    def _generate_checklist(
        self,
        required_status: List[Dict[str, Any]],
        optional_status: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a human-readable checklist.
        
        Args:
            required_status: Status of required documents
            optional_status: Status of optional documents
            
        Returns:
            Formatted checklist string
        """
        lines = ["DOCUMENT CHECKLIST", "=" * 50, "", "Required Documents:"]
        
        for item in required_status:
            symbol = "✓" if item["status"] == "PRESENT" else "✗"
            lines.append(f"  {symbol} {item['document_type']}")
        
        lines.extend(["", "Optional Documents:"])
        
        for item in optional_status:
            symbol = "✓" if item["status"] == "PRESENT" else "○"
            lines.append(f"  {symbol} {item['document_type']}")
        
        return "\n".join(lines)
    
    def batch_check(
        self,
        cases: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Check multiple cases in batch.
        
        Args:
            cases: List of cases with document_types and workflow
            
        Returns:
            List of checklist reports
        """
        results = []
        
        for case in cases:
            case_id = case.get("case_id", "unknown")
            document_types = case.get("document_types", [])
            workflow = case.get("workflow", "GOVERNMENT_APPLICATION")
            
            result = self.check_documents(document_types, workflow)
            result["case_id"] = case_id
            results.append(result)
        
        return results
    
    @staticmethod
    def _create_error_report(workflow: str) -> Dict[str, Any]:
        """Create error report for unknown workflow."""
        return {
            "workflow": workflow,
            "overall_status": "ERROR",
            "status_message": f"Unknown workflow: {workflow}",
            "completeness_percentage": 0,
            "required_documents": [],
            "optional_documents": [],
            "missing_required": [],
            "checklist": "ERROR: Workflow configuration not found"
        }
    
    def add_workflow(
        self,
        workflow_id: str,
        name: str,
        required_documents: List[str],
        optional_documents: Optional[List[str]] = None
    ):
        """
        Add a custom workflow configuration.
        
        Args:
            workflow_id: Unique workflow identifier
            name: Human-readable workflow name
            required_documents: List of required document types
            optional_documents: List of optional document types
        """
        self.workflows[workflow_id] = {
            "name": name,
            "required_documents": required_documents,
            "optional_documents": optional_documents or []
        }
        logger.info(f"Added workflow: {workflow_id}")
    
    def get_workflows(self) -> List[Dict[str, Any]]:
        """Get list of all available workflows."""
        return [
            {
                "workflow_id": wid,
                "name": config.get("name", wid),
                "required_count": len(config.get("required_documents", [])),
                "optional_count": len(config.get("optional_documents", []))
            }
            for wid, config in self.workflows.items()
        ]
    
    def save_workflows(self, filepath: str):
        """Save workflow configurations to a JSON file."""
        try:
            with open(filepath, 'w') as f:
                json.dump(self.workflows, f, indent=2)
            logger.info(f"Workflows saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save workflows: {e}")
    
    @classmethod
    def load_workflows(cls, filepath: str) -> 'MissingDocumentChecker':
        """Load workflow configurations from a JSON file."""
        try:
            with open(filepath, 'r') as f:
                workflows = json.load(f)
            logger.info(f"Workflows loaded from {filepath}")
            return cls(custom_workflows=workflows)
        except Exception as e:
            logger.error(f"Failed to load workflows: {e}")
            return cls()
