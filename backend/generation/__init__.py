"""
generation/ — Government Document Generation Engine.

Modules (load order)
--------------------
  models.py          — All domain dataclasses and enums
  database.py        — In-memory + JSON-persisted document store
  templates/         — 5 JSON field-schema definitions
  template_engine.py — Dynamic field mapping and validation
  digital_signature.py — RSA-2048 sign/verify document hashes
  watermark.py       — Diagonal text watermarks + department stamps
  qr_generator.py    — QR code embedding verification metadata
  pdf_builder.py     — ReportLab PDF assembly pipeline
  workflow.py        — End-to-end generation orchestration
  routes.py          — All /generate/* and /generated/* API endpoints
"""
