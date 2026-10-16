"""Who a request runs as, now that there is no sign-in.

SIGN-IN WAS REMOVED on 2026-10-16, on request: the app opens straight from its
link, with no login page, registration, password, session or OAuth. This
module used to hold password hashing, session cookies, throttles and an
email-verification gate; all of that is gone.

WHAT REMAINS
------------
The data model is still per-account -- saved configurations, the paper-trading
session and the journal key on a user id -- so every request is attributed to
ONE account, `db.users.workspace_user()`: the owner account when there is one
(it holds the Schwab entitlement, so live data keeps working), otherwise the
oldest active account, otherwise a fresh "workspace" account.

WHAT IS DELIBERATELY KEPT: the cross-origin check
-------------------------------------------------
A state-changing request (POST/PUT/DELETE) that arrives with an Origin header
naming another site is still refused. That was defence in depth beside the
session cookie, and it matters MORE without sign-in, not less: with no
session to forge, the only thing stopping another website from driving this
API through a visitor's browser is that the request does not come from here.

ACCESS NOTE
-----------
With sign-in gone, anyone who can reach the URL can use every route. The
remaining restrictions are the cross-origin check above and the per-account
Schwab entitlement (`is_owner`), which this instance satisfies because the
workspace IS the owner account. Restricting who can reach the URL at all is
now a network-level decision.
"""

import logging

from fastapi import Depends, HTTPException, Request, status

from db import users as repo

log = logging.getLogger(__name__)

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


async def require_user(request: Request):
    """Every protected route depends on this. Returns the workspace account.

    The name stays: it is what every router already depends on, and renaming
    it would touch every route for no change in behaviour. There is nothing to
    require any more except that a state-changing request come from this site.
    """
    if request.method not in _SAFE_METHODS:
        origin = request.headers.get("origin")
        if origin:
            host = request.headers.get("host", "")
            if host and not origin.endswith("//" + host):
                log.warning("cross-origin %s to %s from %s",
                            request.method, request.url.path, origin)
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail="Cross-origin request refused.")

    user = repo.workspace_user()
    request.state.user = user
    return user


#: Convenience for router-level protection: `dependencies=[PROTECTED]`.
PROTECTED = Depends(require_user)


async def user_for_websocket(websocket) -> object | None:
    """The account a WebSocket handshake runs as.

    The same cross-site rule as the HTTP routes. A browser always sends Origin
    on a WebSocket upgrade, and a socket opened from another site is refused
    here, because the replay socket streams the same data the HTTP routes
    serve. Returning None is the existing "refuse the handshake" signal.
    """
    origin = websocket.headers.get("origin")
    host = websocket.headers.get("host", "")
    if origin and host and not origin.endswith("//" + host):
        log.warning("cross-origin websocket from %s", origin)
        return None
    return repo.workspace_user()
