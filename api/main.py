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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from importlib.metadata import version as _pkg_version, PackageNotFoundError as _PkgNotFound

from api.routers import meta, backtests, replay, schwab, optimize, elliott_wave, data_export

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

app.include_router(meta.router, prefix="/api")
app.include_router(backtests.router, prefix="/api")
app.include_router(replay.router, prefix="/api")
app.include_router(schwab.router, prefix="/api")
app.include_router(optimize.router, prefix="/api")
app.include_router(elliott_wave.router, prefix="/api")
app.include_router(data_export.router, prefix="/api")
