"""Vercel serverless entry point for AppealMate.

Vercel's Python runtime looks for a WSGI ``app`` callable in api/index.py. This
serves exactly the same endpoints as server.py — it is an adapter, not a second
implementation.

Local run:  python server.py          (the normal way, stdlib HTTPServer)
Vercel:     api/index.py is picked up automatically.

Test the adapter locally with any WSGI server, e.g.:
    python -c "from wsgiref.simple_server import make_server; \
      import api.index as m; make_server('127.0.0.1', 8090, m.app).serve_forever()"
"""

from __future__ import annotations

import json
import os
import re
import sys

# The project modules live one directory up from api/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent  # noqa: E402
import store  # noqa: E402

store.init_db()

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name: str) -> str:
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def _body(environ) -> dict:
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        length = 0
    raw = environ["wsgi.input"].read(length) if length else b""
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except (ValueError, TypeError):
        return {}


def _route(method: str, path: str, body: dict):
    """Return (status, content_type, body_text)."""
    if method == "GET":
        if path in ("/", "/index.html"):
            return 200, "text/html; charset=utf-8", _read("index.html")
        if path in ("/slides", "/slides.html"):
            return 200, "text/html; charset=utf-8", _read("slides.html")
        if path == "/api/health":
            return 200, "application/json", json.dumps({"status": "ok", "service": "appealmate"})
        if path == "/api/audit":
            return 200, "application/json", json.dumps(store.list_audit())
        if path == "/api/evidence":
            return 200, "application/json", json.dumps(store.run_counts())
        m = re.match(r"^/api/session/([^/]+)$", path)
        if m:
            got = agent.get_session(m.group(1))
            if got:
                return 200, "application/json", json.dumps(got)
            return 404, "application/json", json.dumps({"error": "unknown session"})
        return 404, "application/json", json.dumps({"error": "not found"})

    if method == "POST":
        if path == "/api/session":
            return 200, "application/json", json.dumps(agent.start_session())
        m = re.match(r"^/api/session/([^/]+)/say$", path)
        if m:
            return 200, "application/json", json.dumps(agent.send(m.group(1), body.get("text", "")))
        return 404, "application/json", json.dumps({"error": "not found"})

    return 405, "application/json", json.dumps({"error": "method not allowed"})


def app(environ, start_response):
    """WSGI application — the entry point Vercel's Python runtime looks for."""
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/") or "/"
    try:
        status, ctype, text = _route(method, path, _body(environ))
    except Exception as exc:  # never 500 without a body the demo can show
        status, ctype, text = 500, "application/json", json.dumps(
            {"error": "internal", "detail": type(exc).__name__})

    payload = text.encode("utf-8")
    start_response("%d %s" % (status, "OK" if status == 200 else "Error"),
                   [("Content-Type", ctype), ("Content-Length", str(len(payload)))])
    return [payload]
