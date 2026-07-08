"""
FastAPI backend for the AutoTrader dashboard.

Run from the trading-platform/ repo root (same CWD assumption ui/app.py
already makes for config/ and data/ relative paths):

    uvicorn api.main:app --reload --port 8000

The React dev server (web/) proxies /api/* to this process — see
web/vite.config.ts. Nothing under src/ is modified to support this; the API
is a thin consumer of the same backtesting/strategy/data-provider code the
Streamlit app already uses.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI

from api.routers import meta, backtests, replay, schwab

app = FastAPI(title="AutoTrader API")

app.include_router(meta.router, prefix="/api")
app.include_router(backtests.router, prefix="/api")
app.include_router(replay.router, prefix="/api")
app.include_router(schwab.router, prefix="/api")
