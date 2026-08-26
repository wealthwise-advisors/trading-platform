"""OAuth2 sign-in with Google, LinkedIn and Twitter/X.

WHAT THIS IS FOR, AND WHAT IT IS NOT FOR
----------------------------------------
This lets somebody who ALREADY has an account enter it a second way. It is not
registration and it cannot become registration: no path through this module
creates a user. Accounts still come from scripts/manage_users.py and nowhere
else, exactly as /api/auth/register's permanent 403 says.

WHY NO ID TOKEN IS PARSED
-------------------------
The obvious way to learn who signed in is to decode the OIDC id_token. That
means fetching a provider's JWKS, picking the right key, and verifying an
ES256/RS256 signature -- and a JWT check that is subtly wrong still returns a
name, so it fails open and looks like it works. Instead the access token from
our own server-to-server code exchange is spent on the provider's userinfo
endpoint over TLS. The answer comes straight from the provider; nothing that
passed through the browser is trusted, and there is no signature to get wrong.
That is also why this file needs no JWT library.

WHY MATCHING IS ON `sub` AND NOT ON EMAIL
-----------------------------------------
Email is used exactly once -- to find the account the first time, and only when
the provider says it has verified it. After that the provider's permanent
subject id is stored and used forever. Email addresses get released, re-issued
and changed; a subject does not.

TWITTER/X IS DIFFERENT AND CANNOT DO THE ABOVE
----------------------------------------------
X does not return an email address at all, at any scope. There is therefore no
way for it to find an account on its own, and it is refused until an
administrator has linked it by hand:

    py -3.12 scripts/manage_users.py link akash --provider twitter --subject <id>

Pretending otherwise would mean either inventing an identifier or opening
registration, and neither is acceptable.

APPLE IS NOT HERE, AND ADDING IT IS A SEPARATE JOB
--------------------------------------------------
"Sign in with Apple" is deliberately absent. It needs a paid Apple Developer
Program membership, and it does not use a client secret at all: the secret is
an ES256-signed JWT that the server has to mint from a .p8 private key and
re-mint every six months, from a Service ID + Team ID + Key ID triple. It also
returns its callback as a cross-site form_post rather than a redirect, which
does not carry a SameSite=Lax cookie and would need its own handling.

To add it later: a fourth Provider entry cannot express it -- give it its own
client-secret function that signs the JWT, and a POST callback route. Until
then the Apple button on the sign-in page shows the same honest "not connected
yet" notice it shows for any unconfigured provider, because this module never
reports it as available.

CONFIGURATION
-------------
Every credential is read from the environment and defaults to empty. A provider
with no credentials is reported as unconfigured and refuses cleanly; it never
half-works and never guesses a value.

    AUTOTRADER_PUBLIC_BASE_URL        https://your-host  (no trailing slash)
    AUTOTRADER_GOOGLE_CLIENT_ID       AUTOTRADER_GOOGLE_CLIENT_SECRET
    AUTOTRADER_LINKEDIN_CLIENT_ID     AUTOTRADER_LINKEDIN_CLIENT_SECRET
    AUTOTRADER_TWITTER_CLIENT_ID      AUTOTRADER_TWITTER_CLIENT_SECRET

`py -3.12 scripts/manage_users.py oauth-status` prints which of these are set
and the exact redirect URI to register for each provider.
"""

import base64
import hashlib
import logging
import os
import secrets
from dataclasses import dataclass, field
from urllib.parse import urlencode

import requests

log = logging.getLogger(__name__)

#: Absolute, public base URL of this deployment, e.g. https://trade.example.com
#: -- the origin a browser reaches us on. It cannot be derived from the request
#: (Host is client-supplied) and it must match what is registered at each
#: provider byte for byte, so it is stated explicitly.
PUBLIC_BASE_URL = os.environ.get("AUTOTRADER_PUBLIC_BASE_URL", "").rstrip("/")

#: How long we will wait on a provider. Short: this runs inside a request a
#: person is watching, and a hung provider must not hold the worker open.
HTTP_TIMEOUT = 10


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str
    #: PKCE. Required by X; supported by Google. LinkedIn's OIDC
    #: implementation rejects the parameters, so it is off there.
    use_pkce: bool = True
    #: X authenticates the client with HTTP Basic on the token endpoint;
    #: Google and LinkedIn take the credentials in the form body.
    basic_auth: bool = False
    #: X cannot report an email, so it can never find an account by itself.
    provides_email: bool = True
    extra_authorize: dict = field(default_factory=dict)


PROVIDERS: dict[str, Provider] = {
    "google": Provider(
        key="google",
        label="Google",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        scope="openid email profile",
        # Without these Google returns no refresh token and silently reuses a
        # previous consent, which makes a failed link impossible to retry.
        extra_authorize={"access_type": "online", "prompt": "select_account"},
    ),
    "linkedin": Provider(
        key="linkedin",
        label="LinkedIn",
        authorize_url="https://www.linkedin.com/oauth/v2/authorization",
        token_url="https://www.linkedin.com/oauth/v2/accessToken",
        userinfo_url="https://api.linkedin.com/v2/userinfo",
        scope="openid email profile",
        use_pkce=False,
    ),
    "twitter": Provider(
        key="twitter",
        label="Twitter",
        authorize_url="https://twitter.com/i/oauth2/authorize",
        token_url="https://api.twitter.com/2/oauth2/token",
        userinfo_url="https://api.twitter.com/2/users/me",
        scope="users.read tweet.read",
        use_pkce=True,          # X requires it
        basic_auth=True,
        provides_email=False,   # hence: admin pre-linking only
    ),
}


# ── configuration ────────────────────────────────────────────────────────────
def credentials(provider_key: str) -> tuple[str, str]:
    """(client_id, client_secret) from the environment. Empty when unset.

    Read at call time rather than import time so a test -- or a restart with
    new values -- takes effect without reimporting the module.
    """
    prefix = f"AUTOTRADER_{provider_key.upper()}_"
    return (os.environ.get(prefix + "CLIENT_ID", "").strip(),
            os.environ.get(prefix + "CLIENT_SECRET", "").strip())


def base_url() -> str:
    """The public origin, read at call time for the same reason."""
    return os.environ.get("AUTOTRADER_PUBLIC_BASE_URL", PUBLIC_BASE_URL).rstrip("/")


def redirect_uri(provider_key: str) -> str:
    return f"{base_url()}/api/auth/oauth/{provider_key}/callback"


def is_configured(provider_key: str) -> bool:
    """Both halves of the credential AND somewhere to send the person back to.

    The base URL counts: without it the redirect_uri would be a bare path, the
    provider would reject the request, and the failure would surface as an
    opaque error on the provider's own site rather than here.
    """
    cid, secret = credentials(provider_key)
    return bool(cid and secret and base_url())


def configured_providers() -> dict[str, bool]:
    return {k: is_configured(k) for k in PROVIDERS}


# ── PKCE ─────────────────────────────────────────────────────────────────────
def new_verifier() -> str:
    """A PKCE code_verifier: 43-128 chars of unreserved alphabet (RFC 7636)."""
    return secrets.token_urlsafe(64)[:96]


def challenge_for(verifier: str) -> str:
    """S256 challenge. Never `plain` -- plain offers no protection at all."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


# ── building the redirect ────────────────────────────────────────────────────
def authorization_url(provider: Provider, state: str, verifier: str) -> str:
    client_id, _ = credentials(provider.key)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri(provider.key),
        "scope": provider.scope,
        "state": state,
        **provider.extra_authorize,
    }
    if provider.use_pkce:
        params["code_challenge"] = challenge_for(verifier)
        params["code_challenge_method"] = "S256"
    return f"{provider.authorize_url}?{urlencode(params)}"


# ── the two network seams ────────────────────────────────────────────────────
# Named, module-level, and called through the module so tests can replace them
# -- the same shape as the Schwab token exchange in
# tests/test_schwab_redirect_parsing.py. Nothing else here touches the network.

class OAuthError(RuntimeError):
    """A provider refused, or answered with something unusable."""


def _post_token(provider: Provider, code: str, verifier: str) -> dict:
    """Exchange an authorization code for an access token, server to server."""
    client_id, client_secret = credentials(provider.key)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(provider.key),
        "client_id": client_id,
    }
    if provider.use_pkce:
        data["code_verifier"] = verifier

    headers = {"Content-Type": "application/x-www-form-urlencoded",
               "Accept": "application/json"}
    if provider.basic_auth:
        pair = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        headers["Authorization"] = f"Basic {pair}"
    else:
        data["client_secret"] = client_secret

    resp = requests.post(provider.token_url, data=data, headers=headers,
                         timeout=HTTP_TIMEOUT)
    if not resp.ok:
        # The body can echo the client_secret back on some errors, so it is
        # logged at neither level and never returned to the browser.
        log.warning("%s token exchange failed: HTTP %s", provider.key, resp.status_code)
        raise OAuthError(f"{provider.label} rejected the sign-in.")
    try:
        return resp.json()
    except ValueError as exc:
        raise OAuthError(f"{provider.label} returned an unreadable response.") from exc


def _fetch_userinfo(provider: Provider, access_token: str) -> dict:
    """Ask the provider who just signed in."""
    params = {"user.fields": "id,name,username"} if provider.key == "twitter" else None
    resp = requests.get(provider.userinfo_url,
                        headers={"Authorization": f"Bearer {access_token}",
                                 "Accept": "application/json"},
                        params=params, timeout=HTTP_TIMEOUT)
    if not resp.ok:
        log.warning("%s userinfo failed: HTTP %s", provider.key, resp.status_code)
        raise OAuthError(f"Could not read your {provider.label} profile.")
    try:
        return resp.json()
    except ValueError as exc:
        raise OAuthError(f"{provider.label} returned an unreadable profile.") from exc


# ── normalising what came back ───────────────────────────────────────────────
@dataclass(frozen=True)
class ProviderUser:
    subject: str
    email: str
    email_verified: bool
    full_name: str


def normalise(provider: Provider, info: dict) -> ProviderUser:
    """Flatten a provider's own profile shape into one we can act on.

    `email_verified` is treated as false unless the provider positively says
    otherwise. An unverified address proves nothing -- anyone can put another
    person's email on an account at a provider that does not check it, and
    trusting it here would hand them that person's login.
    """
    if provider.key == "twitter":
        # {"data": {"id": ..., "name": ..., "username": ...}} -- no email field
        data = info.get("data") or {}
        return ProviderUser(subject=str(data.get("id") or ""), email="",
                            email_verified=False,
                            full_name=str(data.get("name") or ""))

    raw_verified = info.get("email_verified")
    verified = raw_verified is True or str(raw_verified).lower() == "true"
    return ProviderUser(
        subject=str(info.get("sub") or ""),
        email=str(info.get("email") or "").strip(),
        email_verified=verified,
        full_name=str(info.get("name") or "").strip(),
    )


# ── where to send the person afterwards ──────────────────────────────────────
SIGN_IN_PAGE = "/autotrader_signin.html"


def safe_next(raw: str | None) -> str:
    """Constrain the post-sign-in destination to a same-site path.

    Same rule the sign-in page applies to its own `next`: taking the value as
    given would let a crafted link land somebody on another host at the exact
    moment they have just authenticated, which is the moment they are most
    likely to trust what they see. A protocol-relative "//evil.example" is a
    URL, not a path, so a leading double slash is rejected too.
    """
    if not raw or not raw.startswith("/") or raw.startswith("//"):
        return "/"
    if "autotrader_signin" in raw or "autotrader_signup" in raw:
        return "/"
    return raw[:512]


def sign_in_redirect(reason: str, *, provider: str = "", next_path: str = "") -> str:
    """Back to the sign-in page carrying a reason it can explain."""
    params = {"reason": reason}
    if provider:
        params["provider"] = provider
    if next_path and next_path != "/":
        params["next"] = next_path
    return f"{SIGN_IN_PAGE}?{urlencode(params)}"
