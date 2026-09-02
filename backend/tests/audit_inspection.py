import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000"

def get(url, token=None):
    req = urllib.request.Request(f"{BASE}{url}")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

def post(url, data=None, token=None):
    req = urllib.request.Request(f"{BASE}{url}", method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    body = json.dumps(data).encode() if data else b"{}"
    try:
        with urllib.request.urlopen(req, data=body) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

def patch(url, data=None, token=None):
    req = urllib.request.Request(f"{BASE}{url}", method="PATCH")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    body = json.dumps(data).encode() if data else b"{}"
    try:
        with urllib.request.urlopen(req, data=body) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

print("=== 1. DEMO USERS AND LOGIN TOKENS ===")
status, demo_data = get("/api/auth/demo-users")
demo_users = demo_data.get("users", [])
print(f"Status: {status}, Count: {len(demo_users)}")

tokens = {}
for u in demo_users:
    role = u["role"]
    email = u["email"]
    # Login
    l_status, l_resp = post("/api/auth/login", {"email": email, "password": "aiia2026"})
    if l_status == 200:
        token = l_resp["access_token"]
        tokens[role] = (token, u)
        # Decode token payload structure without verify
        import base64
        payload_b64 = token.split(".")[1] + "=="
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
        print(f"[{role.upper()}] Email: {email} | Claims: sub={payload.get('sub')}, role={payload.get('role')}, site_id={payload.get('site_id')}, subject_id={payload.get('subject_id')}, jti={payload.get('jti')}")
    else:
        print(f"[{role.upper()}] Login FAILED: {l_status} {l_resp}")

print("\n=== 2. PATIENT LOGIN TEST ===")
p_status, p_data = get("/api/auth/patient/demo-users")
p_email = p_data["users"][0]["email"]
p_status, p_resp = post("/api/auth/patient/login", {"email": p_email, "password": "aiia2026"})
print(f"Patient Login ({p_email}): {p_status}")
if p_status == 200:
    p_token = p_resp["access_token"]
    tokens["patient"] = (p_token, p_resp["user"])
    payload_b64 = p_token.split(".")[1] + "=="
    payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
    print(f"[PATIENT] Claims: sub={payload.get('sub')}, role={payload.get('role')}, site_id={payload.get('site_id')}, subject_id={payload.get('subject_id')}")

print("\n=== 3. SCOPE ENFORCEMENT AUDIT ===")
# PI is at site 1 (e.g., Delhi). Let's find site 2.
s_status, s_resp = get("/api/sites", tokens["admin"][0])
sites = s_resp.get("items", [])
print(f"Available Sites: {[(s['id'], s['site_code'], s['name']) for s in sites]}")
site1_id = sites[0]["id"] if len(sites) > 0 else 1
site2_id = sites[1]["id"] if len(sites) > 1 else 2

# Test A: PI site-scoped checks
pi_tok = tokens["principal_investigator"][0]
print("\n--- Test A: PI Site Scoping ---")
# PI accessing own site
code, res = get(f"/api/sites/{site1_id}", pi_tok)
print(f"PI accessing Site #{site1_id} (own site): {code}")
# PI accessing cross-site
code, res = get(f"/api/sites/{site2_id}", pi_tok)
print(f"PI accessing Site #{site2_id} (cross site): {code} (Expect 403) -> Detail: {res.get('detail')}")

# Test B: Coordinator site-scoped checks
coord_tok = tokens["coordinator"][0]
print("\n--- Test B: Coordinator Site Scoping ---")
code, res = get(f"/api/sites/{site2_id}/subjects", coord_tok)
print(f"Coordinator accessing Site #{site2_id} subjects: {code} (Expect 403) -> Detail: {res.get('detail')}")

# Test C: Ethics Committee access to subjects
ethics_tok = tokens["ethics_committee"][0]
print("\n--- Test C: Ethics Committee Subject Privacy Gate ---")
code, res = get("/api/subjects", ethics_tok)
print(f"Ethics Committee calling GET /api/subjects: {code} (Expect 403) -> Detail: {res.get('detail')}")

# Test D: Regulator and Sponsor Write Block
reg_tok = tokens["regulator"][0]
spon_tok = tokens["sponsor"][0]
print("\n--- Test D: Regulator & Sponsor Write Block ---")
code, res = post("/api/subjects", {"full_name": "Hack Subject", "site_id": site1_id}, reg_tok)
print(f"Regulator attempting POST /api/subjects: {code} (Expect 403) -> Detail: {res.get('detail')}")
code, res = post("/api/adverse-events", {"term_verbatim": "Hack AE", "site_id": site1_id}, spon_tok)
print(f"Sponsor attempting POST /api/adverse-events: {code} (Expect 403) -> Detail: {res.get('detail')}")

print("\n=== 4. CROSS-MODULE INTEGRATION AUDIT ===")
# Check trial ethics gate
trials_status, trials_resp = get("/api/trials", tokens["admin"][0])
trials = trials_resp.get("items", [])
if trials:
    target_trial = trials[0]
    t_id = target_trial["id"]
    print(f"Testing Trial #{t_id} ({target_trial['protocol_number']}) - Current Status: {target_trial['status']}")
    
    # Sponsor activates trial
    code, res = post(f"/api/trials/{t_id}/activate", token=spon_tok)
    print(f"Sponsor activating trial: {code} -> Response: {res}")

    # Check Safety Signals calculation
    code, res = get(f"/api/trials/{t_id}/safety-signals", spon_tok)
    print(f"Safety Signals query: {code} -> Signals Count: {len(res.get('items', [])) if isinstance(res, dict) else len(res)}")

print("\n=== AUDIT COMPLETE ===")
