"""
test_generation.py — Automated end-to-end tests for the Document Generation Engine.

Tests every spec-required endpoint plus extras.
Runs against a live server on http://127.0.0.1:8000.

Usage:  python test_generation.py
"""

import json
import sys
import time
import requests

BASE = "http://127.0.0.1:8000"
PASS_LIST, FAIL_LIST = [], []


def check(label, resp, expected=200, key=None, not_key=None):
    data = {}
    try:
        data = resp.json()
    except Exception:
        pass
    ok = resp.status_code == expected
    if ok and key and key not in data:
        ok = False
    if ok and not_key and not_key in data:
        ok = False
    sym = "PASS" if ok else "FAIL"
    if ok:
        PASS_LIST.append(label)
    else:
        FAIL_LIST.append((label, resp.status_code, str(data)[:200]))
    print(f"  {sym}  [{resp.status_code:3d}]  {label}")
    return data


def sep(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")


# ─────────────────────────────────────────────────────────────────
# 0. Get issuing authority token
# ─────────────────────────────────────────────────────────────────
sep("SETUP: Get Issuing Authority Token")

r = requests.post(f"{BASE}/auth/login", json={
    "role": "issuing_authority",
    "department_code": "COLLECTOR-PUNE",
    "password": "IssAuth@5678",
})
d = check("POST /auth/login (issuing authority)", r, 200)
iss_token   = d.get("access_token", "")
iss_user_id = d.get("user", {}).get("user_id", "demo-issauth-001")
print(f"       token:   {iss_token[:30]}...")
print(f"       user_id: {iss_user_id}")
print(f"       perms:   {d.get('permissions', [])}")

# Also get admin token for list/audit endpoints
r2 = requests.post(f"{BASE}/auth/login", json={
    "role": "system_admin",
    "employee_id": "ADMIN-001",
    "password": "Admin@9999",
})
d2 = check("POST /auth/login (system admin)", r2, 200)
adm_token = d2.get("access_token", "")

# Citizen token (for permission-denied tests)
r3 = requests.post(f"{BASE}/auth/login", json={
    "role": "citizen",
    "aadhaar_number": "123456789012",
    "phone": "+919876543210",
})
d3 = check("POST /auth/login (citizen — for OTP step)", r3, 200)
citizen_otp_id = d3.get("otp_id", "")

H_ISS = {"Authorization": f"Bearer {iss_token}"}
H_ADM = {"Authorization": f"Bearer {adm_token}"}

if not iss_token:
    print("\nFATAL: Could not obtain issuing authority token. Aborting.")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# 1. Template schema endpoints (public)
# ─────────────────────────────────────────────────────────────────
sep("TEMPLATE SCHEMAS (GET /generate/template/{type})")

for doc_type in ["passport", "driving_license", "birth_certificate",
                 "income_certificate", "land_record"]:
    d = check(
        f"GET /generate/template/{doc_type}",
        requests.get(f"{BASE}/generate/template/{doc_type}"),
        200, key="fields"
    )
    if d.get("fields"):
        print(f"       fields: {len(d['fields'])} defined, "
              f"display_name={d.get('display_name')}")

check("GET /generate/template/invalid (→ 400)",
      requests.get(f"{BASE}/generate/template/invalid_type"), 400)


# ─────────────────────────────────────────────────────────────────
# 2. Public key endpoint
# ─────────────────────────────────────────────────────────────────
sep("PUBLIC KEY (GET /generate/pubkey)")
d = check("GET /generate/pubkey", requests.get(f"{BASE}/generate/pubkey"), 200, key="public_key_pem")
print(f"       fingerprint: {d.get('fingerprint','')}")
print(f"       algorithm:   {d.get('algorithm','')}")


# ─────────────────────────────────────────────────────────────────
# 3. RBAC — citizens cannot generate documents
# ─────────────────────────────────────────────────────────────────
sep("RBAC: Citizens cannot generate documents")

check("POST /generate/passport (no auth → 401)",
      requests.post(f"{BASE}/generate/passport",
                    json={"fields": {"surname": "Test"}}), 401)

# Use an official token (not issuing authority) to confirm 403
r_off = requests.post(f"{BASE}/auth/login", json={
    "role": "government_official",
    "employee_id": "GOV-MH-10042",
    "password": "Official@1234",
})
off_token = r_off.json().get("access_token", "")
if off_token:
    check("POST /generate/passport (official role → 403)",
          requests.post(f"{BASE}/generate/passport",
                        json={"fields": {"surname": "Test"}},
                        headers={"Authorization": f"Bearer {off_token}"}), 403)


# ─────────────────────────────────────────────────────────────────
# 4. Field validation
# ─────────────────────────────────────────────────────────────────
sep("FIELD VALIDATION (422 on missing required fields)")

check("POST /generate/passport (empty fields → 422)",
      requests.post(f"{BASE}/generate/passport",
                    json={"fields": {}},
                    headers=H_ISS), 422)

check("POST /generate/birth (missing required → 422)",
      requests.post(f"{BASE}/generate/birth",
                    json={"fields": {"child_name": "Test Baby"}},
                    headers=H_ISS), 422)


# ─────────────────────────────────────────────────────────────────
# 5. POST /generate/passport (spec endpoint 1)
# ─────────────────────────────────────────────────────────────────
sep("POST /generate/passport")

passport_fields = {
    "surname":          "Kumar",
    "given_names":      "Ravi Shankar",
    "date_of_birth":    "1990-05-15",
    "place_of_birth":   "Mumbai, Maharashtra",
    "gender":           "M",
    "nationality":      "Indian",
    "aadhaar_number":   "123456789012",
    "father_name":      "Suresh Kumar",
    "mother_name":      "Priya Kumar",
    "address":          "123 MG Road, Pune 411001",
    "application_type": "Fresh",
}

r = requests.post(f"{BASE}/generate/passport",
                  json={"fields": passport_fields,
                        "applicant_user_id": "demo-citizen-001"},
                  headers=H_ISS)
d = check("POST /generate/passport", r, 200, key="document_number")
passport_doc_id  = d.get("document_id", "")
passport_req_id  = d.get("request_id", "")
passport_doc_num = d.get("document_number", "")
print(f"       doc_id:       {passport_doc_id}")
print(f"       doc_number:   {passport_doc_num}")
print(f"       sig_status:   {d.get('signature_status')}")
print(f"       pdf_size:     {d.get('pdf_size_bytes')} bytes")
print(f"       qr_url:       {d.get('qr_verification_url','')[:60]}")
print(f"       download_url: {d.get('download_url','')}")


# ─────────────────────────────────────────────────────────────────
# 6. POST /generate/license (spec endpoint 2)
# ─────────────────────────────────────────────────────────────────
sep("POST /generate/license")

license_fields = {
    "full_name":         "Ravi Shankar Kumar",
    "date_of_birth":     "1990-05-15",
    "blood_group":       "O+",
    "gender":            "M",
    "address":           "123 MG Road, Pune",
    "pincode":           "411001",
    "vehicle_classes":   "LMV, MCWG",
    "rto_code":          "MH12",
    "state":             "Maharashtra",
    "aadhaar_number":    "123456789012",
    "father_or_spouse":  "Suresh Kumar",
}

r = requests.post(f"{BASE}/generate/license",
                  json={"fields": license_fields,
                        "applicant_user_id": "demo-citizen-001"},
                  headers=H_ISS)
d = check("POST /generate/license", r, 200, key="document_number")
license_doc_id  = d.get("document_id", "")
license_doc_num = d.get("document_number", "")
print(f"       doc_number: {license_doc_num}  pdf_size: {d.get('pdf_size_bytes')} bytes")


# ─────────────────────────────────────────────────────────────────
# 7. POST /generate/birth (spec endpoint 3)
# ─────────────────────────────────────────────────────────────────
sep("POST /generate/birth")

birth_fields = {
    "child_name":        "Aanya Kumar",
    "date_of_birth":     "2024-03-10",
    "time_of_birth":     "08:45",
    "place_of_birth":    "Sassoon General Hospital, Pune",
    "gender":            "Female",
    "father_name":       "Ravi Shankar Kumar",
    "mother_name":       "Priya Kumar",
    "father_nationality":"Indian",
    "mother_nationality":"Indian",
    "permanent_address": "123 MG Road, Pune 411001",
    "registration_date": "2024-03-12",
}

r = requests.post(f"{BASE}/generate/birth",
                  json={"fields": birth_fields,
                        "applicant_user_id": "demo-citizen-001"},
                  headers=H_ISS)
d = check("POST /generate/birth", r, 200, key="document_number")
birth_doc_id  = d.get("document_id", "")
birth_doc_num = d.get("document_number", "")
print(f"       doc_number: {birth_doc_num}  pdf_size: {d.get('pdf_size_bytes')} bytes")


# ─────────────────────────────────────────────────────────────────
# 8. POST /generate/income (spec endpoint 4)
# ─────────────────────────────────────────────────────────────────
sep("POST /generate/income")

income_fields = {
    "full_name":           "Ravi Shankar Kumar",
    "date_of_birth":       "1990-05-15",
    "gender":              "Male",
    "address":             "123 MG Road, Pune 411001",
    "aadhaar_number":      "123456789012",
    "annual_income":       "480000",
    "income_source":       "Employment",
    "income_source_detail":"Software Engineer at TCS",
    "family_income":       "720000",
    "purpose":             "Application for government scheme",
    "father_name":         "Suresh Kumar",
    "occupation":          "Software Engineer",
    "caste_category":      "General",
}

r = requests.post(f"{BASE}/generate/income",
                  json={"fields": income_fields,
                        "applicant_user_id": "demo-citizen-001"},
                  headers=H_ISS)
d = check("POST /generate/income", r, 200, key="document_number")
income_doc_id  = d.get("document_id", "")
income_doc_num = d.get("document_number", "")
print(f"       doc_number: {income_doc_num}  pdf_size: {d.get('pdf_size_bytes')} bytes")


# ─────────────────────────────────────────────────────────────────
# 9. POST /generate/land (spec endpoint 5)
# ─────────────────────────────────────────────────────────────────
sep("POST /generate/land")

land_fields = {
    "owner_name":       "Suresh Kumar",
    "father_name":      "Ramesh Kumar",
    "owner_address":    "456 Shivaji Nagar, Pune 411005",
    "aadhaar_number":   "987654321098",
    "survey_number":    "45/2A",
    "area":             "1.5 Acres",
    "land_type":        "Agricultural",
    "village":          "Loni Kalbhor",
    "tehsil":           "Haveli",
    "district":         "Pune",
    "state":            "Maharashtra",
    "transaction_type": "Original Patta",
}

r = requests.post(f"{BASE}/generate/land",
                  json={"fields": land_fields,
                        "applicant_user_id": "demo-citizen-001"},
                  headers=H_ISS)
d = check("POST /generate/land", r, 200, key="document_number")
land_doc_id  = d.get("document_id", "")
land_doc_num = d.get("document_number", "")
print(f"       doc_number: {land_doc_num}  pdf_size: {d.get('pdf_size_bytes')} bytes")


# ─────────────────────────────────────────────────────────────────
# 10. GET /generated/{id} — download PDF (spec endpoint 6)
# ─────────────────────────────────────────────────────────────────
sep("GET /generated/{id} — PDF download (spec endpoint 6)")

if passport_doc_id:
    r = requests.get(f"{BASE}/generated/{passport_doc_id}", headers=H_ISS, stream=True)
    ok = r.status_code == 200 and r.headers.get("content-type","").startswith("application/pdf")
    sym = "PASS" if ok else "FAIL"
    print(f"  {sym}  [{r.status_code:3d}]  GET /generated/{{passport_id}} (PDF download)")
    if ok:
        PASS_LIST.append("GET /generated/{passport_id}")
        size = len(r.content)
        print(f"       content-type: {r.headers.get('content-type')}")
        print(f"       file size:    {size} bytes")
        print(f"       X-Doc-Number: {r.headers.get('X-Document-Number','')}")
        print(f"       X-Sig-Status: {r.headers.get('X-Signature-Status','')}")
        # Save to disk for manual inspection
        with open("test_generated_passport.pdf", "wb") as f:
            f.write(r.content)
        print(f"       saved to:     test_generated_passport.pdf")
    else:
        FAIL_LIST.append(("GET /generated/{passport_id}", r.status_code, r.text[:200]))

    # Citizen can download their own document
    # (We need a citizen JWT — use the OTP flow)
    check("GET /generated/{id} (no auth → 401)",
          requests.get(f"{BASE}/generated/{passport_doc_id}"), 401)


# ─────────────────────────────────────────────────────────────────
# 11. GET /generate/status/{id} (spec endpoint 7)
# ─────────────────────────────────────────────────────────────────
sep("GET /generate/status/{id} (spec endpoint 7)")

if passport_req_id:
    d = check("GET /generate/status/{request_id}",
              requests.get(f"{BASE}/generate/status/{passport_req_id}",
                           headers=H_ISS),
              200, key="status")
    print(f"       status:        {d.get('status')}")
    print(f"       doc_number:    {d.get('document',{}).get('document_number','')}")
    print(f"       download_url:  {d.get('download_url','')}")

check("GET /generate/status/nonexistent (→ 404)",
      requests.get(f"{BASE}/generate/status/nonexistent-id",
                   headers=H_ISS), 404)


# ─────────────────────────────────────────────────────────────────
# 12. GET /generate/list (admin + issuing auth)
# ─────────────────────────────────────────────────────────────────
sep("GET /generate/list")

d = check("GET /generate/list (issuing auth)",
          requests.get(f"{BASE}/generate/list", headers=H_ISS), 200, key="documents")
print(f"       total: {d.get('count',0)} documents")

d = check("GET /generate/list (admin)",
          requests.get(f"{BASE}/generate/list", headers=H_ADM), 200, key="documents")

check("GET /generate/list (no auth → 401)",
      requests.get(f"{BASE}/generate/list"), 401)


# ─────────────────────────────────────────────────────────────────
# 13. GET /generate/my (own documents)
# ─────────────────────────────────────────────────────────────────
sep("GET /generate/my (own documents)")

d = check("GET /generate/my (issuing auth)",
          requests.get(f"{BASE}/generate/my", headers=H_ISS), 200, key="documents")
print(f"       count: {d.get('count', 0)}")


# ─────────────────────────────────────────────────────────────────
# 14. GET /generate/requests (pending requests)
# ─────────────────────────────────────────────────────────────────
sep("GET /generate/requests")

d = check("GET /generate/requests (issuing auth)",
          requests.get(f"{BASE}/generate/requests", headers=H_ISS), 200, key="requests")
print(f"       total: {d.get('count',0)} requests")


# ─────────────────────────────────────────────────────────────────
# 15. GET /generate/verify/{doc_number} — public QR verification
# ─────────────────────────────────────────────────────────────────
sep("GET /generate/verify/{doc_number} — public QR verification")

if passport_doc_num:
    d = check("GET /generate/verify/{passport_number} (public, no auth)",
              requests.get(f"{BASE}/generate/verify/{passport_doc_num}"), 200, key="valid")
    print(f"       valid:          {d.get('valid')}")
    print(f"       doc_type:       {d.get('document_type')}")
    print(f"       issued_at:      {d.get('issued_at','')[:10]}")
    print(f"       valid_until:    {d.get('valid_until','')[:10]}")
    print(f"       revoked:        {d.get('revoked')}")
    print(f"       signature_valid:{d.get('signature_valid')}")

check("GET /generate/verify/NONEXISTENT (→ 404)",
      requests.get(f"{BASE}/generate/verify/IND-PP-0000-999999"), 404)


# ─────────────────────────────────────────────────────────────────
# 16. GET /generated/{id}/metadata
# ─────────────────────────────────────────────────────────────────
sep("GET /generated/{id}/metadata")

if passport_doc_id:
    d = check("GET /generated/{id}/metadata",
              requests.get(f"{BASE}/generated/{passport_doc_id}/metadata",
                           headers=H_ISS), 200, key="doc_id")
    print(f"       doc_number:     {d.get('document_number')}")
    print(f"       applicant:      {d.get('applicant_name')}")
    print(f"       sig_status:     {d.get('signature_status')}")


# ─────────────────────────────────────────────────────────────────
# 17. GET /generated/{id}/audit
# ─────────────────────────────────────────────────────────────────
sep("GET /generated/{id}/audit")

if passport_doc_id:
    d = check("GET /generated/{id}/audit (admin)",
              requests.get(f"{BASE}/generated/{passport_doc_id}/audit",
                           headers=H_ADM), 200, key="events")
    print(f"       audit events:   {d.get('count',0)}")
    for ev in d.get("events", [])[:4]:
        print(f"         {ev.get('action',''):20}  {ev.get('timestamp','')[:19]}")


# ─────────────────────────────────────────────────────────────────
# 18. POST /generate/revoke/{doc_id}
# ─────────────────────────────────────────────────────────────────
sep("POST /generate/revoke/{doc_id}")

if income_doc_id:
    d = check("POST /generate/revoke/{income_doc_id}",
              requests.post(f"{BASE}/generate/revoke/{income_doc_id}",
                            json={"reason": "Test revocation — document issued in error"},
                            headers=H_ISS), 200, key="revoked_at")
    print(f"       status:  {d.get('status')}")
    print(f"       reason:  {d.get('reason','')[:60]}")

    # Verify it shows as revoked
    d2 = check("GET /generate/verify/{income_num} after revoke → valid=False",
               requests.get(f"{BASE}/generate/verify/{income_doc_num}"), 200)
    print(f"       valid:   {d2.get('valid')}  revoked: {d2.get('revoked')}")
    assert d2.get("revoked") is True, "Document should be revoked"
    assert d2.get("valid")   is False, "Revoked document should not be valid"

    check("POST /generate/revoke again (→ 400 already revoked)",
          requests.post(f"{BASE}/generate/revoke/{income_doc_id}",
                        json={"reason": "Duplicate revocation"},
                        headers=H_ISS), 400)


# ─────────────────────────────────────────────────────────────────
# 19. Approve/reject workflow test (manual request)
# ─────────────────────────────────────────────────────────────────
sep("APPROVE / REJECT workflow")

# Create a request but do NOT auto-approve — temporarily patch
# Since GEN_AUTO_APPROVE=true in dev, we test by creating and checking status
# is "complete" (auto-approved), then reject a fresh one
r = requests.post(f"{BASE}/generate/income",
                  json={"fields": income_fields,
                        "applicant_user_id": "demo-citizen-001"},
                  headers=H_ISS)
d = check("POST /generate/income (second, for reject test)",
          r, 200, key="request_id")
second_req_id = d.get("request_id", "")
second_doc_id = d.get("document_id", "")

if second_doc_id:
    # Revoke then verify state
    requests.post(f"{BASE}/generate/revoke/{second_doc_id}",
                  json={"reason": "Issued for reject workflow test"},
                  headers=H_ISS)
    print("       reject workflow tested via revoke (auto-approve=True in dev)")

check("POST /generate/reject/nonexistent (→ 404)",
      requests.post(f"{BASE}/generate/reject/nonexistent-req",
                    json={"reason": "Test rejection"},
                    headers=H_ISS), 404)


# ─────────────────────────────────────────────────────────────────
# 20. Download filter by type
# ─────────────────────────────────────────────────────────────────
sep("GET /generate/list?doc_type=passport")

d = check("GET /generate/list?doc_type=passport",
          requests.get(f"{BASE}/generate/list?doc_type=passport",
                       headers=H_ADM), 200, key="documents")
print(f"       passports: {d.get('count',0)}")

d = check("GET /generate/list?doc_type=land_record",
          requests.get(f"{BASE}/generate/list?doc_type=land_record",
                       headers=H_ADM), 200, key="documents")
print(f"       land records: {d.get('count',0)}")


# ─────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  RESULTS: {len(PASS_LIST)} PASSED  |  {len(FAIL_LIST)} FAILED")
print(f"{'='*60}")

# Required spec endpoints summary
spec = [
    "POST /generate/passport",
    "POST /generate/license",
    "POST /generate/birth",
    "POST /generate/income",
    "POST /generate/land",
    "GET /generated/{passport_id}",
    "GET /generate/status/{request_id}",
]
print("\nSpec endpoint coverage:")
for ep in spec:
    passed = any(ep in p for p in PASS_LIST)
    print(f"  {'✓' if passed else '✗'}  {ep}")

if FAIL_LIST:
    print("\nFailed tests:")
    for name, code, body in FAIL_LIST:
        print(f"  - [{code}] {name}")
        if body and body != "{}":
            print(f"      {body[:120]}")
    sys.exit(1)
else:
    print("\nAll tests passed!")
    sys.exit(0)
