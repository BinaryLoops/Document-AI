"""
Document type definitions and descriptions for classification.
P2 requirement: 8-10 document types with descriptions.
"""

from typing import Dict, List

# Document type definitions with descriptions for embedding-based classification
DOCUMENT_TYPES = {
    "APPLICATION": {
        "name": "Application",
        "description": "Government application forms, job applications, permit applications, license applications, registration forms, application for benefits, service request forms",
        "keywords": ["application", "form", "applicant", "apply", "request", "registration", "enrollment"]
    },
    "IDENTITY_PROOF": {
        "name": "Identity Proof",
        "description": "Identity documents including Aadhaar card, PAN card, passport, driver's license, voter ID card, national ID, employee ID, student ID",
        "keywords": ["aadhaar", "pan", "passport", "license", "voter", "identity", "identification", "ID card"]
    },
    "ADDRESS_PROOF": {
        "name": "Address Proof",
        "description": "Address verification documents including utility bills, bank statements, rental agreements, property documents, ration card, domicile certificate",
        "keywords": ["address", "residence", "domicile", "utility bill", "electricity", "water bill", "rental", "lease"]
    },
    "AFFIDAVIT": {
        "name": "Affidavit",
        "description": "Sworn statements, affidavits, statutory declarations, notarized statements, oath documents, legal declarations",
        "keywords": ["affidavit", "sworn", "oath", "declare", "notary", "notarized", "solemnly", "affirm"]
    },
    "CERTIFICATE": {
        "name": "Certificate",
        "description": "Certificates including birth certificate, death certificate, marriage certificate, educational certificates, experience certificates, caste certificate, income certificate",
        "keywords": ["certificate", "certify", "certified", "hereby certify", "issued", "attestation"]
    },
    "COURT_DOCUMENT": {
        "name": "Court Document",
        "description": "Court orders, judgments, summons, petitions, court notices, legal proceedings, case documents, court rulings",
        "keywords": ["court", "judge", "honorable", "petition", "plaintiff", "defendant", "case", "judgment", "order"]
    },
    "INVOICE": {
        "name": "Invoice",
        "description": "Invoices, bills, receipts, payment requests, purchase orders, proforma invoices, tax invoices, billing statements",
        "keywords": ["invoice", "bill", "amount", "total", "payment", "due", "GST", "tax", "purchase"]
    },
    "CONTRACT": {
        "name": "Contract",
        "description": "Contracts, agreements, memorandums of understanding (MOU), service agreements, employment contracts, lease agreements, terms and conditions",
        "keywords": ["contract", "agreement", "party", "parties", "terms", "conditions", "hereby agree", "MOU"]
    },
    "RECEIPT": {
        "name": "Receipt",
        "description": "Payment receipts, acknowledgment receipts, transaction confirmations, proof of payment, fee receipts",
        "keywords": ["receipt", "received", "acknowledgment", "paid", "transaction", "confirmation", "ref no"]
    },
    "OTHER": {
        "name": "Other",
        "description": "Miscellaneous documents, letters, notices, memos, reports, statements that don't fit other categories",
        "keywords": ["document", "letter", "notice", "memo", "report", "statement"]
    }
}


def get_document_type_list() -> List[str]:
    """Get list of all document type names."""
    return [dt["name"] for dt in DOCUMENT_TYPES.values()]


def get_document_type_descriptions() -> Dict[str, str]:
    """Get mapping of document type names to descriptions."""
    return {dt["name"]: dt["description"] for dt in DOCUMENT_TYPES.values()}


def get_document_type_keywords() -> Dict[str, List[str]]:
    """Get mapping of document type names to keywords."""
    return {dt["name"]: dt["keywords"] for dt in DOCUMENT_TYPES.values()}


def get_all_document_types() -> Dict[str, Dict]:
    """Get complete document type definitions."""
    return {key: value for key, value in DOCUMENT_TYPES.items()}
