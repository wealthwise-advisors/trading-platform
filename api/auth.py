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
import re
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


class SignupThrottle:
    """A budget for creating accounts, per IP.

    The login Throttle above is the wrong shape for this. It keys on
    (ip, username) and counts FAILURES, which suits a password guesser
    hammering one account -- and does nothing at all about registration, where
    every attempt uses a NEW username and every attempt succeeds. A thousand
    signups from one address would not register as a single failure.

    So this counts successes, keys on the address alone, and uses a long
    window: a person signs up once, and the second account from the same
    address within the hour is already unusual. Bots are the normal caller of
    a burst.

    Deliberately in front of the CAPTCHA rather than behind it: Turnstile costs
    a network round-trip to Cloudflare, so verifying first would let a flood
    turn into a flood of outbound requests. The cheap local check runs first.
    """

    MAX_PER_WINDOW = 5
    WINDOW_SECONDS = 3600
    BLOCK_SECONDS = 3600

    def __init__(self) -> None:
        self._ips: dict[str, _Bucket] = {}

    def retry_after(self, ip: str) -> int:
        b = self._ips.get(ip)
        if b and b.blocked_until > time.monotonic():
            return int(b.blocked_until - time.monotonic()) + 1
        return 0

    def record(self, ip: str) -> None:
        """Count one account creation attempt against this address."""
        now = time.monotonic()
        b = self._ips.setdefault(ip, _Bucket())
        b.seen = [t for t in b.seen if now - t < self.WINDOW_SECONDS]
        b.seen.append(now)
        if len(b.seen) >= self.MAX_PER_WINDOW:
            b.blocked_until = now + self.BLOCK_SECONDS
            b.seen.clear()


signup_throttle = SignupThrottle()


class RecoveryThrottle:
    """A sliding window for recovery. No punishment block.

    THE PROBLEM THIS REPLACES
    -------------------------
    SignupThrottle does not merely refuse the request over the limit -- it sets
    a fixed block and refuses EVERYTHING for the next quarter of an hour. So a
    person who pressed the button a few times too many was not slowed down,
    they were shut out, and nothing they could do shortened it. Reported twice:
    "one time is working, but the second time the email is not coming."

    It also shared one counter with registration, so signing up spent the
    allowance for forgetting a password.

    WHAT THIS DOES INSTEAD
    ----------------------
    Counts what happened in the last WINDOW_SECONDS and allows the request if
    that is under the cap. Nothing is punished, nothing is cleared, no penalty
    period is imposed. Ask ten times in a minute and the eleventh waits only
    until the oldest of the ten ages out -- seconds or a couple of minutes, not
    a flat fifteen. For anybody using this like a person it is invisible.

    WHY THERE IS A CAP AT ALL
    -------------------------
    Not to stop guessing -- there is nothing to guess here. It stops one person
    typing somebody else's address and burying them in mail, and it protects a
    shared, finite resource: the mail provider's free tier is a few hundred
    messages a day for the WHOLE application. Uncapped, one bored visitor
    exhausts it and nobody can register or reset anything until tomorrow.

    Keyed per IP, so one caller cannot spend anyone else's share.
    """

    MAX_PER_WINDOW = 12
    WINDOW_SECONDS = 600

    def __init__(self) -> None:
        self._ips: dict[str, list[float]] = {}

    def retry_after(self, ip: str) -> int:
        """Seconds until the caller may try again. 0 when they may go now."""
        now = time.monotonic()
        seen = [t for t in self._ips.get(ip, []) if now - t < self.WINDOW_SECONDS]
        self._ips[ip] = seen
        if len(seen) < self.MAX_PER_WINDOW:
            return 0
        # The oldest request in the window is the one whose expiry frees a slot.
        return int(self.WINDOW_SECONDS - (now - seen[0])) + 1

    def record(self, ip: str) -> None:
        now = time.monotonic()
        seen = [t for t in self._ips.get(ip, []) if now - t < self.WINDOW_SECONDS]
        seen.append(now)
        self._ips[ip] = seen


#: One budget per FLOW, not one shared between them.
#:
#: They shared a counter, on the reasoning that what matters is how much mail a
#: caller can cause. True in the abstract, and wrong in practice: asking for a
#: password reset a few times then trying "forgot username" met a refusal the
#: person had no way to connect to anything they had done. Two buttons, two
#: purposes, one invisible shared allowance -- the second one appearing broken.
#:
#: Twelve each in a rolling ten minutes. The ceiling on mail is now twice what
#: it was, which is still far below anything that troubles a sending domain,
#: and each flow answers only for its own use.
recovery_throttle = RecoveryThrottle()          # password reset
username_throttle = RecoveryThrottle()          # username reminder
verify_throttle = RecoveryThrottle()            # resend verification


#: Rejected outright regardless of length. Not a substitute for a real
#: breach-corpus check -- it is the shortlist that a determined guesser tries
#: first, and it costs nothing to refuse them.
_OBVIOUS_PASSWORDS = {
    "password", "passw0rd", "letmein", "welcome", "iloveyou", "admin",
    "qwerty", "qwertyuiop", "abc123", "123456", "1234567890", "monkey",
    "dragon", "football", "baseball", "sunshine", "princess", "trustno1",
    "autotrader", "tradingplatform", "changeme", "secret",
}

#: Twelve, matching what the sign-up page has always told people. Length is
#: the only password rule that reliably helps; composition rules mostly push
#: people towards Password1! and a sticky note.
MIN_PASSWORD_LENGTH = 12


#: Names the application needs for itself, or that would let one account
#: impersonate a system message. Case-insensitive, matched whole.
_RESERVED_USERNAMES = {
    "admin", "administrator", "root", "system", "support", "help", "security",
    "autotrader", "api", "auth", "login", "logout", "register", "me", "owner",
    "operator", "moderator", "staff", "null", "none", "undefined", "anonymous",
}

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9._-]{1,30})[a-zA-Z0-9]$")

#: Deliberately loose. The only proof an address works is a message arriving at
#: it, which is what verification is for -- so this rejects what cannot
#: possibly be an address rather than trying to decide what is one. Strict
#: regexes here mostly succeed at rejecting real, unusual, valid addresses.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$")


def username_problem(username: str) -> str | None:
    """Why this username is unacceptable, or None if it is fine."""
    if not _USERNAME_RE.match(username or ""):
        return ("Username must be 3-32 characters, letters, numbers, dot, "
                "underscore or hyphen, starting and ending with a letter or number.")
    if username.lower() in _RESERVED_USERNAMES:
        return "That username is reserved. Please choose another."
    return None


def email_problem(email: str) -> str | None:
    """Why this address is unacceptable, or None if it is fine.

    An address is REQUIRED to register. It is the only way to recover an
    account, and from v5 it is what an OAuth identity matches against -- an
    account with no address can never be reached by either.
    """
    if not (email or "").strip():
        return "An email address is required."
    if not _EMAIL_RE.match(email.strip()):
        return "That does not look like an email address."
    return None


def password_problem(password: str, *, username: str = "",
                     email: str = "") -> str | None:
    """Why this password is unacceptable, or None if it is fine."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > 256:
        # argon2 will hash anything, but an unbounded field is a free way to
        # make the server do expensive work on demand.
        return "Password must be at most 256 characters."

    # Kept from the original rule this function replaced. Composition rules are
    # weak next to length, but dropping one silently while merging two
    # functions would have quietly weakened every existing caller.
    classes = sum((any(c.islower() for c in password),
                   any(c.isupper() for c in password),
                   any(c.isdigit() for c in password),
                   any(not c.isalnum() for c in password)))
    if classes < 3:
        return ("Password must combine at least three of: lowercase, uppercase, "
                "digits, symbols.")

    flat = password.strip().lower()
    if flat in _OBVIOUS_PASSWORDS:
        return "That password is too easy to guess. Choose something else."
    if len(set(flat)) <= 2:
        return "That password is too repetitive. Choose something else."
    for other, label in ((username, "username"), (email.split("@")[0], "email")):
        if other and len(other) >= 4 and other.lower() in flat:
            return f"Password must not contain your {label}."
    return None


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
