"""Run the whole AutoTrader app on this machine: sign-in page + dashboard.

    py -3.12 scripts/run_local.py

Serves the sign-in page, the built dashboard and the API from ONE origin on
http://127.0.0.1:8800 -- the same shape nginx gives in production, which is
what makes the session cookie behave identically here and there.

Nothing about this touches the deployed server, and nothing here needs GitHub.

The local database lives in data/local-demo.db, separate from data/autotrader.db,
so trying things out here cannot disturb real results.
"""

import http.server
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = Path.home() / "OneDrive" / "Desktop"
API_PORT, WEB_PORT = 8801, 8800
BASE = f"http://127.0.0.1:{WEB_PORT}"

DB = ROOT / "data" / "local-demo.db"
env = dict(
    os.environ,
    AUTOTRADER_DB_PATH=str(DB),
    # This is plain http on localhost. A Secure cookie would never be stored by
    # the browser here, so the login would appear to do nothing at all.
    AUTOTRADER_INSECURE_COOKIE="1",
    PYTHONPATH=str(ROOT),
)


def find_pages() -> Path:
    """Collect the sign-in pages and the built dashboard into one folder."""
    site = ROOT / "data" / "local-site"
    site.mkdir(parents=True, exist_ok=True)
    found = []
    for name in ("autotrader_signin.html", "autotrader_signup.html"):
        for src in (DESKTOP / name, ROOT / "web" / "public" / name):
            if src.is_file():
                (site / name).write_bytes(src.read_bytes())
                found.append(name)
                break
    dist = ROOT / "web" / "dist"
    if dist.is_dir():
        import shutil
        for item in dist.iterdir():
            dest = site / item.name
            if item.is_dir():
                shutil.rmtree(dest, ignore_errors=True)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        found.append("dashboard (web/dist)")
    return site, found


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is a response to relay, not an instruction to obey.

    nginx hands a 3xx straight back to the browser in production; this makes
    the local rig behave the same way instead of chasing it server-side.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECT = urllib.request.build_opener(_NoRedirect)


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static files, with /api/ forwarded to the API on the same origin."""

    site: Path

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(self.site), **kw)

    def log_message(self, *a):
        pass

    def _proxy(self, method):
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(
            f"http://127.0.0.1:{API_PORT}{self.path}", data=body, method=method)
        for h in ("content-type", "cookie", "origin", "user-agent", "accept"):
            if self.headers.get(h):
                req.add_header(h, self.headers[h])
        try:
            # _NoRedirect, not urlopen: urlopen FOLLOWS a redirect itself, so an
            # OAuth start -- which answers 303 to accounts.google.com -- would be
            # fetched by this dev server instead of by the browser. The person
            # would never see the consent screen, and this process would be the
            # one talking to Google. A proxy must hand the 303 back untouched.
            with _NO_REDIRECT.open(req, timeout=120) as r:
                data, status, hdrs = r.read(), r.status, r.headers
        except urllib.error.HTTPError as e:
            data, status, hdrs = e.read(), e.code, e.headers
        except Exception as e:                       # API down or restarting
            data, status, hdrs = str(e).encode(), 502, {}
        self.send_response(status)
        for k, v in (hdrs.items() if hdrs else []):
            # `location` matters: without it a 3xx arrives as an empty body with
            # nowhere to go, and every redirect-based flow silently dead-ends.
            if k.lower() in ("content-type", "set-cookie", "location"):
                self.send_header(k, v)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._proxy("GET")
        if self.path in ("/", "/index.html"):
            # Land on the dashboard if it is built -- its own gate will send an
            # unauthenticated visitor to the sign-in page, which is the flow
            # worth seeing. Without a build, go straight to sign-in.
            self.path = "/index.html" if (self.site / "index.html").is_file() \
                else "/autotrader_signin.html"
        return super().do_GET()

    def do_POST(self):
        return self._proxy("POST")

    def do_DELETE(self):
        return self._proxy("DELETE")


def main() -> int:
    site, found = find_pages()
    Handler.site = site
    print(f"  serving: {', '.join(found) or 'nothing found!'}")

    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app",
         "--host", "127.0.0.1", "--port", str(API_PORT), "--log-level", "warning"],
        cwd=ROOT, env=env)

    for _ in range(120):
        try:
            socket.create_connection(("127.0.0.1", API_PORT), timeout=1).close()
            break
        except OSError:
            time.sleep(0.5)
    else:
        print("  the API did not start")
        api.terminate()
        return 1

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", WEB_PORT), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    print(f"\n  AutoTrader is running at  {BASE}")
    print(f"  sign-in page:             {BASE}/autotrader_signin.html")
    print(f"  database:                 {DB}")
    print("\n  No account yet?  py -3.12 scripts/manage_users.py add <username>")
    print("     (set AUTOTRADER_DB_PATH to the database above first)")
    print("\n  Ctrl+C to stop.\n")
    webbrowser.open(BASE)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  stopping…")
    finally:
        httpd.shutdown()
        api.terminate()
        try:
            api.wait(timeout=10)
        except subprocess.TimeoutExpired:
            api.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
