"""AppealMate — HTTP server. Stdlib only.

Run:  python server.py   (from the appealmate/ directory)
Then: http://localhost:8080

Endpoints:
  GET  /                     -> the voice UI
  GET  /slides               -> the presentation deck
  GET  /api/health           -> {"status":"ok"}
  POST /api/session          -> start a session; returns Aria's introduction
  POST /api/session/<id>/say -> {"text": "..."} caller's turn; returns Aria's reply
  GET  /api/session/<id>     -> session state + tool trace
  GET  /api/audit            -> append-only audit log
  GET  /api/evidence         -> run counts (the evidence denominator)
"""

from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

import agent
import store

PORT = int(os.environ.get("PORT", "8080"))


def _load(path: str) -> str:
    with open(os.path.join(os.path.dirname(__file__), path), encoding="utf-8") as f:
        return f.read()


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: dict, status: int = 200) -> None:
        self._send(json.dumps(payload).encode(), status)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        if self.path == "/":
            self._send(_load("index.html").encode(), 200, "text/html; charset=utf-8")
        elif self.path == "/slides":
            self._send(_load("slides.html").encode(), 200, "text/html; charset=utf-8")
        elif self.path == "/api/health":
            self._json({"status": "ok", "service": "appealmate"})
        elif self.path == "/api/audit":
            self._json(store.list_audit())
        elif self.path == "/api/evidence":
            self._json(store.run_counts())
        else:
            m = re.match(r"^/api/session/([^/]+)$", self.path)
            if m:
                got = agent.get_session(m.group(1))
                self._json(got if got is not None else {"error": "unknown session"}, 200 if got else 404)
            else:
                self._json({"error": "not found"}, 404)

    def do_POST(self):
        body = self._read_body()
        if self.path == "/api/session":
            self._json(agent.start_session())
            return
        m = re.match(r"^/api/session/([^/]+)/say$", self.path)
        if m:
            self._json(agent.send(m.group(1), body.get("text", "")))
            return
        self._json({"error": "not found"}, 404)

    def log_message(self, *args):
        pass


def main():
    store.init_db()
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print("AppealMate running at http://localhost:%d  (slides at /slides)" % PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
