"""
Verification module for document validation and consistency checking.
"""

from verification.document_comparison import DocumentComparison, FieldNormalizer
from verification.missing_document_checker import MissingDocumentChecker
from verification.readiness_score import ReadinessScoreCalculator

__all__ = [
    "DocumentComparison",
    "FieldNormalizer",
    "MissingDocumentChecker",
    "ReadinessScoreCalculator"
]
