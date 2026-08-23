# CHANGELOG — Phase AUTH
## Government-Grade Authentication System

**Date:** 2026-08-22  
**Status:** Complete — 36/36 tests passing  
**Base:** merged-backend (DocuMind AI + SIH Phase-1)

---

## What Was Built

A production-oriented, government-grade authentication and authorisation layer added to the DocuMind AI unified backend. Zero existing APIs were removed or modified.

---

## New Files

| File | Purpose |
|------|---------|
| `auth/__init__.py` | Package docstring |
| `auth/models.py` | All domain dataclasses and enums |
| `auth/database.py` | In-memory + JSON-persisted stores |
| `auth/hashing.py` | bcrypt passwords, HMAC-Aadhaar, SHA-256 OTP/token hashing |
| `auth/jwt_handler.py` | JWT access-token and opaque refresh-token lifecycle |
| `auth/otp_handler.py` | Phone OTP generation, delivery simulation, validation, lockout |
| `auth/mfa.py` | TOTP setup/verify, backup codes |
| `auth/session_manager.py` | Device fingerprinting, session CRUD, IP tracking, login history, account lockout |
| `auth/rbac.py` | Permission enum, role-permission map, FastAPI dependency factories |
| `auth/routes.py` | All `/auth/*` API endpoints (11 endpoints) |
| `test_auth.py` | Automated endpoint test suite (36 assertions) |
| `test_citizen_otp.py` | Manual citizen OTP completion helper |

## Modified Files

| File | Change |
|------|--------|
| `main.py` | Auth store load/flush in lifespan; auth router registered before RAG init |
| `core/config.py` | 14 new auth settings added to `Settings` |
| `requirements.txt` | Added: `passlib[bcrypt]`, `PyJWT`, `pyotp`, `user-agents` |
| `.env.example` | Full auth configuration block documented |

---

## Four Roles

### Citizen
- **Authentication:** Aadhaar number (12-digit) + Phone OTP (6-digit, 5-min TTL)
- **Permissions:** `read_own_documents`, `upload_documents`, `request_generation`
- **Flow:** `POST /auth/login` → returns `otp_id` → `POST /auth/otp` → JWT tokens

### Government Official
- **Authentication:** Employee ID + Password + TOTP MFA (RFC 6238)
- **Permissions:** `read_case_documents`, `upload_case_files`, `verify_document`, `verify_jurisdiction`
- **Restriction:** Jurisdiction-scoped access only (`user.jurisdiction` validated per request)
- **Flow:** `POST /auth/login` → returns `session_token` (if MFA enabled) → `POST /auth/mfa` → JWT tokens

### System Admin
- **Authentication:** Employee ID + Password + TOTP MFA
- **Permissions:** `read_all_documents`, `audit_logs`, `monitor_system`, `manage_departments`, `manage_users`
- **Restriction:** Cannot generate, sign, or edit issued documents (not in role's permission set)
- **Extra endpoint:** `POST /auth/admin/revoke-user` — force-revoke any user's sessions

### Issuing Authority
- **Authentication:** Department code + Password + TOTP MFA; digital certificate fields stored (`cert_serial`, `cert_thumbprint`)
- **Permissions:** `read_all_documents`, `upload_documents`, `generate_document`, `digitally_sign`, `revoke_document`, `reissue_document`, `verify_document`
- **Note:** `edit_issued_document` is absent from all role permission sets by design

---

## API Endpoints

### Required by spec (all implemented)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | None | Step 1 — primary credential check for all roles |
| POST | `/auth/otp` | None | Step 2 (Citizen) — verify phone OTP |
| POST | `/auth/logout` | Bearer | Revoke current session + invalidate JTI |
| POST | `/auth/refresh` | None (body) | Rotate access + refresh tokens |
| GET | `/auth/me` | Bearer | Current user profile + permissions |
| GET | `/auth/devices` | Bearer | All registered devices for current user |
| POST | `/auth/revoke-session` | Bearer | Revoke specific session or all sessions |

### Additional endpoints implemented

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/mfa` | None (session_token) | Step 2 (Official/Admin/IssAuth) — verify TOTP or backup code |
| POST | `/auth/mfa/setup` | Bearer (role-gated) | Generate TOTP secret + QR URI + 8 backup codes |
| POST | `/auth/mfa/verify` | Bearer (role-gated) | Confirm TOTP code to activate MFA |
| GET | `/auth/history` | Bearer | Login event history (last N events) |
| POST | `/auth/admin/revoke-user` | Bearer (Admin only) | Force-revoke all sessions for any user |

---

## Security Features

### JWT
- Algorithm: HS256
- Access token TTL: 30 minutes (configurable via `ACCESS_TOKEN_TTL_MINUTES`)
- Refresh token: opaque 64-byte URL-safe random string, stored as SHA-256 hash
- Refresh token TTL: 7 days (configurable via `REFRESH_TOKEN_TTL_DAYS`)
- Token rotation: refresh token is single-use; each `/auth/refresh` call issues a new pair
- Revocation: JTI blocklist in memory (`_revoked_jtis` set); checked on every verify

### Password Hashing
- Algorithm: bcrypt (direct `bcrypt` package, rounds=12)
- Passlib 1.7.4 bypassed due to incompatibility with `bcrypt>=4.0`
- All passwords truncated to 72 bytes before hashing (bcrypt spec)

### Aadhaar Hashing
- Algorithm: HMAC-SHA256 with `AADHAAR_HMAC_KEY` environment variable
- Deterministic lookup: users found by Aadhaar hash without iterating all users
- Key not set → loud warning + insecure dev fallback (never silent)

### OTP
- 6-digit cryptographically secure random code (`secrets.randbelow`)
- Stored as SHA-256 hash (fast; appropriate for 5-minute TTL)
- Constant-time comparison via `hmac.compare_digest`
- 5 max attempts before record is burned; new OTP required
- TTL: 300 seconds (configurable via `OTP_TTL_SECONDS`)
- Old OTPs invalidated on reissue

### MFA (TOTP)
- Standard RFC 6238, 30-second window, SHA-1 (pyotp default)
- Compatible with Google Authenticator, Authy, Microsoft Authenticator
- ±1 window drift tolerance (±30 seconds)
- 8 backup codes generated at setup (8-char alphanumeric, no ambiguous chars)
- Backup codes stored as SHA-256 hashes; single-use (consumed on verify)
- Setup requires confirmation TOTP before MFA is activated

### Account Lockout
- 5 consecutive failed attempts → account locked (configurable: `LOCKOUT_THRESHOLD`)
- Lock duration: 15 minutes (configurable: `LOCKOUT_DURATION_MINUTES`)
- Auto-unlock after duration expires
- Failed counter reset on successful login

### Device Fingerprinting
- SHA-256 of `(User-Agent + /24 IP subnet + Accept-Language)`
- Stable across browser restarts on same machine/network
- Per-user device registry with login count, first/last seen, browser/OS parsed via `user-agents`
- New device detection logged

### Session Management
- One session record per login; multiple concurrent sessions per user supported
- Session stores: `access_token_jti`, `refresh_token_hash`, `device_id`, `ip_address`, `user_agent`
- Sessions expire at `min(refresh_expires_at, session_ttl)` (8 hours default)
- `/auth/revoke-session` accepts specific `session_id` or revokes all

### IP Tracking
- Real IP extracted from `X-Forwarded-For` (proxy-aware)
- Recorded on every login event and session creation
- Stored in `LoginEvent` audit records

### Login History
- Every auth attempt (success and failure) logged to `LoginEvent` ring buffer (max 10,000)
- Event types: `success`, `failed_credentials`, `failed_otp`, `failed_mfa`, `locked_out`, `logout`, `token_refresh`, `session_revoked`, `password_changed`
- Accessible via `GET /auth/history`

### Request ID Correlation
- Every auth log line includes `rid=<request-id>` from `RequestIDMiddleware`
- Auth events traceable across the full request lifecycle

---

## RBAC Middleware

### `require_auth`
Returns the authenticated `User` for any valid Bearer token. Raises 401 if missing/expired/revoked.

### `require_role(*roles)`
Factory — gates an endpoint to specific roles. Raises 403 with role mismatch message.

### `require_permission(permission)`
Factory — gates an endpoint to users who have a specific `Permission`. Raises 403 if missing.

### `require_jurisdiction(jurisdiction)`
Factory — validates Government Officials are accessing only their assigned jurisdiction.

### Usage example
```python
from auth.rbac import require_role, require_permission, Permission
from auth.models import Role

# Role gate
@router.get("/admin/users", dependencies=[Depends(require_role(Role.SYSTEM_ADMIN))])
async def list_users(): ...

# Permission gate
@router.post("/sign", dependencies=[Depends(require_permission(Permission.DIGITALLY_SIGN))])
async def sign_document(): ...
```

---

## Persistence

Auth state is stored in `auth_store.json` (path configurable via `AUTH_STORE_PATH`).

- Loaded at startup via `auth.database.load()`
- Flushed at shutdown via `auth.database.flush()` (graceful shutdown in lifespan)
- Demo users re-seeded automatically if missing from store
- In production: replace with a proper database (PostgreSQL, Firestore, etc.)

---

## Demo Credentials (Development Only)

| Role | Credential | Value |
|------|-----------|-------|
| Citizen | Aadhaar | `123456789012` |
| Citizen | Phone | `+919876543210` |
| Government Official | Employee ID | `GOV-MH-10042` |
| Government Official | Password | `Official@1234` |
| System Admin | Employee ID | `ADMIN-001` |
| System Admin | Password | `Admin@9999` |
| Issuing Authority | Department Code | `COLLECTOR-PUNE` |
| Issuing Authority | Password | `IssAuth@5678` |

**Change all credentials before any production deployment.**

---

## Production Checklist

- [ ] Set `JWT_SECRET_KEY` to a 32-byte random hex string
- [ ] Set `AADHAAR_HMAC_KEY` to a 32-byte random hex string
- [ ] Set `APP_ENV=production`
- [ ] Set `CORS_ORIGINS` to explicit allowed origins (never `*`)
- [ ] Wire `_send_sms()` in `auth/otp_handler.py` to a real SMS gateway
- [ ] Replace JSON file persistence with a proper database
- [ ] Enable MFA for all non-Citizen users (`user.mfa_enabled = True` after setup)
- [ ] Rotate demo user credentials and remove demo seed before go-live
- [ ] Set `LOG_LEVEL=WARNING` and `LOG_FORMAT=json`
- [ ] Configure HTTPS via reverse proxy (nginx, Caddy, Railway)
- [ ] Review and implement `SECURITY_GAP_REPORT.md` items C1-C3 (CORS, auth on delete endpoints, file size limits)

---

## Bugs Fixed During Implementation

| # | Bug | Fix |
|---|-----|-----|
| 1 | `passlib 1.7.4` incompatible with `bcrypt>=4.0` — `ValueError: password cannot be longer than 72 bytes` on init | Replaced all passlib calls with direct `bcrypt` package + `hashlib.sha256` for OTP/backup codes |
| 2 | Auth router registered inside `_init_components` which exits early when `numpy` is missing | Moved auth store load + router registration to lifespan, before `_init_components` |
| 3 | `_seed_demo_users()` only called when store file absent; existing empty/partial stores got 0 users | Added `_ensure_demo_users()` — idempotent check called after every successful store load |
| 4 | `hash_backup_codes` imported from `auth.hashing` but defined in `auth.mfa` | Fixed import in `auth/routes.py` |
| 5 | Non-ASCII em-dash in warning strings causing PowerShell stderr encoding errors | Replaced `—` with `--` in all log strings |

---

## Test Results

```
36 PASSED | 0 FAILED
```

Coverage:
- System endpoints (/, /health, /version, /status, /diagnostics, /readiness)
- Unauthenticated access rejection (401 on all protected endpoints)
- Citizen login → OTP issue → OTP verify → JWT tokens (full flow)
- Government Official login (password auth, tokens issued)
- System Admin login
- Issuing Authority login
- GET /auth/me (all 3 non-citizen roles + invalid token)
- GET /auth/devices
- GET /auth/history
- POST /auth/refresh (rotation + old-token rejection + garbage-token rejection)
- POST /auth/revoke-session (session invalidation + subsequent request rejected)
- POST /auth/logout (JTI revocation + subsequent request rejected)
- MFA setup + TOTP verify (full TOTP flow)
- RBAC permission enforcement (citizen blocked from MFA setup, non-admin blocked from admin endpoints)
- Admin force-revoke (unknown user 404, non-admin 403)
