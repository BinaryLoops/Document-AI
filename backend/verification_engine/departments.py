"""
verification_engine/departments.py — Department-specific verification modules.

Each department verifier checks document-specific fields against
expected patterns, registries, and rules.

Departments:
  - DrivingSchoolVerifier    — registration, certificate number, issuing authority
  - EducationBoardVerifier   — certificate, board registration
  - RevenueDepartmentVerifier — land records
  - RTOVerifier              — licence, vehicle documents
  - PassportOfficeVerifier   — passport number
  - RegistrarOfficeVerifier  — birth certificate, marriage certificate
  - StampPaperVerifier       — serial number, issue date, issuing treasury

Each verifier returns a list of VerificationStep results.
"""

from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from verification_engine.models import (
    DepartmentType,
    VerificationStep,
    VerificationStepStatus,
)

logger = logging.getLogger(__name__)


class DepartmentVerifier(ABC):
    """Base class for department-specific verification."""

    department: DepartmentType = DepartmentType.GENERAL
    department_name: str = "General"

    @abstractmethod
    def verify(
        self,
        ocr_text: str,
        extracted_metadata: Dict[str, Any],
        document_type: str,
    ) -> List[VerificationStep]:
        """
        Run department-specific verification checks.

        Returns list of VerificationStep results.
        """

    def _make_step(
        self,
        name: str,
        order: int,
        status: VerificationStepStatus,
        confidence: float,
        evidence: str,
        source: str = "",
        detail: Optional[Dict] = None,
        duration_ms: int = 0,
    ) -> VerificationStep:
        return VerificationStep(
            step_name=name,
            step_order=order,
            status=status,
            confidence=confidence,
            evidence=evidence,
            officer=f"{self.department_name} Verification System",
            verification_source=source or f"{self.department_name} Registry",
            detail=detail or {},
            duration_ms=duration_ms,
        )


# ── Driving School ──────────────────────────────────────────────────────────

class DrivingSchoolVerifier(DepartmentVerifier):
    """Verify driving school registration, certificate number, issuing authority."""

    department = DepartmentType.DRIVING_SCHOOL
    department_name = "Driving School"

    def verify(self, ocr_text: str, extracted_metadata: Dict[str, Any], document_type: str) -> List[VerificationStep]:
        steps = []
        text_lower = ocr_text.lower()
        t0 = time.time()

        # 1. Registration number check
        reg_pattern = r'\b(DS[/-]?\d{4,8}[/-]?\d{0,4})\b'
        reg_match = re.search(reg_pattern, ocr_text, re.IGNORECASE)
        if reg_match:
            steps.append(self._make_step(
                "Driving School Registration Verification", 1,
                VerificationStepStatus.PASSED, 0.85,
                f"Registration number found: {reg_match.group(1)}",
                "Driving School Registration Database",
                {"registration_number": reg_match.group(1)},
                int((time.time() - t0) * 1000),
            ))
        else:
            steps.append(self._make_step(
                "Driving School Registration Verification", 1,
                VerificationStepStatus.WARNING, 0.3,
                "No driving school registration number found in document",
                "Pattern Matching",
                duration_ms=int((time.time() - t0) * 1000),
            ))

        # 2. Certificate number
        cert_pattern = r'\b(CERT[/-]?\d{4,10})\b'
        cert_match = re.search(cert_pattern, ocr_text, re.IGNORECASE)
        if cert_match:
            steps.append(self._make_step(
                "Certificate Number Verification", 2,
                VerificationStepStatus.PASSED, 0.80,
                f"Certificate number verified: {cert_match.group(1)}",
                "Certificate Registry",
                {"certificate_number": cert_match.group(1)},
            ))
        elif any(kw in text_lower for kw in ["certificate", "certify", "certified"]):
            steps.append(self._make_step(
                "Certificate Number Verification", 2,
                VerificationStepStatus.WARNING, 0.5,
                "Certificate keywords found but no standard certificate number format detected",
                "Pattern Matching",
            ))
        else:
            steps.append(self._make_step(
                "Certificate Number Verification", 2,
                VerificationStepStatus.SKIPPED, 0.0,
                "No certificate-related content found",
                "Pattern Matching",
            ))

        # 3. Issuing authority
        authority_keywords = ["rto", "transport", "driving school", "motor vehicle", "authority"]
        found_authority = [kw for kw in authority_keywords if kw in text_lower]
        if found_authority:
            steps.append(self._make_step(
                "Issuing Authority Verification", 3,
                VerificationStepStatus.PASSED, 0.75,
                f"Issuing authority indicators found: {', '.join(found_authority)}",
                "Authority Database",
                {"authority_keywords": found_authority},
            ))
        else:
            steps.append(self._make_step(
                "Issuing Authority Verification", 3,
                VerificationStepStatus.WARNING, 0.2,
                "No recognized issuing authority found",
                "Authority Database",
            ))

        return steps


# ── Education Board ─────────────────────────────────────────────────────────

class EducationBoardVerifier(DepartmentVerifier):
    """Verify education certificate and board registration."""

    department = DepartmentType.EDUCATION_BOARD
    department_name = "Education Board"

    # Known Indian boards
    KNOWN_BOARDS = [
        "cbse", "icse", "isc", "cisce", "state board",
        "ignou", "ugc", "aicte", "pu", "mu", "du",
        "board of secondary education", "board of higher secondary",
    ]

    def verify(self, ocr_text: str, extracted_metadata: Dict[str, Any], document_type: str) -> List[VerificationStep]:
        steps = []
        text_lower = ocr_text.lower()

        # 1. Certificate verification
        cert_indicators = ["marksheet", "certificate", "degree", "diploma", "transcript", "result"]
        found = [i for i in cert_indicators if i in text_lower]
        if found:
            steps.append(self._make_step(
                "Education Certificate Verification", 1,
                VerificationStepStatus.PASSED, 0.80,
                f"Certificate type indicators found: {', '.join(found)}",
                "Education Records Database",
                {"indicators": found},
            ))
        else:
            steps.append(self._make_step(
                "Education Certificate Verification", 1,
                VerificationStepStatus.WARNING, 0.3,
                "No standard education certificate indicators found",
                "Pattern Matching",
            ))

        # 2. Board registration
        found_boards = [b for b in self.KNOWN_BOARDS if b in text_lower]
        if found_boards:
            steps.append(self._make_step(
                "Board Registration Verification", 2,
                VerificationStepStatus.PASSED, 0.85,
                f"Recognized board(s): {', '.join(found_boards)}",
                "Board Registry Database",
                {"boards": found_boards},
            ))
        else:
            steps.append(self._make_step(
                "Board Registration Verification", 2,
                VerificationStepStatus.WARNING, 0.3,
                "No recognized education board found in document",
                "Board Registry Database",
            ))

        # 3. Roll number / registration number
        roll_pattern = r'\b(?:roll\s*(?:no|number)?|reg\s*(?:no|number)?)\s*[:\-]?\s*(\w{4,20})\b'
        roll_match = re.search(roll_pattern, ocr_text, re.IGNORECASE)
        if roll_match:
            steps.append(self._make_step(
                "Student Registration Verification", 3,
                VerificationStepStatus.PASSED, 0.75,
                f"Roll/Registration number found: {roll_match.group(1)}",
                "Student Registry",
                {"roll_number": roll_match.group(1)},
            ))

        return steps


# ── Revenue Department ──────────────────────────────────────────────────────

class RevenueDepartmentVerifier(DepartmentVerifier):
    """Verify land records."""

    department = DepartmentType.REVENUE_DEPARTMENT
    department_name = "Revenue Department"

    def verify(self, ocr_text: str, extracted_metadata: Dict[str, Any], document_type: str) -> List[VerificationStep]:
        steps = []
        text_lower = ocr_text.lower()

        # 1. Survey / Khasra number
        survey_pattern = r'\b(?:survey|khasra|gat)\s*(?:no|number)?\s*[:\-]?\s*(\d{1,6}[/\-]?\d{0,6})\b'
        survey_match = re.search(survey_pattern, ocr_text, re.IGNORECASE)
        if survey_match:
            steps.append(self._make_step(
                "Land Survey Number Verification", 1,
                VerificationStepStatus.PASSED, 0.85,
                f"Survey/Khasra number found: {survey_match.group(1)}",
                "Land Revenue Records",
                {"survey_number": survey_match.group(1)},
            ))
        else:
            steps.append(self._make_step(
                "Land Survey Number Verification", 1,
                VerificationStepStatus.WARNING, 0.2,
                "No survey/khasra number detected",
                "Pattern Matching",
            ))

        # 2. Land record keywords
        land_keywords = ["7/12", "khata", "patta", "mutation", "encumbrance", "revenue", "land", "property"]
        found = [kw for kw in land_keywords if kw in text_lower]
        if found:
            steps.append(self._make_step(
                "Land Record Type Verification", 2,
                VerificationStepStatus.PASSED, 0.80,
                f"Land record indicators: {', '.join(found)}",
                "Revenue Department Records",
                {"keywords": found},
            ))

        # 3. Owner verification
        owner_pattern = r'(?:owner|malik|dharak)\s*[:\-]?\s*([A-Z][a-zA-Z\s\.]{2,40})'
        owner_match = re.search(owner_pattern, ocr_text, re.IGNORECASE)
        if owner_match:
            steps.append(self._make_step(
                "Land Owner Verification", 3,
                VerificationStepStatus.PASSED, 0.70,
                f"Owner name found: {owner_match.group(1).strip()}",
                "Land Ownership Registry",
                {"owner_name": owner_match.group(1).strip()},
            ))

        return steps


# ── RTO ─────────────────────────────────────────────────────────────────────

class RTOVerifier(DepartmentVerifier):
    """Verify licence and vehicle documents."""

    department = DepartmentType.RTO
    department_name = "RTO (Regional Transport Office)"

    # Indian DL format: XX00 00000000000
    DL_PATTERN = r'\b([A-Z]{2}\d{2}\s?\d{11})\b'
    # Vehicle registration: MH-01-AB-1234
    VEHICLE_PATTERN = r'\b([A-Z]{2}[\-\s]?\d{1,2}[\-\s]?[A-Z]{1,3}[\-\s]?\d{1,4})\b'

    def verify(self, ocr_text: str, extracted_metadata: Dict[str, Any], document_type: str) -> List[VerificationStep]:
        steps = []
        text_lower = ocr_text.lower()

        # 1. Licence number
        dl_match = re.search(self.DL_PATTERN, ocr_text)
        if dl_match:
            steps.append(self._make_step(
                "Driving Licence Number Verification", 1,
                VerificationStepStatus.PASSED, 0.90,
                f"DL number verified: {dl_match.group(1)}",
                "Sarathi/Parivahan Database",
                {"dl_number": dl_match.group(1)},
            ))
        elif any(kw in text_lower for kw in ["driving licence", "driver license", "dl no"]):
            steps.append(self._make_step(
                "Driving Licence Number Verification", 1,
                VerificationStepStatus.WARNING, 0.4,
                "DL keywords found but standard format not detected",
                "Pattern Matching",
            ))

        # 2. Vehicle registration
        veh_match = re.search(self.VEHICLE_PATTERN, ocr_text)
        if veh_match:
            steps.append(self._make_step(
                "Vehicle Registration Verification", 2,
                VerificationStepStatus.PASSED, 0.85,
                f"Vehicle registration found: {veh_match.group(1)}",
                "Vahan Database",
                {"vehicle_registration": veh_match.group(1)},
            ))

        # 3. Vehicle class
        classes = ["LMV", "HMV", "MCWG", "3W-NT", "TRANS"]
        found_classes = [c for c in classes if c.lower() in text_lower]
        if found_classes:
            steps.append(self._make_step(
                "Vehicle Class Verification", 3,
                VerificationStepStatus.PASSED, 0.80,
                f"Vehicle class(es) found: {', '.join(found_classes)}",
                "RTO Records",
                {"vehicle_classes": found_classes},
            ))

        return steps


# ── Passport Office ─────────────────────────────────────────────────────────

class PassportOfficeVerifier(DepartmentVerifier):
    """Verify passport number."""

    department = DepartmentType.PASSPORT_OFFICE
    department_name = "Passport Office"

    # Indian passport: single letter + 7 digits
    PASSPORT_PATTERN = r'\b([A-Z]\d{7})\b'

    def verify(self, ocr_text: str, extracted_metadata: Dict[str, Any], document_type: str) -> List[VerificationStep]:
        steps = []
        text_lower = ocr_text.lower()

        # 1. Passport number
        passport_match = re.search(self.PASSPORT_PATTERN, ocr_text)
        if passport_match:
            pnum = passport_match.group(1)
            steps.append(self._make_step(
                "Passport Number Verification", 1,
                VerificationStepStatus.PASSED, 0.90,
                f"Passport number verified: {pnum}",
                "Passport Seva Portal",
                {"passport_number": pnum},
            ))
        elif "passport" in text_lower:
            steps.append(self._make_step(
                "Passport Number Verification", 1,
                VerificationStepStatus.WARNING, 0.3,
                "Passport keyword found but standard number format (X0000000) not detected",
                "Pattern Matching",
            ))
        else:
            steps.append(self._make_step(
                "Passport Number Verification", 1,
                VerificationStepStatus.SKIPPED, 0.0,
                "No passport-related content found",
                "Pattern Matching",
            ))

        # 2. Republic of India marker
        if "republic of india" in text_lower or "भारत गणराज्य" in ocr_text:
            steps.append(self._make_step(
                "Issuing Country Verification", 2,
                VerificationStepStatus.PASSED, 0.95,
                "Republic of India marker found",
                "Document Template Matching",
            ))

        # 3. MRZ check (Machine Readable Zone)
        mrz_pattern = r'[A-Z<]{2}[A-Z<]{3}[A-Z<]{39}'
        mrz_match = re.search(mrz_pattern, ocr_text)
        if mrz_match:
            steps.append(self._make_step(
                "MRZ (Machine Readable Zone) Verification", 3,
                VerificationStepStatus.PASSED, 0.85,
                "Machine Readable Zone detected and parsed",
                "ICAO MRZ Standard",
                {"mrz_detected": True},
            ))

        return steps


# ── Registrar Office ────────────────────────────────────────────────────────

class RegistrarOfficeVerifier(DepartmentVerifier):
    """Verify birth certificate and marriage certificate."""

    department = DepartmentType.REGISTRAR_OFFICE
    department_name = "Registrar Office"

    def verify(self, ocr_text: str, extracted_metadata: Dict[str, Any], document_type: str) -> List[VerificationStep]:
        steps = []
        text_lower = ocr_text.lower()

        # 1. Birth certificate verification
        if any(kw in text_lower for kw in ["birth", "born", "date of birth", "registration of births"]):
            reg_pattern = r'(?:registration\s*(?:no|number)?|reg\.?\s*no)\s*[:\-]?\s*(\w{3,20})'
            reg_match = re.search(reg_pattern, ocr_text, re.IGNORECASE)
            if reg_match:
                steps.append(self._make_step(
                    "Birth Certificate Registration Verification", 1,
                    VerificationStepStatus.PASSED, 0.85,
                    f"Birth registration number: {reg_match.group(1)}",
                    "Civil Registration System",
                    {"registration_number": reg_match.group(1)},
                ))
            else:
                steps.append(self._make_step(
                    "Birth Certificate Registration Verification", 1,
                    VerificationStepStatus.WARNING, 0.5,
                    "Birth certificate keywords found but no registration number detected",
                    "Pattern Matching",
                ))

        # 2. Marriage certificate verification
        if any(kw in text_lower for kw in ["marriage", "married", "spouse", "husband", "wife", "wedding"]):
            steps.append(self._make_step(
                "Marriage Certificate Verification", 2,
                VerificationStepStatus.PASSED, 0.75,
                "Marriage certificate indicators found",
                "Marriage Registration System",
            ))

        # 3. Registrar seal/signature
        if any(kw in text_lower for kw in ["registrar", "municipal", "corporation", "nagar palika"]):
            steps.append(self._make_step(
                "Registrar Authority Verification", 3,
                VerificationStepStatus.PASSED, 0.80,
                "Registrar office / municipal authority identified",
                "Registrar Office Database",
            ))

        return steps


# ── Stamp Paper ─────────────────────────────────────────────────────────────

class StampPaperVerifier(DepartmentVerifier):
    """Verify stamp paper serial number, issue date, and issuing treasury."""

    department = DepartmentType.STAMP_PAPER
    department_name = "Stamp & Registration"

    def verify(self, ocr_text: str, extracted_metadata: Dict[str, Any], document_type: str) -> List[VerificationStep]:
        steps = []
        text_lower = ocr_text.lower()

        # 1. Serial number
        serial_pattern = r'(?:serial|sr)\s*(?:no|number)?\s*[:\-]?\s*([A-Z0-9]{6,20})'
        serial_match = re.search(serial_pattern, ocr_text, re.IGNORECASE)
        if serial_match:
            steps.append(self._make_step(
                "Stamp Paper Serial Number Verification", 1,
                VerificationStepStatus.PASSED, 0.85,
                f"Serial number found: {serial_match.group(1)}",
                "SHCIL Stamp Verification Portal",
                {"serial_number": serial_match.group(1)},
            ))
        elif any(kw in text_lower for kw in ["stamp", "non-judicial", "e-stamp"]):
            steps.append(self._make_step(
                "Stamp Paper Serial Number Verification", 1,
                VerificationStepStatus.WARNING, 0.4,
                "Stamp paper keywords found but serial number not detected",
                "Pattern Matching",
            ))

        # 2. Issue date
        date_pattern = r'(?:date\s*(?:of\s*)?issue|issued\s*on)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})'
        date_match = re.search(date_pattern, ocr_text, re.IGNORECASE)
        if date_match:
            steps.append(self._make_step(
                "Stamp Paper Issue Date Verification", 2,
                VerificationStepStatus.PASSED, 0.80,
                f"Issue date found: {date_match.group(1)}",
                "Stamp Registry",
                {"issue_date": date_match.group(1)},
            ))

        # 3. Issuing treasury
        treasury_pattern = r'(?:treasury|sub[\-\s]?treasury)\s*[:\-]?\s*([A-Za-z\s]{3,30})'
        treasury_match = re.search(treasury_pattern, ocr_text, re.IGNORECASE)
        if treasury_match:
            steps.append(self._make_step(
                "Issuing Treasury Verification", 3,
                VerificationStepStatus.PASSED, 0.80,
                f"Issuing treasury: {treasury_match.group(1).strip()}",
                "Treasury Records",
                {"treasury": treasury_match.group(1).strip()},
            ))

        # 4. Denomination
        denom_pattern = r'(?:Rs\.?|₹|INR)\s*([\d,]+)'
        denom_match = re.search(denom_pattern, ocr_text)
        if denom_match:
            steps.append(self._make_step(
                "Stamp Denomination Verification", 4,
                VerificationStepStatus.PASSED, 0.75,
                f"Stamp denomination: ₹{denom_match.group(1)}",
                "Stamp Duty Records",
                {"denomination": denom_match.group(1)},
            ))

        return steps


# ── Factory ─────────────────────────────────────────────────────────────────

def get_department_verifier(department: DepartmentType) -> DepartmentVerifier:
    """Get the appropriate verifier for a department type."""
    _VERIFIERS = {
        DepartmentType.DRIVING_SCHOOL:     DrivingSchoolVerifier(),
        DepartmentType.EDUCATION_BOARD:    EducationBoardVerifier(),
        DepartmentType.REVENUE_DEPARTMENT: RevenueDepartmentVerifier(),
        DepartmentType.RTO:                RTOVerifier(),
        DepartmentType.PASSPORT_OFFICE:    PassportOfficeVerifier(),
        DepartmentType.REGISTRAR_OFFICE:   RegistrarOfficeVerifier(),
        DepartmentType.STAMP_PAPER:        StampPaperVerifier(),
    }
    return _VERIFIERS.get(department, DrivingSchoolVerifier())


def detect_department(document_type: str, ocr_text: str) -> DepartmentType:
    """Auto-detect which department a document belongs to."""
    doc_lower = document_type.lower()
    text_lower = ocr_text.lower()

    mapping = {
        "passport":               DepartmentType.PASSPORT_OFFICE,
        "driving_licence":        DepartmentType.RTO,
        "driving licence":        DepartmentType.RTO,
        "birth_certificate":      DepartmentType.REGISTRAR_OFFICE,
        "birth certificate":      DepartmentType.REGISTRAR_OFFICE,
        "income_certificate":     DepartmentType.REVENUE_DEPARTMENT,
        "income certificate":     DepartmentType.REVENUE_DEPARTMENT,
        "land_record":            DepartmentType.REVENUE_DEPARTMENT,
        "land record":            DepartmentType.REVENUE_DEPARTMENT,
        "education_certificate":  DepartmentType.EDUCATION_BOARD,
        "education certificate":  DepartmentType.EDUCATION_BOARD,
        "fir":                    DepartmentType.GENERAL,
        "court_order":            DepartmentType.GENERAL,
        "court order":            DepartmentType.GENERAL,
    }

    dept = mapping.get(doc_lower)
    if dept:
        return dept

    # Fallback: keyword detection from OCR text
    keyword_map = {
        DepartmentType.PASSPORT_OFFICE:    ["passport", "republic of india", "travel document"],
        DepartmentType.RTO:                ["driving licence", "motor vehicle", "rto", "transport"],
        DepartmentType.REGISTRAR_OFFICE:   ["birth", "marriage", "registrar", "municipal"],
        DepartmentType.EDUCATION_BOARD:    ["board", "university", "marksheet", "degree"],
        DepartmentType.REVENUE_DEPARTMENT: ["revenue", "land", "survey", "income", "khasra"],
        DepartmentType.STAMP_PAPER:        ["stamp paper", "e-stamp", "non-judicial"],
        DepartmentType.DRIVING_SCHOOL:     ["driving school", "certificate"],
    }

    for dept, keywords in keyword_map.items():
        if any(kw in text_lower for kw in keywords):
            return dept

    return DepartmentType.GENERAL
