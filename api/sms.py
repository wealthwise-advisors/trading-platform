"""Text messages, dormant until a provider is configured.

WHY THIS EXISTS BEFORE ANY PROVIDER DOES
----------------------------------------
Nothing here can send a message today, and that is the intended state. The
blockers to real SMS on this project are not code:

  * every phone number in the database is UNVERIFIED -- see phone_verified in
    db/schema.sql, added alongside this module. Sending a sign-in code to a
    number nobody confirmed hands account access to whoever typed it, which is
    a hole rather than a feature;
  * transactional SMS to Indian numbers requires DLT registration with TRAI --
    a sender id and every template registered in advance. That is a process
    measured in days, and it belongs to the operator, not to this file;
  * every provider charges per message and needs an account.

So this ships the way api/verification.py's SMTP support did: complete,
tested, and inert until credentials appear. The alternative -- waiting -- means
the day the credentials arrive is also the day the code gets written, under
time pressure, against a live account.

NO NEW DEPENDENCY
-----------------
urllib, exactly as verification.py calls Resend. Twilio and MSG91 both have
SDKs and neither is worth a dependency for one POST.

WHAT IS DELIBERATELY NOT HERE
-----------------------------
No fallback to a different channel on failure. If a text cannot be sent, the
caller says so; quietly emailing instead would mean a person who chose SMS
because their email is compromised gets the code in the compromised mailbox.
"""

import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10.0

#: Which provider to talk to. Two are supported because the choice is not
#: interchangeable here: Twilio is the global default, and MSG91 is the one
#: most Indian operators already hold a DLT-registered sender with.
PROVIDER_ENV = "AUTOTRADER_SMS_PROVIDER"

TWILIO_SID_ENV = "AUTOTRADER_TWILIO_ACCOUNT_SID"
TWILIO_TOKEN_ENV = "AUTOTRADER_TWILIO_AUTH_TOKEN"
TWILIO_FROM_ENV = "AUTOTRADER_TWILIO_FROM"

MSG91_KEY_ENV = "AUTOTRADER_MSG91_AUTH_KEY"
MSG91_SENDER_ENV = "AUTOTRADER_MSG91_SENDER_ID"
#: MSG91 sends a REGISTERED TEMPLATE by id, not free text -- that is what DLT
#: compliance means in practice. The message body below is only used by Twilio;
#: for MSG91 the wording lives in the template you registered with TRAI, and
#: this passes the code in as a variable.
MSG91_TEMPLATE_ENV = "AUTOTRADER_MSG91_TEMPLATE_ID"

_USER_AGENT = "AutoTrader/1.0 (+https://github.com/wealthwise-advisors/trading-platform)"

_last_error: str = ""


def last_error() -> str:
    return _last_error


def _remember(reason: str) -> None:
    global _last_error
    _last_error = reason


def _https_only(url: str) -> str:
    """Refuse anything that is not https. Same guard as verification.py."""
    if not url.startswith("https://"):
        raise ValueError(f"refusing a non-https endpoint: {url[:40]!r}")
    return url


def provider() -> str:
    return os.environ.get(PROVIDER_ENV, "").strip().lower()


def configured() -> bool:
    """True when a provider and its credentials are all present."""
    p = provider()
    if p == "twilio":
        return all(os.environ.get(k, "").strip() for k in
                   (TWILIO_SID_ENV, TWILIO_TOKEN_ENV, TWILIO_FROM_ENV))
    if p == "msg91":
        return all(os.environ.get(k, "").strip() for k in
                   (MSG91_KEY_ENV, MSG91_SENDER_ENV, MSG91_TEMPLATE_ENV))
    return False


def describe() -> str:
    """One line for the startup log, matching verification.describe()."""
    p = provider()
    if not p:
        return (f"SMS: dormant (set {PROVIDER_ENV} to twilio or msg91, plus that "
                f"provider's credentials, to enable)")
    if configured():
        return f"SMS: ACTIVE via {p}"
    return f"SMS: dormant ({PROVIDER_ENV}={p} but its credentials are incomplete)"


# ── phone numbers ────────────────────────────────────────────────────────────

#: E.164: a leading + and up to 15 digits. Everything is normalised to this
#: before it is stored or compared, because "+91 98765 43210", "919876543210"
#: and "09876543210" are one number and three different strings -- and a
#: uniqueness check that cannot see that is not a uniqueness check.
E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def normalise(raw: str, default_country_code: str = "") -> str:
    """Best-effort E.164, or "" if it cannot be made into one.

    Deliberately conservative. A number this cannot confidently normalise is
    rejected rather than guessed at, because the guess would be a text message
    sent to somebody else.
    """
    if not raw:
        return ""
    digits = re.sub(r"[^\d+]", "", raw.strip())
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if not digits.startswith("+"):
        # A single leading zero is a national trunk prefix; it is never part of
        # the international form.
        digits = digits.lstrip("0")
        cc = re.sub(r"[^\d]", "", default_country_code or "")
        if not cc:
            return ""
        digits = "+" + cc + digits
    return digits if E164.match(digits) else ""


def redact(number: str) -> str:
    """Last two digits only, for logs. A full number in a log is a phone book."""
    if not number:
        return "(none)"
    return f"***{number[-2:]}"


# ── sending ──────────────────────────────────────────────────────────────────

def _send_twilio(to: str, body: str) -> bool:
    sid = os.environ.get(TWILIO_SID_ENV, "").strip()
    token = os.environ.get(TWILIO_TOKEN_ENV, "").strip()
    sender = os.environ.get(TWILIO_FROM_ENV, "").strip()
    url = _https_only(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json")

    data = urllib.parse.urlencode({"To": to, "From": sender, "Body": body}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": _USER_AGENT,
    })
    # Twilio authenticates with HTTP Basic over the account sid and token.
    import base64
    creds = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req.add_header("Authorization", f"Basic {creds}")

    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # nosec B310 -- _https_only enforces the scheme
        return 200 <= resp.status < 300


def _send_msg91(to: str, code: str) -> bool:
    """MSG91 sends a REGISTERED TEMPLATE, not free text.

    That is not an API quirk -- it is what DLT compliance looks like from the
    code's side. The wording was approved by TRAI in advance and lives in the
    template; all that travels from here is the recipient and the variable.
    """
    key = os.environ.get(MSG91_KEY_ENV, "").strip()
    template = os.environ.get(MSG91_TEMPLATE_ENV, "").strip()
    sender = os.environ.get(MSG91_SENDER_ENV, "").strip()

    import json
    payload = json.dumps({
        "template_id": template,
        "sender": sender,
        # MSG91 wants the number without the leading +.
        "mobiles": to.lstrip("+"),
        "otp": code,
    }).encode()
    req = urllib.request.Request(
        _https_only("https://control.msg91.com/api/v5/flow/"),
        data=payload,
        headers={"Content-Type": "application/json", "authkey": key,
                 "User-Agent": _USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # nosec B310 -- _https_only enforces the scheme
        return 200 <= resp.status < 300


def send_code(to: str, code: str, purpose: str = "sign-in") -> bool:
    """Text one code. False when dormant, misconfigured, or the send failed.

    Never raises, for the same reason verification's senders do not: a message
    that could not be sent must not turn a request that otherwise succeeded
    into an error, and must never vary the caller's response in a way that
    reveals whether a number is on file.
    """
    number = normalise(to)
    if not number:
        log.info("refusing to text a number that is not E.164: %s", redact(to))
        return False
    if not configured():
        log.info("SMS is dormant; %s code for %s not sent", purpose, redact(number))
        return False

    body = (f"{code} is your AutoTrader {purpose} code. It expires in 10 minutes. "
            f"Do not share it with anyone, including AutoTrader support.")
    try:
        p = provider()
        ok = _send_msg91(number, code) if p == "msg91" else _send_twilio(number, body)
        if ok:
            _remember("")
            log.info("%s code texted to %s via %s", purpose, redact(number), p)
        return ok
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        reason = f"{type(exc).__name__}: {exc}"
        _remember(reason)
        log.warning("could not text %s: %s", redact(number), reason)
        return False
