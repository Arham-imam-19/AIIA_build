import json
import urllib.request
import urllib.error
import base64

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

def decode_jwt(token):
    payload_b64 = token.split(".")[1] + "=="
    return json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())

print("=== 1. SPONSOR ROLE DIFFERENTIATION AUDIT ===")
# Login as sponsor
s_status, s_resp = post("/api/auth/login", {"email": "vikram.desai@demo.aiia-ctms.in", "password": "aiia2026"})
sponsor_token = s_resp["access_token"]
payload = decode_jwt(sponsor_token)
print(f"Decoded Sponsor Token Claims: {json.dumps(payload, indent=2)}")

# Query trials as sponsor
t_status, t_resp = get("/api/trials", sponsor_token)
print(f"GET /api/trials as Sponsor -> Status: {t_status}")
print(f"Response Body Sample: {json.dumps(t_resp, indent=2)[:400]}...")

print("\n=== 2. BLINDING CHECK FOR SPONSOR/DIRECTOR ===")
sub_status, sub_resp = get("/api/subjects", sponsor_token)
print(f"GET /api/subjects as Sponsor -> Status: {sub_status}")
if "items" in sub_resp and len(sub_resp["items"]) > 0:
    first_sub = sub_resp["items"][0]
    print(f"First Subject returned to Sponsor: {json.dumps(first_sub, indent=2)}")
    print(f"--> 'arm' field present in payload? {'arm' in first_sub} (Value: {first_sub.get('arm')})")

print("\n=== 3. ADVERSARIAL HALT TRIAL & AUDIT CHECK ===")
# Check trial status
t_id = t_resp["items"][0]["id"]
print(f"Trial #{t_id} current status: {t_resp['items'][0]['status']}")
