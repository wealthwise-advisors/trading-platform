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

from api.auth import PROTECTED
from api.routers import (auth as auth_router, meta, backtests, replay,
                         schwab, optimize, data_export, account, quotes, live)

try:
    _version = _pkg_version("autotrader")
except _PkgNotFound:
    _version = "unknown"

# ── make the application's own logs visible ──────────────────────────────────
#
# Parts of this app log through the STANDARD library's logging (api/auth.py's
# cross-origin refusals among them); main.py uses loguru, which does not adopt
# stdlib records unless it is told to. Without this, every log.info from those
# modules was dropped outright, and log.warning survived only via Python's
# "handler of last resort", with no logger name, level or time.
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
    """Startup notice.

    This used to report what mail and CAPTCHA were doing and whether the email
    gate was live. All three belonged to sign-in, which was removed on
    2026-10-16; what is worth saying at startup now is that the app is open.
    """
    logger.info("Sign-in is disabled: every request runs as the workspace account.")
    yield


#: Swagger UI and the raw schema. ON by default -- they are a documented
#: feature (docs/API_GUIDE.md) and the way anyone works on this locally.
#:
#: The DEPLOY turns them off. Every route behind them is guarded, so this is
#: not access control; it is surface reduction. A public /docs hands an
#: attacker the complete route list, every parameter name and every response
#: shape, on a site that anyone can reach and register on. That is a map worth
#: not drawing for them.
_DOCS = os.environ.get("AUTOTRADER_ENABLE_DOCS", "1").strip().lower() not in {
    "0", "false", "no", "off"}

app = FastAPI(
    title="AutoTrader API", version=_version, lifespan=_lifespan,
    docs_url="/docs" if _DOCS else None,
    redoc_url="/redoc" if _DOCS else None,
    # The schema itself, which is what /docs reads. Leaving it reachable while
    # hiding the UI would publish exactly the same information one fetch away.
    openapi_url="/openapi.json" if _DOCS else None,
)

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


# /auth/me and /auth/onboarded, and the two liveness endpoints inside meta.
app.include_router(auth_router.router, prefix="/api")
app.include_router(meta.router, prefix="/api")


# Everything below runs through require_user: no sign-in any more, but it
# attributes the request to the workspace account and refuses cross-origin
# state changes. Declared on the ROUTER, not on each function, so an endpoint
# added to any of these files later gets the same treatment by default.
app.include_router(backtests.router, prefix="/api", dependencies=[PROTECTED])
app.include_router(replay.router, prefix="/api", dependencies=[PROTECTED])
# Not PROTECTED: a websocket handshake cannot resolve an HTTP dependency.
# replay_ws resolves the workspace account and checks Origin itself.
app.include_router(replay.ws_router, prefix="/api")
app.include_router(schwab.router, prefix="/api", dependencies=[PROTECTED])
app.include_router(optimize.router, prefix="/api", dependencies=[PROTECTED])
app.include_router(data_export.router, prefix="/api", dependencies=[PROTECTED])
# The account's own saved configurations. Under PROTECTED like the rest, and
# every handler additionally scopes its query by the resolved user's id.
app.include_router(account.router, prefix="/api", dependencies=[PROTECTED])
# Protected like every other data route: a quote is market data the account
# is entitled to through ITS Schwab link, not a public feed.
app.include_router(quotes.router, prefix="/api", dependencies=[PROTECTED])
# Paper trading sessions. Guarded like every other trading route; the broker
# it uses is chosen in api/routers/live.py and is a PaperBroker.
app.include_router(live.router, prefix="/api", dependencies=[PROTECTED])
