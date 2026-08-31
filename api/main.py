"""
FastAPI backend for the AutoTrader dashboard.

Run from the trading-platform/ repo root (relative paths like config/ and
data/ assume that CWD):

    uvicorn api.main:app --reload --port 8000

The React dev server (web/) proxies /api/* to this process — see
web/vite.config.ts. Nothing under src/ is modified to support this; the API
is a thin consumer of the same backtesting/strategy/data-provider code.
"""

import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from importlib.metadata import version as _pkg_version, PackageNotFoundError as _PkgNotFound

from api import auth as auth_mod
from api import captcha, verification
from api.auth import PROTECTED
from api.routers import (auth as auth_router, meta, backtests, replay,
                         schwab, optimize, data_export, account,
                         oauth as oauth_router)

try:
    _version = _pkg_version("autotrader")
except _PkgNotFound:
    _version = "unknown"

# ── make the application's own logs visible ──────────────────────────────────
#
# There was no logging configuration anywhere in this app. api/auth.py,
# api/routers/oauth.py and api/verification.py all use the STANDARD library's
# logging; main.py uses loguru, which does not adopt stdlib records unless it
# is told to. So no handler was ever attached to them: every log.info was
# dropped outright, and log.warning survived only via Python's "handler of last
# resort", which prints a bare message with no logger name, level or time.
#
# That was not a cosmetic gap. Those modules log the reason behind every OAuth
# refusal, every throttle, and every rejected recovery attempt -- deliberately,
# because none of it can be told apart from the outside: a failed token
# exchange and a failed profile fetch produce the identical redirect. Debugging
# a live sign-in problem meant guessing between branches that had each already
# written down exactly which one they took.
#
# force=True because uvicorn installs its own handlers first; without it this
# call is a silent no-op under the server we actually deploy on -- which is the
# only place it matters.
logging.basicConfig(
    level=os.environ.get("AUTOTRADER_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Say what mail and CAPTCHA are actually doing, once, at startup.

    Both modules have had a describe() for a while and NOTHING CALLED EITHER --
    the one line that says whether confirmation mail can leave the building was
    computed by a function no code path reached. That matters more than it
    sounds: `verification.describe()` is what reports the sandbox sender, the
    state in which every send succeeds and only the recipients notice it did
    not arrive. Silence there is indistinguishable from working.

    It also reports whether the address gate is live, because the gate switches
    itself on from mail's own configuration and an operator should not have to
    infer that from two other lines.

    A lifespan handler rather than @app.on_event("startup"): on_event is
    deprecated and warns, and adding a warning to a clean build to carry a log
    line is a poor trade.
    """
    logger.info(verification.describe())
    logger.info(captcha.describe())
    # An f-string, not %s with an argument: this is loguru's logger, which
    # formats with str.format and would silently drop a %-style argument,
    # printing the placeholder itself.
    gate = ("ENFORCED -- unconfirmed addresses cannot use the app"
            if auth_mod.verification_enforced()
            else "off -- unconfirmed addresses are allowed through")
    logger.info(f"Email gate: {gate}")
    yield


app = FastAPI(title="AutoTrader API", version=_version, lifespan=_lifespan)

# Task 10 API audit: no CORS policy existed at all. In dev this is masked
# by Vite's proxy (browser sees same-origin), but a production deployment
# that serves the built frontend from a different origin/port than the API
# (e.g. Docker's default compose layout in this release) needs one, or the
# browser blocks every request. Origins come from an env var so this stays
# a deployment-time config choice, not a hardcoded guess; defaults to the
# two local dev ports so `docker compose up` and `npm run dev` both work
# out of the box without extra setup.
_cors_origins = [o.strip() for o in os.environ.get(
    "AUTOTRADER_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def _unhandled_exception(request: Request, exc: Exception):
    """
    Never let an unhandled exception reach the user as a bare
    "Internal Server Error".

    That default told them nothing: a missing CSV for the symbol they had just
    picked and a genuine server defect looked identical, so the only actionable
    part of the failure -- which input to change -- was the part thrown away.
    The full traceback still goes to the server log; the response carries the
    exception type and message so the UI, which already renders `detail`, can
    show something a person can act on.
    """
    # An error id ties what the caller sees to what the log holds, so a report
    # of "it broke" can be found without the response carrying the details.
    error_id = uuid.uuid4().hex[:12]
    logger.exception(
        f"[{error_id}] Unhandled error on {request.method} {request.url.path}")

    # The reasoning above still stands for someone signed in: they own this
    # system and the message is the actionable part. It must not go to a
    # stranger, though -- an exception message can carry a filesystem path, a
    # query, or a driver's own text. require_user sets request.state.user, so
    # its absence means the caller never authenticated.
    signed_in = getattr(request.state, "user", None) is not None
    detail = (f"{type(exc).__name__}: {exc}" if signed_in
              else "Internal server error.")
    return JSONResponse(
        status_code=500,
        content={"detail": detail, "path": request.url.path, "error_id": error_id},
    )


# Public: sign in/out, and the two liveness endpoints inside meta.
app.include_router(auth_router.router, prefix="/api")
app.include_router(meta.router, prefix="/api")

# Also public, and necessarily so: someone signing in with Google has no
# session yet, and the provider redirects the browser back to the callback
# carrying none of our cookies. These routes defend themselves with a
# single-use server-side state plus PKCE -- see api/routers/oauth.py.
#
# They CAN create an account, and only on an address the provider positively
# states it has verified. (This comment used to say the opposite; that stopped
# being true when signup was opened.) What they still cannot do is grant the
# broker: is_owner is not a parameter of create_user, so no path through here
# reaches it.
app.include_router(oauth_router.router, prefix="/api")

# Everything below requires a session. The dependency is declared on the
# ROUTER, not on each function, so an endpoint added to any of these files
# later is protected by default rather than by remembering to protect it.
app.include_router(backtests.router, prefix="/api", dependencies=[PROTECTED])
app.include_router(replay.router, prefix="/api", dependencies=[PROTECTED])
# Not PROTECTED: a websocket handshake cannot resolve an HTTP dependency.
# replay_ws authenticates the cookie itself, before accept().
app.include_router(replay.ws_router, prefix="/api")
app.include_router(schwab.router, prefix="/api", dependencies=[PROTECTED])
app.include_router(optimize.router, prefix="/api", dependencies=[PROTECTED])
app.include_router(data_export.router, prefix="/api", dependencies=[PROTECTED])
# The account's own saved configurations. Under PROTECTED like the rest, and
# every handler additionally scopes its query by the resolved user's id.
app.include_router(account.router, prefix="/api", dependencies=[PROTECTED])
