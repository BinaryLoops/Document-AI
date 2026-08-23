"""Quick citizen OTP completion test — run after obtaining OTP from server log."""
import sys
import requests

BASE   = "http://127.0.0.1:8000"
OTP_ID = sys.argv[1] if len(sys.argv) > 1 else ""
CODE   = sys.argv[2] if len(sys.argv) > 2 else ""

if not OTP_ID or not CODE:
    print("Usage: python test_citizen_otp.py <otp_id> <code>")
    sys.exit(1)

r = requests.post(f"{BASE}/auth/otp", json={"otp_id": OTP_ID, "code": CODE})
print(f"POST /auth/otp  [{r.status_code}]")
d = r.json()

if r.status_code == 200:
    tok = d.get("access_token", "")
    print(f"  access_token : {tok[:40]}...")
    print(f"  token_type   : {d.get('token_type')}")
    print(f"  session_id   : {d.get('session_id')}")
    print(f"  role         : {d.get('user', {}).get('role')}")
    print(f"  permissions  : {d.get('permissions')}")

    # Confirm /auth/me
    me = requests.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {tok}"})
    print(f"\nGET /auth/me   [{me.status_code}]  role={me.json().get('role')}")

    # Test RBAC: citizen cannot access MFA setup
    mfa = requests.post(f"{BASE}/auth/mfa/setup", headers={"Authorization": f"Bearer {tok}"})
    print(f"POST /auth/mfa/setup (citizen -> expect 403): [{mfa.status_code}]  {mfa.json().get('detail','')[:80]}")

    print("\nCitizen flow COMPLETE")
else:
    print(f"  Error: {d}")
    sys.exit(1)
