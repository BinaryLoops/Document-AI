"""
digilocker — Government Digital Locker Backend
================================================

Full document lifecycle management:
  Upload → Scan → OCR → Classification → Verification → Encryption → Storage → Retrieval

Features:
  - AES-256 encryption at rest
  - Immutable audit trail & version history
  - Duplicate detection (content-hash + perceptual)
  - Malware scanning (pluggable: mock / ClamAV)
  - Preview & thumbnail generation
  - Controlled deletion with admin approval
"""

__version__ = "1.0.0"
