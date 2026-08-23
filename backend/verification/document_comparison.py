"""
Cross-document comparison and inconsistency detection.
P7 requirement: Compare same field types across documents, flag mismatches using fuzzy matching.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from rapidfuzz import fuzz
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class DocumentComparison:
    """
    Compare extracted fields across multiple documents to detect inconsistencies.
    """
    
    # Field types that should match across documents
    COMPARABLE_FIELDS = [
        "full_name", "applicant_name", "holder_name", "deponent_name", "person_name",
        "date_of_birth", "dob",
        "address", "applicant_address", "deponent_address",
        "document_number", "application_number", "certificate_number",
        "contact_number", "phone", "mobile",
        "email",
        "father_name", "mother_name"
    ]
    
    # Similarity thresholds
    EXACT_MATCH_THRESHOLD = 100
    HIGH_SIMILARITY_THRESHOLD = 90
    MODERATE_SIMILARITY_THRESHOLD = 75
    LOW_SIMILARITY_THRESHOLD = 60
    
    def __init__(self, fuzzy_threshold: float = 85.0):
        """
        Initialize document comparison.
        
        Args:
            fuzzy_threshold: Threshold for fuzzy matching (0-100)
        """
        self.fuzzy_threshold = fuzzy_threshold
        logger.info(f"DocumentComparison initialized with threshold: {fuzzy_threshold}")
    
    def compare_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compare all documents in a set and flag inconsistencies.
        
        Args:
            documents: List of documents with extracted fields
                      Each doc should have: {document_id, filename, extracted_fields}
            
        Returns:
            List of inconsistency reports
        """
        if len(documents) < 2:
            logger.info("Need at least 2 documents for comparison")
            return []
        
        inconsistencies = []
        
        # Group fields by type across documents
        field_groups = self._group_fields_by_type(documents)
        
        # Compare each field type
        for field_name, field_instances in field_groups.items():
            if len(field_instances) < 2:
                continue
            
            # Compare all pairs
            field_inconsistencies = self._compare_field_instances(
                field_name, 
                field_instances
            )
            
            inconsistencies.extend(field_inconsistencies)
        
        logger.info(f"Found {len(inconsistencies)} potential inconsistencies")
        return inconsistencies
    
    def _group_fields_by_type(
        self, 
        documents: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group fields by their normalized type across documents.
        
        Args:
            documents: List of documents with extracted fields
            
        Returns:
            Dict mapping field names to list of instances across documents
        """
        field_groups = {}
        
        for doc in documents:
            doc_id = doc.get("document_id")
            filename = doc.get("filename", "Unknown")
            extracted_fields = doc.get("extracted_fields", [])
            
            for field_data in extracted_fields:
                field_name = field_data.get("field", "")
                value = field_data.get("value")
                
                # Normalize field name
                normalized_name = self._normalize_field_name(field_name)
                
                if normalized_name and value:
                    if normalized_name not in field_groups:
                        field_groups[normalized_name] = []
                    
                    field_groups[normalized_name].append({
                        "document_id": doc_id,
                        "filename": filename,
                        "field_name": field_name,
                        "value": value,
                        "confidence": field_data.get("confidence", 0.0),
                        "evidence": field_data.get("evidence", {})
                    })
        
        return field_groups
    
    def _normalize_field_name(self, field_name: str) -> Optional[str]:
        """
        Normalize field names for comparison.
        
        Args:
            field_name: Original field name
            
        Returns:
            Normalized field name or None if not comparable
        """
        field_lower = field_name.lower().replace("_", " ").strip()
        
        # Map variations to canonical names
        name_mappings = {
            "name": ["full_name", "applicant_name", "holder_name", "deponent_name", "person_name", "party_a_name", "party_b_name"],
            "dob": ["date_of_birth", "birth_date", "dob"],
            "address": ["address", "applicant_address", "deponent_address", "party_a_address", "party_b_address", "seller_address", "buyer_address"],
            "phone": ["contact_number", "phone", "mobile", "telephone"],
            "email": ["email", "email_address"],
            "father_name": ["father_name", "father's_name"],
            "mother_name": ["mother_name", "mother's_name"]
        }
        
        for canonical, variations in name_mappings.items():
            if any(var in field_lower for var in variations):
                return canonical
        
        # Return original if it's in comparable fields
        if field_name in self.COMPARABLE_FIELDS:
            return field_name
        
        return None
    
    def _compare_field_instances(
        self,
        field_name: str,
        instances: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compare all instances of a field type.
        
        Args:
            field_name: Name of the field being compared
            instances: List of field instances across documents
            
        Returns:
            List of inconsistency reports
        """
        inconsistencies = []
        
        # Compare each pair
        for i in range(len(instances)):
            for j in range(i + 1, len(instances)):
                instance_a = instances[i]
                instance_b = instances[j]
                
                inconsistency = self._compare_pair(
                    field_name,
                    instance_a,
                    instance_b
                )
                
                if inconsistency:
                    inconsistencies.append(inconsistency)
        
        return inconsistencies
    
    def _compare_pair(
        self,
        field_name: str,
        instance_a: Dict[str, Any],
        instance_b: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Compare two field instances.
        
        Args:
            field_name: Field name
            instance_a: First instance
            instance_b: Second instance
            
        Returns:
            Inconsistency report or None if consistent
        """
        value_a = str(instance_a["value"]).strip()
        value_b = str(instance_b["value"]).strip()
        
        # Calculate similarity
        similarity = fuzz.ratio(value_a.lower(), value_b.lower())
        
        # Determine if this is an inconsistency
        if similarity >= self.EXACT_MATCH_THRESHOLD:
            # Exact match
            return None
        elif similarity >= self.HIGH_SIMILARITY_THRESHOLD:
            # Very similar, might be minor variation (e.g., "Rahul Kumar" vs "Rahul K.")
            severity = "MINOR"
            message = f"Minor variation detected in '{field_name}'"
        elif similarity >= self.MODERATE_SIMILARITY_THRESHOLD:
            # Moderate similarity, needs review
            severity = "MODERATE"
            message = f"Potential inconsistency in '{field_name}'"
        else:
            # Low similarity, likely different
            severity = "MAJOR"
            message = f"Significant inconsistency in '{field_name}'"
        
        return {
            "field_name": field_name,
            "severity": severity,
            "similarity_score": similarity,
            "message": message,
            "document_a": {
                "document_id": instance_a["document_id"],
                "filename": instance_a["filename"],
                "value": value_a,
                "confidence": instance_a["confidence"],
                "page": instance_a.get("evidence", {}).get("page", "unknown")
            },
            "document_b": {
                "document_id": instance_b["document_id"],
                "filename": instance_b["filename"],
                "value": value_b,
                "confidence": instance_b["confidence"],
                "page": instance_b.get("evidence", {}).get("page", "unknown")
            },
            "recommendation": self._get_recommendation(severity, similarity)
        }
    
    @staticmethod
    def _get_recommendation(severity: str, similarity: float) -> str:
        """Generate recommendation based on severity."""
        if severity == "MINOR":
            return "Human verification recommended to confirm if this is acceptable variation"
        elif severity == "MODERATE":
            return "Human review required - values appear different but may refer to same entity"
        else:  # MAJOR
            return "Urgent human review required - significant discrepancy detected"
    
    def generate_comparison_report(
        self,
        inconsistencies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a summary report of inconsistencies.
        
        Args:
            inconsistencies: List of inconsistency reports
            
        Returns:
            Summary report
        """
        if not inconsistencies:
            return {
                "status": "CONSISTENT",
                "total_inconsistencies": 0,
                "by_severity": {"MINOR": 0, "MODERATE": 0, "MAJOR": 0},
                "message": "No inconsistencies detected across documents"
            }
        
        # Count by severity
        severity_counts = {"MINOR": 0, "MODERATE": 0, "MAJOR": 0}
        for inc in inconsistencies:
            severity = inc.get("severity", "MODERATE")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Determine overall status
        if severity_counts["MAJOR"] > 0:
            status = "MAJOR_ISSUES"
        elif severity_counts["MODERATE"] > 0:
            status = "REVIEW_REQUIRED"
        else:
            status = "MINOR_VARIATIONS"
        
        return {
            "status": status,
            "total_inconsistencies": len(inconsistencies),
            "by_severity": severity_counts,
            "inconsistencies": inconsistencies,
            "message": f"Found {len(inconsistencies)} potential inconsistencies requiring review"
        }


class FieldNormalizer:
    """
    Utility class for normalizing field values before comparison.
    """
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize person names for comparison."""
        # Remove titles
        name = re.sub(r'\b(Mr|Mrs|Ms|Dr|Prof|Sir|Madam)\.?\b', '', name, flags=re.IGNORECASE)
        # Remove extra whitespace
        name = ' '.join(name.split())
        # Title case
        return name.strip().title()
    
    @staticmethod
    def normalize_date(date_str: str) -> Optional[str]:
        """Normalize dates to YYYY-MM-DD format."""
        date_patterns = [
            r'(\d{4})-(\d{2})-(\d{2})',  # YYYY-MM-DD
            r'(\d{2})/(\d{2})/(\d{4})',  # DD/MM/YYYY
            r'(\d{2})-(\d{2})-(\d{4})',  # DD-MM-YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    if len(match.group(1)) == 4:  # YYYY format
                        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                    else:  # DD format
                        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
                except:
                    pass
        
        return None
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone numbers."""
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        # Remove country code if present
        if len(digits) > 10 and digits.startswith('91'):
            digits = digits[2:]
        return digits[-10:] if len(digits) >= 10 else digits
    
    @staticmethod
    def normalize_address(address: str) -> str:
        """Normalize addresses."""
        # Remove extra whitespace
        address = ' '.join(address.split())
        # Lowercase for comparison
        return address.lower().strip()
