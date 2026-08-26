"""Authentication: password hashing, sessions, and the guards that use them.

WHY A COOKIE AND NOT A TOKEN IN JAVASCRIPT
------------------------------------------
nginx serves the dashboard at / and proxies /api/ to this process, so the
browser and the API are one origin. That makes an HttpOnly cookie the simplest
correct choice: the value never reaches JavaScript, so an XSS bug cannot read
it, and nothing has to be stored in localStorage. A bearer token would have to
live somewhere script can reach, which is strictly worse here for no gain.

CSRF
----
The cookie is SameSite=Lax, so a browser will not attach it to a cross-site
POST/PUT/DELETE -- which is the request shape a CSRF attack needs. Top-level
GET navigation still carries it, and GETs in this API do not change state.
`require_user` additionally refuses a state-changing request that arrives
without a same-origin marker, so the protection does not rest on one control.

WHAT IS DELIBERATELY NOT HERE
-----------------------------
No registration. Accounts are created with scripts/manage_users.py by someone
with shell access. This is a two-person instance; a self-serve endpoint would
let anyone who reaches the URL provision themselves an account, and hiding the
button is not a control.

No OAuth. The four provider buttons are inert until real credentials exist,
and those belong in the server environment, never in a page the browser reads.
"""

import logging
import os
import time
from dataclasses import dataclass, field

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status

from db import users as repo

log = logging.getLogger(__name__)

COOKIE = "autotrader_session"

#: Set AUTOTRADER_INSECURE_COOKIE=1 only for local http:// development. In the
#: deployed stack nginx terminates TLS, so the cookie must be Secure.
_INSECURE = os.environ.get("AUTOTRADER_INSECURE_COOKIE") == "1"

#: argon2id at the library's defaults (64 MiB, t=3, p=4). Tuned by the library
#: rather than by us; raising it later is safe because each stored hash carries
#: the parameters it was made with.
_ph = PasswordHasher()

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


# ── passwords ────────────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(stored_hash: str, plain: str) -> bool:
    try:
        _ph.verify(stored_hash, plain)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    try:
        return _ph.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return False


def password_problem(pw: str) -> str | None:
    """Server-side strength check. Returns a reason, or None if acceptable."""
    if len(pw) < 12:
        return "Password must be at least 12 characters."
    if len(pw) > 256:                      # argon2 is fine with long inputs;
        return "Password must be at most 256 characters."   # this bounds cost
    classes = sum((any(c.islower() for c in pw), any(c.isupper() for c in pw),
                   any(c.isdigit() for c in pw),
                   any(not c.isalnum() for c in pw)))
    if classes < 3:
        return ("Password must combine at least three of: lowercase, uppercase, "
                "digits, symbols.")
    return None


# ── brute-force throttle ─────────────────────────────────────────────────────
@dataclass
class _Bucket:
    fails: int = 0
    blocked_until: float = 0.0
    seen: list[float] = field(default_factory=list)


class Throttle:
    """Delay-then-block, keyed on (ip, username) together.

    Keying on the pair matters: keying on username alone would let anyone lock
    a known account out by failing logins for it, which is a denial of service
    dressed up as a security control. An attacker changing IP gets a fresh
    budget, but they also lose the one they had -- and a per-IP ceiling still
    applies underneath.
    """

    MAX_FAILS = 6
    BLOCK_SECONDS = 300
    IP_MAX_FAILS = 30
    IP_WINDOW = 900

    def __init__(self) -> None:
        self._pairs: dict[tuple[str, str], _Bucket] = {}
        self._ips: dict[str, _Bucket] = {}

    def retry_after(self, ip: str, username: str) -> int:
        now = time.monotonic()
        for b in (self._pairs.get((ip, username.lower())), self._ips.get(ip)):
            if b and b.blocked_until > now:
                return int(b.blocked_until - now) + 1
        return 0

    def record_failure(self, ip: str, username: str) -> None:
        now = time.monotonic()
        b = self._pairs.setdefault((ip, username.lower()), _Bucket())
        b.fails += 1
        if b.fails >= self.MAX_FAILS:
            b.blocked_until = now + self.BLOCK_SECONDS
            b.fails = 0

        ib = self._ips.setdefault(ip, _Bucket())
        ib.seen = [t for t in ib.seen if now - t < self.IP_WINDOW]
        ib.seen.append(now)
        if len(ib.seen) >= self.IP_MAX_FAILS:
            ib.blocked_until = now + self.BLOCK_SECONDS
            ib.seen.clear()

    def record_success(self, ip: str, username: str) -> None:
        self._pairs.pop((ip, username.lower()), None)


throttle = Throttle()


def client_ip(request: Request) -> str:
    """The peer address, taking one hop of X-Forwarded-For from our own nginx.

    Only the LAST entry is trusted -- the header is client-controlled, and
    reading the first entry would let a caller forge whatever IP it liked and
    walk around the throttle.
    """
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[-1].strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]


# ── guards ───────────────────────────────────────────────────────────────────
def _unauthorised() -> HTTPException:
    # One shape for every failure: no hint about which part was wrong.
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                         detail="Authentication required.")


async def require_user(request: Request):
    """Every protected route depends on this. Returns the signed-in user.

    The cookie is read off the request rather than declared as a Cookie()
    parameter on purpose: a declared parameter is added to the OpenAPI schema
    of EVERY route that depends on this, so `autotrader_session` would appear
    in the documented parameters of all 26 endpoints. Reading it here keeps
    each endpoint's published contract exactly as it was before auth existed.
    """
    user = repo.resolve_session(request.cookies.get(COOKIE, ""))
    if user is None:
        raise _unauthorised()

    # Defence in depth beside SameSite=Lax: a state-changing request must look
    # same-origin. Browsers set Origin on cross-site POSTs, so a forged one is
    # rejected here even if a future cookie policy change let it through.
    if request.method not in _SAFE_METHODS:
        origin = request.headers.get("origin")
        if origin:
            host = request.headers.get("host", "")
            if host and not origin.endswith("//" + host):
                log.warning("cross-origin %s to %s from %s",
                            request.method, request.url.path, origin)
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail="Cross-origin request refused.")
    request.state.user = user
    return user


#: Convenience for router-level protection: `dependencies=[PROTECTED]`.
PROTECTED = Depends(require_user)


async def user_for_websocket(websocket) -> object | None:
    """Resolve the session for a WebSocket handshake.

    A WebSocket upgrade carries cookies like any other request, but it does NOT
    pass through the HTTP dependency chain -- protecting the routers does
    nothing for it, which is the usual way a socket is left open.
    """
    return repo.resolve_session(websocket.cookies.get(COOKIE, ""))


def set_session_cookie(response, raw_token: str) -> None:
    response.set_cookie(
        COOKIE, raw_token,
        max_age=int(repo.SESSION_TTL.total_seconds()),
        httponly=True,               # unreadable from JavaScript
        secure=not _INSECURE,        # HTTPS only, unless explicitly relaxed
        samesite="lax",              # not sent on cross-site state changes
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(COOKIE, path="/", httponly=True,
                           secure=not _INSECURE, samesite="lax")
