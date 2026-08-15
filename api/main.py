"""
FastAPI backend for the AutoTrader dashboard.

Run from the trading-platform/ repo root (relative paths like config/ and
data/ assume that CWD):

    uvicorn api.main:app --reload --port 8000

The React dev server (web/) proxies /api/* to this process — see
web/vite.config.ts. Nothing under src/ is modified to support this; the API
is a thin consumer of the same backtesting/strategy/data-provider code.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from importlib.metadata import version as _pkg_version, PackageNotFoundError as _PkgNotFound

from api.routers import meta, backtests, replay, schwab, optimize, data_export

try:
    _version = _pkg_version("autotrader")
except _PkgNotFound:
    _version = "unknown"

app = FastAPI(title="AutoTrader API", version=_version)

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
    logger.exception(f"Unhandled error on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"{type(exc).__name__}: {exc}",
            "path": request.url.path,
        },
    )


app.include_router(meta.router, prefix="/api")
app.include_router(backtests.router, prefix="/api")
app.include_router(replay.router, prefix="/api")
app.include_router(schwab.router, prefix="/api")
app.include_router(optimize.router, prefix="/api")
app.include_router(data_export.router, prefix="/api")
