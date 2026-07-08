"""Request/response models for the live-replay endpoints."""

from datetime import date

from pydantic import BaseModel


class ReplayCreateRequest(BaseModel):
    symbol: str = "ES"
    timeframe: str = "5m"
    strategy_id: str
    params: dict = {}
    initial_capital: float = 100_000.0
    contracts_per_trade: int = 1
    start_date: date
    end_date: date


class ReplayCreateResponse(BaseModel):
    replay_id: str
    total_bars: int
    symbol: str
    strategy_name: str
    initial_capital: float
