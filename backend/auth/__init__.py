"""
auth/ — Government-grade authentication and authorisation for DocuMind AI.

Modules
-------
  models.py         — All dataclasses/enums (Role, User, Session, Device, …)
  database.py       — In-memory + JSON-persisted stores
  hashing.py        — bcrypt password hashing + Aadhaar token derivation
  jwt_handler.py    — Access/refresh token lifecycle
  otp_handler.py    — Phone OTP generation, validation, lockout
  mfa.py            — TOTP setup, verify, backup codes (Official/Admin/IssAuth)
  session_manager.py— Device fingerprinting, session CRUD, IP/login history
  rbac.py           — Permission enum, role map, FastAPI dependency factories
  routes.py         — All /auth/* API endpoints
"""
