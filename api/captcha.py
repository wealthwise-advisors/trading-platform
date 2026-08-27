"""Cloudflare Turnstile, dormant until it is configured.

WHY TURNSTILE AND NOT reCAPTCHA
-------------------------------
It is free at any volume, it does not require the visitor to identify puzzle
tiles, and for most people it resolves without any interaction at all. It also
does not build an advertising profile of whoever is signing up, which reCAPTCHA
does and which is awkward to explain in a privacy policy.

DORMANT IS A SUPPORTED STATE
----------------------------
With no secret key configured, `verify` returns True and registration works
exactly as if there were no CAPTCHA. That is deliberate: the alternative is an
application that cannot create accounts until an unrelated third-party account
exists, and a deploy that half-works is worse than one that works without a
control it was never given.

It is logged at startup, once, so "dormant" is a thing someone can see rather
than something they have to infer.

FAIL CLOSED, NOT OPEN
---------------------
Once a key IS configured, a token that cannot be checked -- Cloudflare
unreachable, a timeout, a malformed reply -- is a refusal, not a pass. A
verifier that waves people through whenever the network hiccups is one outage
away from being no verifier at all, and an attacker can cause that outage by
flooding it.
"""

import logging
import os
import urllib.error
import urllib.parse
import urllib.request

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


VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

#: The site key is PUBLIC -- it is rendered into the page and identifies the
#: widget. The secret key is not, and never reaches the browser.
SITE_KEY_ENV = "AUTOTRADER_TURNSTILE_SITE_KEY"
SECRET_KEY_ENV = "AUTOTRADER_TURNSTILE_SECRET_KEY"

#: Short: this sits in the middle of a signup a person is waiting on, and
#: Cloudflare answers in tens of milliseconds when it answers at all.
TIMEOUT_SECONDS = 5.0


def site_key() -> str:
    """The public key the sign-up page needs, or '' when unconfigured."""
    return os.environ.get(SITE_KEY_ENV, "").strip()


def _secret() -> str:
    return os.environ.get(SECRET_KEY_ENV, "").strip()


def configured() -> bool:
    """True when BOTH keys are present.

    Both, because either alone is a misconfiguration that fails in a confusing
    direction: a site key with no secret renders a widget whose answer is never
    checked, which looks protected and is not.
    """
    return bool(site_key() and _secret())


def verify(token: str, remote_ip: str = "") -> bool:
    """Check a Turnstile token. True when it is good, or when unconfigured."""
    secret = _secret()
    if not secret:
        return True                      # dormant -- see the module docstring

    if not token:
        return False

    data = {"secret": secret, "response": token}
    if remote_ip:
        # Cloudflare uses this to spot a token being replayed from elsewhere.
        data["remoteip"] = remote_ip

    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        _https_only(VERIFY_URL), data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # nosec B310 -- _https_only enforces the scheme
            import json
            payload = json.load(resp)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        # Fail CLOSED. See the module docstring.
        log.warning("Turnstile verification failed to complete: %s", exc)
        return False

    if not payload.get("success"):
        log.info("Turnstile rejected a token: %s", payload.get("error-codes"))
        return False
    return True


def describe() -> str:
    """One line for the startup log."""
    return ("Turnstile: ACTIVE" if configured() else
            f"Turnstile: dormant (set {SITE_KEY_ENV} and {SECRET_KEY_ENV} to enable)")
