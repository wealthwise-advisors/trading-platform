"""Pydantic request/response models for the backtest endpoints."""

from datetime import date, time
from typing import Optional

from pydantic import BaseModel


class BacktestRequest(BaseModel):
    data_source: str = "synthetic"      # "synthetic" | "external_csv" | "schwab" | "rithmic"
    symbol: str = "ES"
    timeframe: str = "5m"
    strategy_id: str
    params: dict = {}
    initial_capital: float = 100_000.0
    contracts_per_trade: int = 1
    commission_per_contract: float = 2.50
    start_date: date
    end_date: date
    # None on either side means "don't filter that edge" -- both None is the
    # 24-hour session, which is the correct default for anything that trades
    # continuously (crypto) and the only way to see pre/post-market activity.
    session_start: Optional[time] = time(9, 30)
    session_end: Optional[time] = time(16, 0)
    # Fractions, not percentages: 0.0005 == 0.05%. The minor (3-leg)
    # zigzag must be finer than the major (10-leg) one it nests inside.
    zigzag_dev_3: float = 0.0005
    zigzag_dev_10: float = 0.0010


class BacktestSummary(BaseModel):
    backtest_id: str
    symbol: str
    strategy_name: str
    timeframe: str
    start_date: date
    end_date: date
    session_start: Optional[time]
    session_end: Optional[time]
    data_source: str
    initial_capital: float
    final_capital: float
    total_pnl: float
    total_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_trade_duration_min: float
    data_points: int


class TradeRecord(BaseModel):
    entry_time: str
    exit_time: Optional[str]
    symbol: str
    direction: str
    qty: int
    entry_price: float
    exit_price: Optional[float]
    pnl: float
    commission: float
    duration_min: Optional[float]
    strategy: str
    quality_score: Optional[float] = None
    quality_grade: Optional[str] = None


class OHLCVRecord(BaseModel):
    t: str
    o: float
    h: float
    l: float
    c: float
    v: Optional[float] = None


class IndicatorSeries(BaseModel):
    ema9: list[Optional[float]]
    ema21: list[Optional[float]]
    rsi2: list[Optional[float]]
    rsi13: list[Optional[float]]
    stoch_k: list[Optional[float]]
    stoch_d: list[Optional[float]]


class PriceDataResponse(BaseModel):
    bars: list[OHLCVRecord]
    indicators: IndicatorSeries


class EquityPoint(BaseModel):
    t: str
    equity: float
    drawdown_pct: float


class ZigZagPoint(BaseModel):
    t: str
    price: float
    type: str
    swing: int
    sub: int
    label: str


class WinLoss(BaseModel):
    wins: int
    losses: int
    win_rate: float
