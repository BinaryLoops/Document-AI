"""
Enhanced field extraction module with schema-based extraction.
P3 requirement: Config-based JSON schemas per document type.
P4 requirement: Evidence tracking for every extracted field.
"""

import json
import os
import re
import logging
from typing import List, Dict, Any, Optional

from document.evidence_tracker import EvidenceTracker, create_extracted_field, Evidence

logger = logging.getLogger(__name__)

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "schemas")


def load_schema(document_type: str) -> Dict[str, Any]:
    """
    Load JSON schema for a document type.
    
    Args:
        document_type: Type of document (e.g., "Application", "Identity Proof")
        
    Returns:
        Schema dictionary with fields and metadata
    """
    # Normalize document type name to filename
    filename = document_type.lower().replace(" ", "_") + ".json"
    path = os.path.join(SCHEMA_DIR, filename)
    
    if not os.path.exists(path):
        logger.warning(f"Schema not found for document type: {document_type}")
        return {"fields": []}
    
    try:
        with open(path, 'r') as f:
            schema = json.load(f)
        return schema
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse schema {filename}: {e}")
        return {"fields": []}


class FieldExtractor:
    """
    Schema-based field extraction with LLM and evidence tracking.
    """
    
    def __init__(self, rag_engine):
        """
        Initialize field extractor.
        
        Args:
            rag_engine: RAG engine instance with LLM access
        """
        self.rag_engine = rag_engine
        self.evidence_tracker = EvidenceTracker()
    
    def extract(
        self, 
        chunks: List[str], 
        chunk_metadata: List[Dict[str, Any]], 
        document_type: str, 
        filename: str
    ) -> List[Dict[str, Any]]:
        """
        Extract structured fields from document chunks using schema.
        
        Args:
            chunks: List of text chunks from document
            chunk_metadata: Metadata for each chunk
            document_type: Type of document
            filename: Source filename
            
        Returns:
            List of extracted fields with evidence
        """
        # Load schema for document type
        schema = load_schema(document_type)
        fields = schema.get("fields", [])

        # Prepare text
        full_text = " ".join(chunks)[:4000]

        extracted_fields = []

        # ── Schema-based extraction (when schema exists) ─────────────────
        for field in fields:
            field_name = self._get_field_name(field)
            field_info = self._get_field_info(fields, field_name)

            value, confidence = self._extract_field_value(field_name, full_text)

            evidence = self.evidence_tracker.find_evidence(
                value, chunks, chunk_metadata, filename
            )

            extracted_field = create_extracted_field(
                field_name=field_name,
                value=value,
                confidence=confidence,
                evidence=evidence,
                field_type=field_info.get("type"),
                required=field_info.get("required")
            )
            extracted_fields.append(extracted_field.to_dict())

        # ── Universal fallback extraction ────────────────────────────────
        # Always runs — picks up whatever the schema missed or when no
        # schema exists.  De-duplicates against schema results.
        schema_found_fields = {
            f["field"] for f in extracted_fields if f.get("value") is not None
        }
        universal = self._universal_extract(full_text)
        for field_name, value in universal.items():
            if field_name not in schema_found_fields:
                evidence = self.evidence_tracker.find_evidence(
                    value, chunks, chunk_metadata, filename
                )
                extracted_field = create_extracted_field(
                    field_name=field_name,
                    value=value,
                    confidence=0.85,
                    evidence=evidence,
                    field_type=self._guess_field_type(field_name),
                    required=False,
                )
                extracted_fields.append(extracted_field.to_dict())

        logger.info(f"Extracted {len(extracted_fields)} fields from {document_type}")
        return extracted_fields
    
    def _universal_extract(self, text: str) -> Dict[str, str]:
        """
        Schema-free extraction — works on ANY document type.

        Scans the text for key:value pairs using a broad set of patterns
        and returns whatever it finds as { field_name: value }.
        """
        results: Dict[str, str] = {}

        # ── Generic key:value pattern ──────────────────────────────────
        # Matches "Label: Value" or "Label - Value" lines
        kv_pattern = re.compile(
            r'^([A-Za-z][A-Za-z0-9 _/]{1,40}?)\s*[:\-]\s*(.{2,120}?)(?:\s*$)',
            re.MULTILINE
        )
        for m in kv_pattern.finditer(text):
            key_raw   = m.group(1).strip()
            value_raw = m.group(2).strip().rstrip('.,;')
            if not value_raw or len(value_raw) < 2:
                continue
            # Normalise key to snake_case
            key = re.sub(r'[\s/]+', '_', key_raw.lower())
            key = re.sub(r'[^a-z0-9_]', '', key)
            if key and value_raw:
                results[key] = value_raw

        # ── Specific universal patterns ────────────────────────────────
        universal_patterns = {
            # Dates — any label ending in "date" or "on"
            'date': r'\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})\b',
            # Email
            'email': r'\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b',
            # Phone (Indian + international)
            'phone': r'\b(\+?(?:91[\-\s]?)?\d{10})\b',
            # PAN card
            'pan_number': r'\b([A-Z]{5}\d{4}[A-Z])\b',
            # Aadhaar
            'aadhaar_number': r'\b(\d{4}\s\d{4}\s\d{4})\b',
            # Pincode
            'pincode': r'\b(\d{6})\b',
            # Currency amounts
            'amount': r'(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d{2})?)',
            # Case / file numbers
            'case_number': r'(?:case|file|matter)\s*(?:no|number|#)\s*[:\-]?\s*([A-Z0-9\-/]{4,20})',
            # Court name
            'court': r'(?:in\s+the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Court|Tribunal|Commission|Board))',
            # Organisation / company
            'organization': r'\b([A-Z][A-Za-z\s&]+(?:Ltd|Limited|Pvt|Corporation|Corp|Inc|LLP|Authority|Board|Council)\.?)\b',
        }

        for field_name, pattern in universal_patterns.items():
            if field_name not in results:
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    results[field_name] = m.group(1).strip()

        # ── Title heuristic ──────────────────────────────────────────
        # Certificates/forms rarely label their own title as "Title: ...";
        # it's almost always the first prominent heading line instead
        # (e.g. "CERTIFICATE OF ACHIEVEMENT", "Birth Certificate"). Pick
        # the first short, non key:value line near the top of the document.
        if 'document_title' not in results:
            for raw_line in text.splitlines()[:8]:
                candidate = raw_line.strip(' \t.:-')
                if not (5 <= len(candidate) <= 90):
                    continue
                if re.search(r'[:=]', candidate):
                    continue  # looks like a "Label: Value" line, not a title
                letters = re.sub(r'[^A-Za-z]', '', candidate)
                if len(letters) < 4:
                    continue
                upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
                is_titlecase = candidate == candidate.title()
                if upper_ratio > 0.6 or is_titlecase:
                    results['document_title'] = candidate
                    break

        # ── Clean up noise keys ──────────────────────────────────────────
        noise = {
            'the', 'and', 'or', 'of', 'to', 'in', 'a', 'an', 'is', 'it',
            'this', 'that', 'for', 'on', 'at', 'by', 'with', 'from',
        }
        return {
            k: v for k, v in results.items()
            if k not in noise and len(k) > 1 and len(v) > 1
        }

    @staticmethod
    def _guess_field_type(field_name: str) -> str:
        """Guess field type from field name."""
        name = field_name.lower()
        if any(x in name for x in ('date', 'dob', 'birth', 'issue', 'expiry', 'valid')):
            return 'date'
        if any(x in name for x in ('amount', 'fee', 'price', 'cost', 'salary', 'income')):
            return 'number'
        if 'email' in name:
            return 'email'
        if any(x in name for x in ('phone', 'mobile', 'contact', 'tel')):
            return 'phone'
        return 'string'

    def _extract_field_value(self, field_name: str, text: str) -> tuple:
        """
        Extract field value using improved pattern matching.
        
        Args:
            field_name: Name of field to extract
            text: Document text
            
        Returns:
            Tuple of (value, confidence)
        """
        # Define improved field patterns - covers both Application and Identity Proof types
        field_patterns = {
            # ── Identity / name fields ──────────────────────────────────
            'full_name': [
                r'(?:full\s+)?name\s*[:\-=]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s+(?:ID|id|S/O|D/O|Age|DOB|Date|Address|Gender|\d)|\s*$)',
                r'(?:holder|bearer|applicant)\s+name\s*[:\-=]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s+\S|\s*$)',
                r'(?:Mr|Ms|Mrs|Dr|Shri|Smt)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
            ],
            'holder_name': [
                r'(?:full\s+)?name\s*[:\-=]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s+\S|\s*$)',
                r'holder\s*[:\-=]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
            ],
            'applicant_name': [
                r'(?:applicant\s+)?name\s*[:\-=]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s+(?:ID|Date|DOB|Address|Age|\d)|\s*$)',
                r'(?:Mr|Ms|Mrs|Dr)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
            ],
            # ── ID / document numbers ────────────────────────────────────
            'document_number': [
                r'(?:id|identification|document)\s+(?:no|number|#)\s*[:\-=]\s*([A-Z0-9\-]{4,20})',
                r'(?:card|cert(?:ificate)?)\s+(?:no|number)\s*[:\-=]\s*([A-Z0-9\-/]{4,20})',
                r'(?:serial|sl)\s*(?:no|number)?\s*[:\-=]\s*([A-Z0-9\-]{4,20})',
                r'\b([A-Z]{2,4}[\-]?\d{4,12}(?:[\-][A-Z0-9]+)?)\b',
            ],
            'id_number': [
                r'(?:id|identification)\s+(?:no|number|#)\s*[:\-=]\s*([A-Z0-9\-]{4,20})',
                r'\b(ID[\-]?\d{4}[\-]\d{4}[\-]\d{4})\b',
                r'\b([A-Z]{2,4}[\-]\d{4,12})\b',
            ],
            'certificate_number': [
                r'cert(?:ificate)?\s+(?:no|number)\s*[:\-=]\s*([A-Z0-9\-/]{4,20})',
                r'\b([A-Z]{2,}\d{6,})\b',
            ],
            'application_number': [
                r'application\s+(?:no|number|#|num)\s*[:\-=]?\s*([A-Z0-9\-/]+)',
                r'reference\s+(?:no|number)\s*[:\-=]?\s*([A-Z0-9\-/]+)',
                r'\b([A-Z]{2,}\d{4,})\b',
            ],
            # ── Dates ────────────────────────────────────────────────────
            'date_of_birth': [
                r'date\s+of\s+birth\s*[:\-=]\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
                r'\bdob\b\s*[:\-=]\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
                r'born\s+on\s*[:\-=]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
                r'birth\s+date\s*[:\-=]\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            ],
            'issue_date': [
                r'issue\s+date\s*[:\-=]\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
                r'issued\s+(?:on|date)\s*[:\-=]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
                r'date\s+of\s+issue\s*[:\-=]\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
                r'valid\s+from\s*[:\-=]\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            ],
            'expiry_date': [
                r'(?:expiry|expiration|valid\s+until|valid\s+upto|valid\s+till)\s*[:\-=]\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
                r'expires?\s+(?:on)?\s*[:\-=]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            ],
            'date_filed': [
                r'(?:application|filed|submission)\s+date\s*[:\-=]\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
                r'date\s+(?:filed|submitted)\s*[:\-=]\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
                r'\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})\b',
            ],
            # ── Address ──────────────────────────────────────────────────
            'address': [
                r'address\s*[:\-=]\s*(.{10,80}?)(?=\s*(?:gender|phone|contact|mobile|dob|date|issue|valid|email|$))',
                r'residential\s+address\s*[:\-=]\s*(.{10,60}?)(?=\s*(?:gender|phone|contact|$))',
            ],
            'applicant_address': [
                r'(?:applicant\s+)?address\s*[:\-=]\s*(.{10,80}?)(?=\s*(?:gender|phone|contact|mobile|dob|date|issue|valid|$))',
                r'(\d+\s+[A-Za-z\s]+(?:nagar|colony|street|road|lane|avenue)\s*,\s*[A-Za-z\s,]+\d{6})',
            ],
            # ── Personal attributes ───────────────────────────────────────
            'gender': [
                r'gender\s*[:\-=]\s*(male|female|other|transgender)',
                r'\b(male|female)\b(?!\s*(?:ward|patient|doctor))',
            ],
            'nationality': [
                r'nationality\s*[:\-=]\s*([A-Za-z]+)',
                r'citizenship\s*[:\-=]\s*([A-Za-z]+)',
            ],
            'father_name': [
                r"father'?s?\s+name\s*[:\-=]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
                r's/o\.?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
            ],
            'mother_name': [
                r"mother'?s?\s+name\s*[:\-=]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
                r'd/o\.?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
            ],
            # ── Contact ──────────────────────────────────────────────────
            'contact_number': [
                r'(?:phone|contact|mobile|tel|mo?b?\.?)\s*(?:no|number)?\s*[:\-=]\s*([\+]?[\d\-\(\)\s]{10,})',
                r'\b(\+?91[\-\s]?\d{10})\b',
                r'\b(\d{10})\b',
            ],
            'email': [
                r'email\s*(?:id|address)?\s*[:\-=]\s*([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})',
                r'\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b',
            ],
            # ── Document-specific ─────────────────────────────────────────
            'document_type_specific': [
                r'^([A-Z][A-Z\s]{3,}(?:CARD|CERTIFICATE|LICENCE|LICENSE|PERMIT|PASS))$',
                r'(?:type|category)\s*[:\-=]\s*([A-Za-z\s]+?)(?:\n|$)',
            ],
            'purpose': [
                r'purpose\s*[:\-=]\s*([^\n]+?)(?:\s+[A-Z][a-z]+\s*[:\-=]|$)',
                r'reason\s*[:\-=]\s*([^\n]+?)(?:\s+[A-Z][a-z]+\s*[:\-=]|$)',
            ],
            'department': [
                r'department\s*[:\-=]\s*([^\n]+?)(?:\s+[A-Z]|$)',
                r'dept\.?\s*[:\-=]\s*([^\n]+?)(?:\s+[A-Z]|$)',
            ],
            'document_title': [
                r'^([A-Z\s]{5,}(?:FORM|APPLICATION|CERTIFICATE|LICENSE|PERMIT|CARD))$',
            ],
            # ── Universal core fields (title/date/author/reference) ────────
            # These back the generic "Other" schema and any document type
            # whose specific fields didn't match, so every processed
            # document gets a best-effort title/date/issuer/reference.
            'date': [
                r'(?:^|\s)date\s*[:\-=]\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
                r'\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})\b',
                r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})\b',
            ],
            'issuing_authority': [
                r'issu(?:ed|ing)\s+(?:by|authority)\s*[:\-=]?\s*([A-Z][A-Za-z0-9\s&,\.\-]{3,60}?)(?:\n|\.|$)',
                r'authority\s*[:\-=]\s*([A-Z][A-Za-z0-9\s&,\.\-]{3,60}?)(?:\n|\.|$)',
                r'(?:this is to certify|certified)\s+.{0,80}?\bby\s+(?:the\s+)?([A-Z][A-Za-z0-9\s&,\.\-]{3,60}?)(?:\n|\.|$)',
                r'\b([A-Z][A-Za-z\s&]+(?:Ltd|Limited|Pvt|Corporation|Corp|Inc|LLP|Authority|Board|Council|Department|Ministry|University|Ins\w*tute|Commission)\.?)\b',
            ],
            'author': [
                r'(?:author|prepared|written)\s+by\s*[:\-=]?\s*([A-Z][A-Za-z\.\s]{2,40}?)(?:\n|\.|$)',
                r'issu(?:ed|ing)\s+(?:by|authority)\s*[:\-=]?\s*([A-Z][A-Za-z0-9\s&,\.\-]{3,60}?)(?:\n|\.|$)',
                r'signed\s+by\s*[:\-=]?\s*([A-Z][A-Za-z\.\s]{2,40}?)(?:\n|\.|$)',
            ],
            'reference_number': [
                r'(?:reference|ref|regd?|registration|certificate|cert|serial|sl|enrolment|enrollment|file|memo)\s*\.?\s*(?:no|number|#)\s*[:\-=]?\s*([A-Z0-9][A-Z0-9\-\/]{3,24})',
                r'\b([A-Z]{2,6}[\-\/]?\d{4,}[\-\/]?[A-Z0-9]*)\b',
            ],
        }
        
        # Try patterns for this field
        patterns = field_patterns.get(field_name, [])
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip()
                # Clean up value
                value = re.sub(r'\s+', ' ', value)  # Normalize spaces
                value = value.rstrip(',.')  # Remove trailing punctuation
                value = value.strip()
                
                if value and len(value) > 1:  # Avoid single character matches
                    logger.info(f"Extracted {field_name}: {value}")
                    return value, 0.9
        
        # Not found
        logger.debug(f"Field {field_name} not found in text")
        return None, 0.0
    
    @staticmethod
    def _get_field_name(field: Any) -> str:
        """Extract field name from field definition."""
        if isinstance(field, dict):
            return field.get("name", str(field))
        return str(field)
    
    @staticmethod
    def _get_field_info(fields: List[Any], field_name: str) -> Dict[str, Any]:
        """Get field metadata from schema."""
        for field in fields:
            if isinstance(field, dict) and field.get("name") == field_name:
                return field
        return {}
    
    def _parse_llm_response(
        self, 
        raw_response: str, 
        fields: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Parse LLM response to extract field values and confidence.
        
        Args:
            raw_response: Raw LLM output
            fields: List of field definitions from schema
            
        Returns:
            List of parsed fields with value and confidence
        """
        # Try to find JSON in the response
        match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if not match:
            logger.warning("No JSON found in LLM response")
            return [
                {
                    "field": self._get_field_name(f), 
                    "value": None, 
                    "confidence": 0.0
                } 
                for f in fields
            ]
        
        try:
            parsed = json.loads(match.group())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM: {e}")
            return [
                {
                    "field": self._get_field_name(f), 
                    "value": None, 
                    "confidence": 0.0
                } 
                for f in fields
            ]
        
        # Extract field values
        results = []
        for field in fields:
            field_name = self._get_field_name(field)
            field_data = parsed.get(field_name, {})
            
            # Handle both dict format and direct value
            if isinstance(field_data, dict):
                value = field_data.get("value")
                confidence = field_data.get("confidence", 0.0)
            else:
                value = field_data
                confidence = 0.7 if value is not None else 0.0
            
            results.append({
                "field": field_name,
                "value": value,
                "confidence": float(confidence) if confidence is not None else 0.0
            })
        
        return results
