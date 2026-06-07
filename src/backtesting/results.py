from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import pandas as pd


@dataclass
class Trade:
    """A completed round-trip trade (entry + exit)."""
    symbol: str
    direction: str           # "LONG" or "SHORT"
    quantity: int
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime]
    exit_price: Optional[float]
    pnl: float               # net P&L in USD after commissions
    commission: float
    strategy: str = ""
    entry_order_id: str = ""
    exit_order_id: str = ""

    @property
    def gross_pnl(self) -> float:
        return self.pnl + self.commission

    @property
    def duration_minutes(self) -> Optional[float]:
        if self.exit_time is None:
            return None
        return (self.exit_time - self.entry_time).total_seconds() / 60


@dataclass
class BacktestResults:
    symbol: str
    strategy_name: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)  # timestamp -> portfolio value
    price_data: pd.DataFrame = field(default_factory=pd.DataFrame)  # full OHLCV

    # Computed metrics (filled by compute_metrics)
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_trade_duration_min: float = 0.0
    final_capital: float = 0.0

    def trades_df(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame([
            {
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "symbol": t.symbol,
                "direction": t.direction,
                "qty": t.quantity,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "commission": t.commission,
                "duration_min": t.duration_minutes,
                "strategy": t.strategy,
            }
            for t in self.trades
        ])
