"""Loopback owner desk. This server is never deployed with the website."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from http.cookies import SimpleCookie
import hmac
import html
import json
import secrets
from .store import Store, canonical, now, require
from .domain import ACTIONS, gate


def queue_html(store, policy):
    groups = {"Proposed / open": [], "Landed / deployment unverified": [], "Deployed / editorial work pending": []}
    tasks = sorted({e["task"] for e in store.events(kind="contract")})
    for task in tasks:
        c = store.latest(task, "candidate")
        landing = store.latest(task, "landing")
        deployment = store.latest(task, "feature-deployment")
        group = "Proposed / open" if not landing else "Deployed / editorial work pending" if deployment else "Landed / deployment unverified"
        status = gate(store, task, policy) if c else {"feature_evidence": ["No walkthrough candidate"], "ready": False}
        decision = store.latest(task, "choice")
        previous = store.events(task, "choice")
        media = ""
        if c:
            from .domain import candidate
            value = candidate(store, task)
            media = '<details><summary>Article and original figures</summary><pre>' + html.escape(store.get(value['article_hash']).decode()) + '</pre>'
            for e in value.get('evidence', []):
                media += f'<p>{html.escape(e["requirement_id"])} · {html.escape(e["section"])}</p><img style="max-width:100%" alt="Original workflow capture" src="/media/{e["original_hash"]}"><small>Original SHA-256: {e["original_hash"]}</small>'
            media += '</details>'
        controls = f'<form method="post" action="/choice-draft"><input type="hidden" name="task" value="{html.escape(task)}"><label>Decision <select name="action"><option value="" disabled selected>Choose an action</option>' + ''.join(f'<option>{a}</option>' for a in ACTIONS) + '</select></label><label>Reason (optional)<input name="reason" maxlength="2000"></label><button>Prepare choice for my signature</button></form>' if c else ''
        groups[group].append(f'<article><h3>{html.escape(task)}</h3><p>Owner choice: {html.escape(decision["action"] if decision else "Pending — no choice recorded")}</p><pre>{html.escape(json.dumps(status, indent=2))}</pre>{media}{controls}<details><summary>Immutable choice history ({len(previous)})</summary><pre>{html.escape(json.dumps(previous, indent=2))}</pre></details></article>')
    unassigned = [e["payload"] for e in store.events(kind="discovery") if e["task"] == "UNASSIGNED"]
    body = ''.join(f'<section><h2>{label}</h2>{"".join(rows) or "<p>No work in this phase.</p>"}</section>' for label, rows in groups.items())
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Owner editorial desk</title><style>body{{font:16px system-ui;background:#101c24;color:#e0e8e8;max-width:1100px;margin:3rem auto;padding:1rem}}h1,h2{{color:#87d8bd}}article{{background:#1c303c;padding:1.5rem;margin:1rem 0;border-radius:12px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}label{{display:block;margin:1rem 0}}input,select,button{{font:inherit;padding:.6rem;margin-left:.5rem}}button{{background:#87d8bd;border:0;border-radius:5px}}small{{color:#bbcdce}}</style><h1>Owner editorial desk</h1><p>Private engineering and editorial infrastructure. Choices affect prominence only.</p><small>Every choice needs your signature. Unselected candidates stay pending. Evidence, writing, confidence and owner gates remain separate.</small>{body}<section><h2>Needs task identity</h2><p>{len(unassigned)} discovery snapshots need an explicit shared Task identity or signed legacy mapping.</p></section></html>'''


def make_server(store, policy, token, port=8766):
    require(len(token) >= 32, "Set a random SHOWCASE_QUEUE_TOKEN of at least 32 characters")
    session = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # no tokens, paths, owner choices, or private source in access logs

        def reply(self, status, body, cookie=None):
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(body.encode())

        def host_ok(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def authorized(self):
            cookies = SimpleCookie()
            try:
                cookies.load(self.headers.get("Cookie", ""))
            except Exception:
                return False
            value = cookies.get("desk")
            return value is not None and hmac.compare_digest(value.value, session)

        def do_GET(self):
            if not self.host_ok():
                return self.reply(403, "Invalid host")
            if not self.authorized():
                return self.reply(401, '<h1>Private owner desk</h1><form action="/login" method="post"><label>Local access token <input type="password" name="token" autocomplete="off"></label><button>Open desk</button></form>')
            if self.path.startswith("/media/"):
                journal = Store(store.root)
                try:
                    key = self.path.removeprefix("/media/")
                    allowed = set()
                    from .domain import candidate
                    for event in journal.events(kind="contract"):
                        if journal.latest(event["task"], "candidate"):
                            for e in candidate(journal, event["task"]).get("evidence", []):
                                allowed.update((e["original_hash"], e["inline_hash"]))
                    if key not in allowed:
                        return self.reply(404, "Not found")
                    data = journal.get(key)
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png" if data.startswith(b'\x89PNG') else "image/jpeg")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(data)
                    return
                finally:
                    journal.db.close()
            if self.path != "/":
                return self.reply(404, "Not found")
            journal = Store(store.root)
            try:
                return self.reply(200, queue_html(journal, policy))
            finally:
                journal.db.close()

        def do_POST(self):
            from urllib.parse import parse_qs
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if not self.host_ok() or self.headers.get("Origin") != origin:
                return self.reply(403, "Invalid origin")
            try:
                size = int(self.headers.get("Content-Length", 0))
                require(0 < size <= 12000, "Invalid request size")
                require(self.headers.get("Content-Type", "").startswith("application/x-www-form-urlencoded"), "Wrong content type")
                data = parse_qs(self.rfile.read(size).decode(), strict_parsing=True)
                if self.path == "/login":
                    if not hmac.compare_digest(data.get("token", [""])[0], token):
                        return self.reply(403, "Access denied")
                    return self.reply(200, '<a href="/">Open owner desk</a>', f"desk={session}; HttpOnly; SameSite=Strict; Path=/")
                if not self.authorized():
                    return self.reply(401, "Access denied")
                require(self.path == "/choice-draft", "Unknown operation")
                task, action = data["task"][0], data["action"][0]
                require(action in ACTIONS, "Unknown choice")
                journal = Store(store.root)
                try:
                    c = journal.latest(task, "candidate")
                    history = journal.events(task, "choice")
                finally:
                    journal.db.close()
                require(c, "Candidate missing")
                payload = {"kind": "choice", "task_id": task, "actor": "owner", "at": now(), "action": action,
                           "reason": data.get("reason", [""])[0], "candidate_hash": c["candidate_hash"], "previous": history[-1]["hash"] if history else None}
                return self.reply(200, '<h1>Unsigned owner choice</h1><p>Save the exact bytes below as choice.json, sign them with your owner key, then import the envelope. No decision has been applied.</p><pre>' + html.escape(canonical(payload).decode()) + '</pre><p>See docs/showcase/OPERATIONS.md for the signature command.</p><a href="/">Back</a>')
            except (ValueError, KeyError):
                return self.reply(400, "Invalid request")
    return HTTPServer(("127.0.0.1", port), Handler)
