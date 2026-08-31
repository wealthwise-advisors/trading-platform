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
from pathlib import Path

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


#: Sent on every call to Resend.
#:
#: The User-Agent is not decoration. urllib introduces itself as
#: "Python-urllib/3.12", which is a textbook automation signature, and
#: api.resend.com sits behind Cloudflare -- which refused every request with
#: "403: error code: 1010", meaning blocked on client signature. The request
#: never reached Resend at all, so their Logs page stayed empty and there was
#: nothing anywhere to say why. Naming the application honestly is enough.
_USER_AGENT = "AutoTrader/1.0 (+https://github.com/wealthwise-advisors/trading-platform)"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": _USER_AGENT,
    }


def _api_key() -> str:
    return os.environ.get(API_KEY_ENV, "").strip()


def _sender() -> str:
    return os.environ.get(FROM_ENV, "").strip()


def _base_url() -> str:
    return os.environ.get(BASE_URL_ENV, "").strip().rstrip("/")


#: SMTP, the alternative to Resend's HTTP API.
#:
#: WHY THIS EXISTS
#: Resend will not deliver to a stranger until you have VERIFIED A DOMAIN, and
#: verifying a domain needs DNS access to a domain you own. That is a blocker
#: no amount of code can clear, and it is not always the developer's to clear:
#: on this project the deployment answers to 3-218-23-37.sslip.io, a free
#: IP-to-hostname service whose DNS nobody here controls.
#:
#: SMTP has no such requirement. Any ordinary mailbox -- a Gmail account with an
#: App Password, an Outlook account, a work mailserver -- will relay to any
#: recipient, today, with no domain and no DNS records. Gmail allows roughly 500
#: messages a day, which is far beyond what confirmation and reset mail needs at
#: this scale.
#:
#: When SMTP is configured it WINS over Resend, because someone who went to the
#: trouble of setting it did so to get out of the sandbox.
SMTP_HOST_ENV = "AUTOTRADER_SMTP_HOST"
SMTP_PORT_ENV = "AUTOTRADER_SMTP_PORT"
SMTP_USER_ENV = "AUTOTRADER_SMTP_USER"
SMTP_PASSWORD_ENV = "AUTOTRADER_SMTP_PASSWORD"


def _smtp_host() -> str:
    return os.environ.get(SMTP_HOST_ENV, "").strip()


def _smtp_configured() -> bool:
    return bool(_smtp_host()
                and os.environ.get(SMTP_USER_ENV, "").strip()
                and os.environ.get(SMTP_PASSWORD_ENV, ""))


def _deliver_smtp(to: str, subject: str, body: str) -> bool:
    """Hand one message to an SMTP relay. Raises; the caller reports."""
    import smtplib
    import ssl
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = _sender()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    host = _smtp_host()
    port = int(os.environ.get(SMTP_PORT_ENV, "587") or 587)
    user = os.environ.get(SMTP_USER_ENV, "").strip()
    password = os.environ.get(SMTP_PASSWORD_ENV, "")

    # 465 is implicit TLS; 587 is plain then STARTTLS. Getting these the wrong
    # way round is the usual reason an SMTP send hangs until it times out.
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=TIMEOUT_SECONDS,
                              context=context) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=TIMEOUT_SECONDS) as smtp:
            smtp.starttls(context=context)
            smtp.login(user, password)
            smtp.send_message(msg)
    return True


def _deliver_resend(to: str, subject: str, body: str) -> bool:
    payload = {"from": _sender(), "to": [to], "subject": subject, "text": body}
    req = urllib.request.Request(
        _https_only(API_URL), data=json.dumps(payload).encode(),
        headers=_headers(),
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # nosec B310 -- _https_only enforces the scheme
        return 200 <= resp.status < 300


#: A local development sink: write the message to a FILE instead of sending it.
#:
#: WHY THIS EXISTS
#: Running the app on a laptop meant confirmation links and sign-in codes went
#: nowhere -- correctly, because no transport was configured -- which made every
#: email-dependent flow untestable locally without putting a real mailbox
#: credential on the machine. That is a poor trade for looking at a screen.
#:
#: WHY IT CANNOT LEAK INTO PRODUCTION
#: Two locks, and both must be open:
#:
#:   1. It is OPT-IN by an explicit path. Nothing defaults it on, the deploy
#:      never sets it, and there is no value of any other variable that turns
#:      it on by accident.
#:   2. It REFUSES to run when a real transport exists. The deployed stack has
#:      SMTP configured, so even if this variable were somehow set there, the
#:      check below hands the message to SMTP and never to the file.
#:
#: The file is a full copy of the message, tokens included, so it must be
#: treated as a mailbox: the launcher puts it outside the git repository.
DEV_SINK_ENV = "AUTOTRADER_DEV_MAIL_SINK"


def _dev_sink_path() -> str:
    """The sink path, or "" when it must not be used.

    Empty whenever a real transport is available, so this can never take
    precedence over actually sending.
    """
    if _smtp_configured() or _api_key():
        return ""
    return os.environ.get(DEV_SINK_ENV, "").strip()


def dev_sink_active() -> bool:
    return bool(_dev_sink_path())


def _deliver_dev_sink(to: str, subject: str, body: str) -> bool:
    """Append the whole message to a local file, and log where to look.

    The PATH is logged, never the contents -- a token in a log line is a
    working link in a file that gets shipped and read by more people than a
    mailbox is.
    """
    path = _dev_sink_path()
    stamp = datetime.now().isoformat(timespec="seconds")
    entry = (f"{'=' * 72}\n"
             f"{stamp}   to: {to}\n"
             f"Subject: {subject}\n"
             f"{'-' * 72}\n{body}\n")
    try:
        p = Path(path)
        if p.parent and not p.parent.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(entry)
    except OSError as exc:
        log.warning("could not write the dev mail sink at %s: %s", path, exc)
        return False
    log.info("DEV MAIL SINK: message written to %s -- open that file to read it", path)
    return True


def _deliver(to: str, subject: str, body: str, what: str) -> bool:
    """Send one message by whichever transport is configured.

    One place, so the three callers below cannot drift apart -- and so adding a
    transport does not mean editing three near-identical blocks and missing one.
    """
    try:
        if _smtp_configured():
            ok, via = _deliver_smtp(to, subject, body), "SMTP"
        elif _api_key():
            ok, via = _deliver_resend(to, subject, body), "Resend"
        else:
            # Only reachable when neither real transport exists -- see
            # _dev_sink_path, which returns "" the moment one does.
            ok, via = _deliver_dev_sink(to, subject, body), "the dev sink"
        if ok:
            _remember("")
            log.info("%s sent to %s via %s", what, _redact(to), via)
        return ok
    except Exception as exc:            # noqa: BLE001 -- see below
        # Deliberately broad. smtplib raises a family of its own exceptions
        # (SMTPAuthenticationError, SMTPRecipientsRefused, SMTPServerDisconnected
        # and more), ssl raises another, and this function's whole contract is
        # that a mail failure never becomes a user-visible error on a
        # registration or a reset that otherwise succeeded.
        reason = _explain(exc)
        _remember(reason)
        log.warning("could not send %s to %s: %s", what, _redact(to), reason)
        return False


def configured() -> bool:
    """True when a transport, a sender and a base URL are all present.

    A transport is EITHER SMTP or a Resend key. Requiring the Resend key
    outright would have made SMTP unreachable: every send path checks this
    first and returns early, so a fully configured mailserver would have been
    treated as dormant.

    All three, because a verification email without an absolute link is
    useless, and a sender the domain does not authorise is silently dropped by
    the recipient's provider rather than bounced.
    """
    if dev_sink_active():
        # The sink can always "deliver", so the flows behave locally exactly as
        # they do in production instead of stopping at "mail is dormant" -- the
        # whole point of having it.
        return bool(_sender() and _base_url())
    return bool((_smtp_configured() or _api_key()) and _sender() and _base_url())


#: Resend's shared sandbox sender. Mail from it is accepted by the API and then
#: delivered ONLY to the address that owns the Resend account -- every other
#: recipient is dropped silently, with a 200 on the way in and nothing in the
#: inbox. Nothing in the response distinguishes that from a successful send.
SANDBOX_SENDER = "resend.dev"


def sandboxed() -> bool:
    """True when the sender is Resend's shared domain rather than a verified one.

    Worth a name of its own because the failure it describes is invisible:
    every send "succeeds", the log agrees, and only the recipients notice. It
    is the difference between password reset working for the operator and
    working for users.
    """
    # SMTP relays to whoever is addressed -- there is no sandbox to be in. This
    # matters beyond the label: api/auth.py's verification gate stays OFF while
    # this is True, so without this line an SMTP deployment that CAN reach
    # everyone would still refuse to enforce the confirmation it can now send.
    if dev_sink_active():
        # Reaches nobody at all, so it must read as sandboxed -- otherwise the
        # confirmation gate would switch on locally and lock out an account
        # whose "email" only ever lands in a text file.
        return True
    if _smtp_configured():
        return False
    sender = _sender()
    return bool(sender) and sender.rsplit("@", 1)[-1].lower().endswith(SANDBOX_SENDER)


def transport_name() -> str:
    if _smtp_configured():
        return f"SMTP ({_smtp_host()})"
    return "Resend"


def describe() -> str:
    """One line for the startup log."""
    if configured():
        if dev_sink_active():
            return (f"Email: DEV SINK -- nothing is actually sent. Messages are "
                    f"written to {_dev_sink_path()}; open that file to read the "
                    f"code or link.")
        if _smtp_configured():
            return (f"Email: ACTIVE via {transport_name()} (from {_sender()}) "
                    f"-- delivers to any recipient.")
        if sandboxed():
            return (f"Email verification: ACTIVE but SANDBOXED (from {_sender()}) "
                    f"-- Resend delivers this sender only to the account owner, "
                    f"so nobody else receives confirmation or reset mail. "
                    f"Verify a domain and set {FROM_ENV} to an address on it.")
        return f"Email verification: ACTIVE (from {_sender()})"
    missing = [n for n, v in ((f"{API_KEY_ENV} (or {SMTP_HOST_ENV}"
                               f"/{SMTP_USER_ENV}/{SMTP_PASSWORD_ENV})",
                               _api_key() or ("x" if _smtp_configured() else "")),
                              (FROM_ENV, _sender()),
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
        return _deliver(email, payload["subject"], payload["text"], "verification email")
    except (TimeoutError, OSError, ValueError) as exc:
        # Only token minting and link building can still raise here; delivery
        # reports for itself.
        reason = _explain(exc)
        _remember(reason)
        log.warning("could not prepare the verification email for %s: %s",
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
        return _deliver(email, payload["subject"], payload["text"], "password reset email")
    except (TimeoutError, OSError, ValueError) as exc:
        # Only token minting and link building can still raise here; delivery
        # reports for itself.
        reason = _explain(exc)
        _remember(reason)
        log.warning("could not prepare the password reset email for %s: %s",
                    _redact(email), reason)
        return False


#: A sign-in code lives minutes, not hours. It is six digits -- a million
#: combinations -- so unlike the 32-byte links above, its strength does not
#: come from length. It comes from a short window and a hard attempt cap, and
#: both have to hold or the code is guessable.
#:
#: Four digits was asked for and is not enough: ten thousand combinations is
#: within reach of a patient attacker even through a throttle.
LOGIN_CODE_TTL = timedelta(minutes=10)
LOGIN_CODE_DIGITS = 6

#: Wrong guesses before the code is destroyed outright. The cap is the real
#: control, not the hashing: an attacker who reaches the database can reverse
#: a six-digit SHA-256 in about a second, so nothing about this code is safe
#: once it is stored -- which is exactly why it expires in minutes and dies on
#: the sixth wrong answer.
LOGIN_CODE_MAX_ATTEMPTS = 5


def new_login_code(user_id: int) -> str:
    """Mint a single-use six-digit sign-in code and record its hash."""
    # secrets.randbelow, not random: this is a credential.
    code = f"{secrets.randbelow(10 ** LOGIN_CODE_DIGITS):0{LOGIN_CODE_DIGITS}d}"
    expires = (datetime.now() + LOGIN_CODE_TTL).isoformat(timespec="seconds")
    # Bound to the user id before hashing, so one stolen digest cannot be
    # matched against every account at once.
    repo.new_email_token(user_id, repo.hash_token(f"{user_id}:{code}"),
                         expires, purpose="login")
    return code


def new_phone_code(user_id: int) -> str:
    """A six-digit code for proving a phone number.

    The same shape and the same defences as a sign-in code -- ten minutes, five
    attempts, hashed against the owner -- under its own purpose so requesting
    one does not destroy a sign-in code the same person is mid-way through.
    """
    code = f"{secrets.randbelow(10 ** LOGIN_CODE_DIGITS):0{LOGIN_CODE_DIGITS}d}"
    expires = (datetime.now() + LOGIN_CODE_TTL).isoformat(timespec="seconds")
    repo.new_email_token(user_id, repo.hash_token(f"{user_id}:{code}"),
                         expires, purpose="phone")
    return code


def send_login_code(email: str, username: str, code: str) -> bool:
    """Email a sign-in code. False when unconfigured or the send failed."""
    if not email or not configured():
        return False
    minutes = int(LOGIN_CODE_TTL.total_seconds() // 60)
    return _deliver(
        email,
        f"{code} is your AutoTrader sign-in code",
        (f"Hello {username},\n\n"
         f"Your sign-in code is:\n\n"
         f"    {code}\n\n"
         f"It expires in {minutes} minutes and works once.\n\n"
         f"If you did not ask to sign in, ignore this message. Nobody can use "
         f"this code without it, and your password has not changed.\n\n"
         f"We will never ask you to read this code to anyone, including "
         f"someone claiming to be AutoTrader support.\n"),
        "sign-in code")


def send_registration_collision(email: str, username: str) -> bool:
    """Tell an address that somebody tried to register with it.

    The counterpart to registration answering identically whether or not an
    address is taken. The caller learns nothing; the person who actually owns
    the address learns everything -- that someone tried, that no second account
    was made, and what to do if it was not them.

    Carries no token and no link to spend, so it is safe to send unprompted to
    an address that did not ask for it. It names the existing username because
    the message goes only to the mailbox that already holds that account --
    the same reasoning that lets /forgot-username send a username at all.
    """
    if not email or not configured():
        return False
    return _deliver(
        email,
        "Someone tried to register with your AutoTrader address",
        (f"Hello,\n\n"
         f"Someone just tried to create an AutoTrader account using this email "
         f"address. We did not create one -- an account already exists here, "
         f"with the username:\n\n"
         f"    {username}\n\n"
         f"If that was you, sign in with the account you already have, or use "
         f"'Forgot password' if you cannot get in.\n\n"
         f"If it was not you, no action is needed. Nothing was created, nothing "
         f"about your account changed, and this message contains no links to "
         f"click. Your password still works and nobody has gained access.\n\n"
         f"Sign in at {_base_url()}/autotrader_signin.html\n"),
        "registration collision notice")


def send_username(email: str, username: str) -> bool:
    """Remind someone of their own username. False when unconfigured or failed.

    No token and no link. A username is not a credential -- it is half of a
    public pair, and knowing it grants nothing without the password. So this
    carries nothing that could be spent, which is why it can be sent on a bare
    request where a reset link could not.
    """
    if not email or not configured():
        log.info("username reminder requested but mail is dormant")
        return False
    try:
        payload = {
            "from": _sender(),
            "to": [email],
            "subject": "Your AutoTrader username",
            "text": (
                f"Hello,\n\n"
                f"Someone asked for the username on the AutoTrader account "
                f"registered to this address. It is:\n\n"
                f"    {username}\n\n"
                f"Sign in at {_base_url()}/autotrader_signin.html\n\n"
                f"If this was not you, no action is needed -- a username on "
                f"its own cannot be used to sign in.\n"
            ),
        }
        return _deliver(email, payload["subject"], payload["text"], "username reminder")
    except (TimeoutError, OSError, ValueError) as exc:
        # Only token minting and link building can still raise here; delivery
        # reports for itself.
        reason = _explain(exc)
        _remember(reason)
        log.warning("could not prepare the username reminder for %s: %s",
                    _redact(email), reason)
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
