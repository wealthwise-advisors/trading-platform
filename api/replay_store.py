"""In-memory store for live-replay sessions, mirroring api/store.py's design
(single-process, dev-appropriate).

Holds a MultiReplaySession, which drives one ReplayEngine per selected
timeframe off a shared market clock. A single-timeframe session is just a grid
of one, so there is no separate code path for the original behaviour."""

import uuid
from dataclasses import dataclass

import pandas as pd

from src.backtesting.multi_replay import MultiReplaySession


@dataclass
class ReplaySession:
    session: MultiReplaySession
    df: pd.DataFrame            # source bars at the finest resolution, kept for Reset
    symbol: str
    strategy_name: str
    initial_capital: float
    data_source: str = "synthetic"


_STORE: dict[str, ReplaySession] = {}


def save(session: MultiReplaySession, df: pd.DataFrame, symbol: str, strategy_name: str,
         initial_capital: float, data_source: str = "synthetic") -> str:
    replay_id = f"RP-{uuid.uuid4().hex[:10]}"
    _STORE[replay_id] = ReplaySession(
        session=session, df=df, symbol=symbol,
        strategy_name=strategy_name, initial_capital=initial_capital,
        data_source=data_source,
    )
    return replay_id


def get(replay_id: str) -> ReplaySession | None:
    return _STORE.get(replay_id)
