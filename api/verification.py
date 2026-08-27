"""Email address verification, via Resend, dormant until it is configured.

WHY RESEND
----------
It is an HTTP API with one endpoint and no SDK requirement, so it adds no
dependency -- the call below is urllib. SES needs an AWS client and a sandbox
exit request; SMTP needs a long-lived credential and a port that many hosts
block outbound. Resend also does not require the sending domain to be verified
before it will deliver to the account owner's own address, which means this can
be tested before DNS is set up.

WHAT VERIFICATION IS ACTUALLY FOR
---------------------------------
Not to keep people out of the app. It is what makes email-matched OAuth safe:
signing in with Google finds a local account by address, so if an address could
be claimed merely by typing it, anyone could register with someone else's email
and then have that person's Google identity attach to the account they control.
An address stays a CLAIM until a link sent to it comes back.

DORMANT IS A SUPPORTED STATE
----------------------------
With no API key, `send_if_configured` logs and returns False. Registration
still works and the account is created unverified -- the address simply cannot
be proved yet, so anything gated on verification stays shut. Nothing pretends
to have sent a message that was never sent.

THE TOKEN
---------
Stored as a SHA-256 hash, exactly like a session token, so a leaked database
does not hand over working verification links. Single-use, and it expires:
a link that works forever is a permanent key to an account, sitting in an
inbox that may itself be compromised later.
"""

import json
import logging
import os
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from db import users as repo

log = logging.getLogger(__name__)


def _https_only(url: str) -> str:
    """Refuse anything that is not an https:// URL.

    urlopen is happy to fetch file:// and ftp://, so a URL that ever becomes
    configurable would let the environment redirect this call at the local
    filesystem. The constants below are hard-coded today; this is what keeps
    that true if one is ever made settable. It also satisfies bandit B310,
    which is right to ask.
    """
    if not url.startswith("https://"):
        raise ValueError(f"refusing a non-https endpoint: {url[:40]!r}")
    return url


API_URL = "https://api.resend.com/emails"

API_KEY_ENV = "AUTOTRADER_RESEND_API_KEY"
FROM_ENV = "AUTOTRADER_MAIL_FROM"
BASE_URL_ENV = "AUTOTRADER_PUBLIC_BASE_URL"

TIMEOUT_SECONDS = 10.0

#: Long enough to survive a message sitting unread overnight, short enough that
#: a forgotten link in an old inbox is not a standing key to the account.
TOKEN_TTL = timedelta(hours=24)


#: Why the last send failed, or "" after a success. Kept in memory only: it is
#: a diagnostic for the person who just pressed the button, not a record.
#:
#: Deliberately NOT logged-and-forgotten. Resend explains the refusal in the
#: response body, urlopen raises before anything reads it, and the process log
#: is on a host reachable only over SSH -- so the one sentence that says what is
#: wrong was being thrown away microseconds after it arrived.
_last_error: str = ""


def last_error() -> str:
    return _last_error


def _remember(reason: str) -> None:
    global _last_error
    _last_error = reason


def _explain(exc) -> str:
    """The provider's own words, where it gave any.

    urllib raises HTTPError for 4xx/5xx, and HTTPError is also a file object --
    reading it yields the body that says what was actually wrong. Truncated,
    because it is going into a log line and an HTTP response.
    """
    body = ""
    try:
        raw = exc.read()
        body = raw.decode("utf-8", "replace").strip() if raw else ""
    except Exception:
        body = ""
    code = getattr(exc, "code", None)
    if body:
        return f"{code or 'error'}: {body[:400]}"
    return f"{code or type(exc).__name__}: {exc}"


def _api_key() -> str:
    return os.environ.get(API_KEY_ENV, "").strip()


def _sender() -> str:
    return os.environ.get(FROM_ENV, "").strip()


def _base_url() -> str:
    return os.environ.get(BASE_URL_ENV, "").strip().rstrip("/")


def configured() -> bool:
    """True when a key, a sender and a base URL are all present.

    All three, because a verification email without an absolute link is
    useless, and a sender the domain does not authorise is silently dropped by
    the recipient's provider rather than bounced.
    """
    return bool(_api_key() and _sender() and _base_url())


def describe() -> str:
    """One line for the startup log."""
    if configured():
        return f"Email verification: ACTIVE (from {_sender()})"
    missing = [n for n, v in ((API_KEY_ENV, _api_key()), (FROM_ENV, _sender()),
                              (BASE_URL_ENV, _base_url())) if not v]
    return f"Email verification: dormant (set {', '.join(missing)} to enable)"


def new_token(user_id: int) -> str:
    """Mint a single-use verification token and record its hash."""
    raw = secrets.token_urlsafe(32)
    expires = (datetime.now() + TOKEN_TTL).isoformat(timespec="seconds")
    repo.new_verification_token(user_id, repo.hash_token(raw), expires)
    return raw


def send_if_configured(user_id: int, email: str, username: str) -> bool:
    """Send a verification link. False when unconfigured or the send failed.

    Never raises. A registration that succeeded must not be reported as failed
    because a mail provider was slow -- the account exists either way, and the
    person can ask for another link.
    """
    if not email:
        return False
    if not configured():
        log.info("email verification is dormant; %r registered unverified", username)
        return False

    try:
        token = new_token(user_id)
        link = f"{_base_url()}/api/auth/verify-email?token={token}"
        payload = {
            "from": _sender(),
            "to": [email],
            "subject": "Confirm your AutoTrader email address",
            "text": (
                f"Hello {username},\n\n"
                f"Confirm this address to finish setting up your AutoTrader "
                f"account:\n\n{link}\n\n"
                f"The link works once and expires in "
                f"{int(TOKEN_TTL.total_seconds() // 3600)} hours.\n\n"
                f"If you did not create this account, ignore this message -- "
                f"nothing further will happen.\n"
            ),
        }
        req = urllib.request.Request(
            _https_only(API_URL), data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {_api_key()}",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # nosec B310 -- _https_only enforces the scheme
            ok = 200 <= resp.status < 300
        if ok:
            _remember("")
            log.info("verification email sent to %s", _redact(email))
        return ok
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        reason = _explain(exc)
        _remember(reason)
        log.warning("could not send verification email to %s: %s",
                    _redact(email), reason)
        return False


def consume(token: str) -> int | None:
    """Spend a verification token. Returns the user id, or None.

    None covers unknown, already-used and expired alike -- there is nothing to
    gain from telling an unauthenticated caller which.
    """
    if not token:
        return None
    return repo.take_verification_token(repo.hash_token(token))


#: Deliberately shorter than the 24h verification window. A verification link
#: sits in an inbox as a convenience; a reset link is a live key to an account,
#: and the person asking for one is, by definition, at a keyboard right now.
RESET_TTL = timedelta(hours=1)


def new_reset_token(user_id: int) -> str:
    """Mint a single-use password-reset token and record its hash."""
    raw = secrets.token_urlsafe(32)
    expires = (datetime.now() + RESET_TTL).isoformat(timespec="seconds")
    repo.new_email_token(user_id, repo.hash_token(raw), expires, purpose="reset")
    return raw


def send_reset(user_id: int, email: str, username: str) -> bool:
    """Send a password-reset link. False when unconfigured or the send failed.

    Never raises, and the caller must not vary its response on the result --
    "we could not send you an email" and "there is no such account" are the
    same observable thing to whoever is probing, and one of them is an answer
    they should not get.
    """
    if not email or not configured():
        log.info("password reset requested for %r but mail is dormant", username)
        return False
    try:
        token = new_reset_token(user_id)
        link = f"{_base_url()}/autotrader_signin.html?reset={token}"
        payload = {
            "from": _sender(),
            "to": [email],
            "subject": "Reset your AutoTrader password",
            "text": (
                f"Hello {username},\n\n"
                f"Someone asked to reset the password on your AutoTrader "
                f"account. If that was you, set a new one here:\n\n{link}\n\n"
                f"The link works once and expires in "
                f"{int(RESET_TTL.total_seconds() // 60)} minutes.\n\n"
                f"If it was not you, ignore this message -- your password has "
                f"not changed, and nobody can use this link without your "
                f"inbox.\n"
            ),
        }
        req = urllib.request.Request(
            _https_only(API_URL), data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {_api_key()}",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # nosec B310 -- _https_only enforces the scheme
            ok = 200 <= resp.status < 300
        if ok:
            _remember("")
            log.info("password reset email sent to %s", _redact(email))
        return ok
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        reason = _explain(exc)
        _remember(reason)
        log.warning("could not send a reset email to %s: %s", _redact(email), reason)
        return False


def consume_reset(token: str, new_password_hash: str) -> int | None:
    """Spend a reset token and set the new password. Returns the user id."""
    if not token:
        return None
    return repo.take_reset_token(repo.hash_token(token), new_password_hash)


def _redact(email: str) -> str:
    """An address, enough to identify it in a log, not enough to harvest it."""
    name, _, domain = email.partition("@")
    if not domain:
        return "***"
    return f"{name[:2]}***@{domain}"
