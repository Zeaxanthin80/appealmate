"""Verify the Vercel WSGI adapter end to end, locally.

Starts the real api/index.py `app` under wsgiref, then exercises every route
over HTTP exactly as Vercel would. Exits non-zero on any failure.
"""
import json
import sys
import threading
import time
import urllib.request
from wsgiref.simple_server import make_server

sys.path.insert(0, ".")
import api.index as mod  # noqa: E402

PORT = 8099
failures = []


def check(label, cond, detail=""):
    print("%-46s %s %s" % (label, "PASS" if cond else "FAIL", detail))
    if not cond:
        failures.append(label)


server = make_server("127.0.0.1", PORT, mod.app)
threading.Thread(target=server.serve_forever, daemon=True).start()
time.sleep(0.4)
base = "http://127.0.0.1:%d" % PORT


def get(path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return r.status, r.read().decode()


def post(path, payload):
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, r.read().decode()


# --- health ---
st, body = get("/api/health")
check("GET /api/health -> 200", st == 200, body[:60])
check("health payload ok", json.loads(body).get("status") == "ok")

# --- UI + slides are served ---
st, body = get("/")
check("GET / -> 200 html", st == 200 and "AppealMate" in body)
st, body = get("/slides")
check("GET /slides -> 200 html", st == 200 and "Slide" not in body and "AppealMate" in body)

# --- full conversation over HTTP ---
st, body = post("/api/session", {})
sid = json.loads(body)["session_id"]
check("POST /api/session -> intro", st == 200 and "Aria" in body)

turns = [
    "Maria Fernandez",
    "A123456789",
    "a heart CT scan, they said it wasn't medically necessary and a stress test "
    "should come first, but my stress test was inconclusive and I cannot "
    "exercise because of my knees",
    "Dr. Rodriguez",
    "yes, it was denied",
]
last = None
for text in turns:
    st, body = post("/api/session/%s/say" % sid, {"text": text})
    last = json.loads(body)

# The interview is the step where Aria gathers the facts her argument rests on.
check("interview phase reached", last and last.get("state") == "interview",
      (last or {}).get("state", "?"))

for answer in ("chest pain when I walk",
               "a treadmill test last April, it was inconclusive",
               "I cannot walk on a treadmill, my knees are too bad",
               "my brother died of a heart attack at 58"):
    st, body = post("/api/session/%s/say" % sid, {"text": answer})
    last = json.loads(body)

check("conversation reaches 'drafted'", last and last.get("state") == "drafted",
      (last or {}).get("state", "?"))
check("draft cites real CPB 0228", "0228" in (last or {}).get("policy_citation", ""))
check("draft uses the patient's own words",
      "chest pain when i walk" in (last or {}).get("appeal_text", "").lower())

st, body = post("/api/session/%s/say" % sid, {"text": "file it"})
filed = json.loads(body)
check("'file it' -> filed", filed.get("state") == "filed")
check("confirmation returned", str(filed.get("form", {}).get("confirmation", "")).startswith("AM-"))

# --- session survives a fresh load (the serverless-relevant path) ---
st, body = get("/api/session/%s" % sid)
check("GET session -> 200", st == 200)
check("trace persisted", len(json.loads(body).get("trace", [])) > 5)

# --- evidence + audit ---
st, body = get("/api/evidence")
check("GET /api/evidence -> 200", st == 200, body[:80])
st, body = get("/api/audit")
check("GET /api/audit -> 200", st == 200 and len(json.loads(body)) > 0)

# --- 404 path ---
try:
    get("/api/nope")
    check("unknown route -> 404", False, "no error raised")
except urllib.error.HTTPError as e:
    check("unknown route -> 404", e.code == 404)

server.shutdown()
print("\n%s (%d failure(s))" % ("ALL PASS" if not failures else "FAILURES", len(failures)))
for f in failures:
    print("  -", f)
sys.exit(1 if failures else 0)
