"""Request/response models for the Strategy Optimizer (parameter sweep)."""

from datetime import date, time
from typing import Optional

from pydantic import BaseModel


class OptimizeRequest(BaseModel):
    data_source: str = "synthetic"
    symbol: str = "ES"
    timeframe: str = "5m"
    strategy_id: str
    initial_capital: float = 100_000.0
    contracts_per_trade: int = 1
    commission_per_contract: float = 2.50
    start_date: date
    end_date: date
    session_start: time = time(9, 30)
    session_end: time = time(16, 0)
    metric: str = "sharpe_ratio"  # "sharpe_ratio" | "total_return_pct" | "profit_factor"


class OptimizeCombo(BaseModel):
    params: dict
    total_return_pct: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    profit_factor: float
    max_drawdown_pct: float


class OptimizeResponse(BaseModel):
    metric: str
    combos_tested: int
    results: list[OptimizeCombo]
    best_backtest_id: Optional[str] = None
