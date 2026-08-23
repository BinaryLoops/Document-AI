"""
verification_engine — Multi-layer Government Verification Engine
=================================================================

Pipeline (12 steps):
  Document Upload → OCR → AI Classification → Serial Verification →
  QR Verification → Template Verification → Issuing Authority Verification →
  Government Registry Verification → Ongoing Case Check → Duplicate Check →
  Fraud Score → Trust Badge

Trust badges:
  🟢 GREEN  — Fully verified
  🟡 YELLOW — Needs manual review
  🔴 RED    — Verification failed

Every verification result includes:
  confidence, evidence, timestamp, officer, verification_source
"""

__version__ = "1.0.0"
