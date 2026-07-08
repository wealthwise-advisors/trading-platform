"""In-memory store for live-replay sessions, mirroring api/store.py's design
(single-process, dev-appropriate — matches ReplayEngine's own single-session
model, same as the Streamlit ui/live_app.py it replaces)."""

import uuid
from dataclasses import dataclass

import pandas as pd

from src.backtesting.replay_engine import ReplayEngine


@dataclass
class ReplaySession:
    engine: ReplayEngine
    df: pd.DataFrame            # original bars, kept for Reset (engine.load() again)
    symbol: str
    strategy_name: str
    initial_capital: float


_STORE: dict[str, ReplaySession] = {}


def save(engine: ReplayEngine, df: pd.DataFrame, symbol: str, strategy_name: str,
         initial_capital: float) -> str:
    replay_id = f"RP-{uuid.uuid4().hex[:10]}"
    _STORE[replay_id] = ReplaySession(
        engine=engine, df=df, symbol=symbol,
        strategy_name=strategy_name, initial_capital=initial_capital,
    )
    return replay_id


def get(replay_id: str) -> ReplaySession | None:
    return _STORE.get(replay_id)
