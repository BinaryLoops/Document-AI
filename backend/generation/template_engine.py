"""
generation/template_engine.py — Dynamic field mapping, validation, and
                                  required-field enforcement.

Loads the 5 JSON templates from generation/templates/ once at import time.
Validates a submitted field dict against the template schema and returns
a normalised list of DocumentField objects ready for PDF rendering.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from generation.models import DocumentField, DocumentType
from core.logging import get_logger

logger = get_logger(__name__)

# ── Load all templates at import time ─────────────────────────────────────────
_TEMPLATE_DIR = Path(__file__).parent / "templates"

_TEMPLATES: Dict[str, Dict] = {}

_TEMPLATE_FILES = {
    DocumentType.PASSPORT:           "passport.json",
    DocumentType.DRIVING_LICENSE:    "driving_license.json",
    DocumentType.BIRTH_CERTIFICATE:  "birth_certificate.json",
    DocumentType.INCOME_CERTIFICATE: "income_certificate.json",
    DocumentType.LAND_RECORD:        "land_record.json",
}

for _dt, _fname in _TEMPLATE_FILES.items():
    _path = _TEMPLATE_DIR / _fname
    try:
        _TEMPLATES[_dt.value] = json.loads(_path.read_text(encoding="utf-8"))
        logger.debug("Loaded template: %s", _fname)
    except Exception as _e:
        logger.error("Failed to load template %s: %s", _fname, _e)


# ── Public helpers ────────────────────────────────────────────────────────────

def get_template(doc_type: DocumentType) -> Dict:
    """Return raw template dict.  Raises ValueError if not found."""
    tmpl = _TEMPLATES.get(doc_type.value)
    if tmpl is None:
        raise ValueError(f"No template for document type: {doc_type.value}")
    return tmpl


def get_required_supporting_docs(doc_type: DocumentType) -> List[str]:
    return get_template(doc_type).get("supporting_docs_required", [])


def get_display_name(doc_type: DocumentType) -> str:
    return get_template(doc_type).get("display_name", doc_type.value)


def get_issuing_authority_name(doc_type: DocumentType) -> str:
    return get_template(doc_type).get("issuing_authority", "Government of India")


def get_validity_years(doc_type: DocumentType) -> Optional[int]:
    return get_template(doc_type).get("validity_years")


# ── Validation ────────────────────────────────────────────────────────────────

class FieldValidationError(Exception):
    """Raised when submitted fields fail validation."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _validate_field(
    name: str,
    value: Any,
    field_schema: Dict,
) -> Tuple[Any, Optional[str]]:
    """
    Validate and coerce a single field value.

    Returns (coerced_value, error_message).
    error_message is None on success.
    """
    ftype    = field_schema.get("type", "text")
    required = field_schema.get("required", True)
    label    = field_schema.get("label", name)

    # ── Missing value ─────────────────────────────────────────────────────
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            return None, f"'{label}' is required."
        # Apply default if available
        default = field_schema.get("default")
        return default, None

    # ── Type coercion & validation ────────────────────────────────────────
    if ftype == "text" or ftype == "textarea":
        value = str(value).strip()
        max_len = field_schema.get("max_length")
        if max_len and len(value) > max_len:
            return None, f"'{label}' exceeds max length of {max_len} characters."
        pattern = field_schema.get("pattern")
        if pattern and not re.fullmatch(pattern, value):
            return None, f"'{label}' format is invalid (expected pattern: {pattern})."
        return value, None

    if ftype == "date":
        # Accept ISO dates (YYYY-MM-DD) or common Indian format (DD/MM/YYYY)
        value = str(value).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return value, None
        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", value):
            parts = value.split("/")
            return f"{parts[2]}-{int(parts[1]):02d}-{int(parts[0]):02d}", None
        return None, f"'{label}' must be a date in YYYY-MM-DD or DD/MM/YYYY format."

    if ftype == "number":
        try:
            return float(str(value).replace(",", "")), None
        except ValueError:
            return None, f"'{label}' must be a number."

    if ftype == "enum":
        options = field_schema.get("options", [])
        if str(value) not in options:
            return None, f"'{label}' must be one of: {', '.join(options)}."
        return str(value), None

    # Unknown type — accept as-is
    return value, None


def validate_and_map(
    doc_type: DocumentType,
    submitted: Dict[str, Any],
) -> Tuple[List[DocumentField], Dict[str, Any]]:
    """
    Validate all submitted fields against the template schema.

    Returns:
        (fields_list, normalised_dict)

    Raises:
        FieldValidationError — if any required field is missing or invalid.
    """
    tmpl   = get_template(doc_type)
    errors: List[str] = []
    fields: List[DocumentField] = []
    norm:   Dict[str, Any] = {}

    for section in tmpl.get("sections", []):
        section_name = section.get("name", "General")
        for fschema in section.get("fields", []):
            fname = fschema["name"]
            raw   = submitted.get(fname)
            coerced, err = _validate_field(fname, raw, fschema)

            if err:
                errors.append(err)
                continue

            norm[fname] = coerced
            fields.append(DocumentField(
                name=fname,
                label=fschema.get("label", fname),
                value=coerced,
                required=fschema.get("required", True),
                section=section_name,
            ))

    if errors:
        raise FieldValidationError(errors)

    return fields, norm


def get_template_field_list(doc_type: DocumentType) -> List[Dict]:
    """
    Return a flat list of all field schemas for the given document type.
    Used by the API to tell clients what fields are expected.
    """
    tmpl   = get_template(doc_type)
    result = []
    for section in tmpl.get("sections", []):
        for fschema in section.get("fields", []):
            result.append({
                "name":     fschema["name"],
                "label":    fschema.get("label", fschema["name"]),
                "type":     fschema.get("type", "text"),
                "required": fschema.get("required", True),
                "section":  section.get("name", "General"),
                "options":  fschema.get("options", []),
                "max_length": fschema.get("max_length"),
                "pattern":  fschema.get("pattern"),
                "help":     fschema.get("help", ""),
                "default":  fschema.get("default"),
            })
    return result
