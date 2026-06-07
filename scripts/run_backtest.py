"""
Quick CLI backtest runner.

Examples:
    python scripts/run_backtest.py --symbol ES --strategy ma --fast 9 --slow 21
    python scripts/run_backtest.py --symbol NQ --strategy rsi --period 14
    python scripts/run_backtest.py --symbol ES --strategy breakout --lookback 20
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
from datetime import datetime

from src.data.csv_provider import CSVDataProvider
from src.data.sample_data import generate_sample_data
from src.strategies import MACrossoverStrategy, RSIMeanReversionStrategy, BreakoutStrategy
from src.backtesting.engine import BacktestEngine

CONTRACT_SPECS = {
    "ES":  dict(tick_size=0.25, tick_value=12.50, point_value=50.0,   base_price=4500.0),
    "NQ":  dict(tick_size=0.25, tick_value=5.00,  point_value=20.0,   base_price=15000.0),
    "MES": dict(tick_size=0.25, tick_value=1.25,  point_value=5.0,    base_price=4500.0),
    "CL":  dict(tick_size=0.01, tick_value=10.00, point_value=1000.0, base_price=75.0),
}


def main():
    parser = argparse.ArgumentParser(description="Run a backtest from the command line")
    parser.add_argument("--symbol", default="ES", choices=CONTRACT_SPECS.keys())
    parser.add_argument("--timeframe", default="5m", choices=["1m", "5m", "15m", "1h"])
    parser.add_argument("--strategy", default="ma", choices=["ma", "rsi", "breakout"])
    parser.add_argument("--start", default="2024-01-02")
    parser.add_argument("--end", default="2025-01-01")
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--contracts", type=int, default=1)
    # MA params
    parser.add_argument("--fast", type=int, default=9)
    parser.add_argument("--slow", type=int, default=21)
    # RSI params
    parser.add_argument("--period", type=int, default=14)
    parser.add_argument("--oversold", type=float, default=30.0)
    parser.add_argument("--overbought", type=float, default=70.0)
    # Breakout params
    parser.add_argument("--lookback", type=int, default=20)
    parser.add_argument("--atr-mult", type=float, default=2.0)
    args = parser.parse_args()

    spec = CONTRACT_SPECS[args.symbol]
    tf_min = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}[args.timeframe]
    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d")

    # Ensure data exists
    data_file = Path(f"data/historical/{args.symbol}_{args.timeframe}.csv")
    if not data_file.exists():
        print(f"Generating sample data for {args.symbol}…")
        generate_sample_data(
            symbol=args.symbol,
            start=start.replace(hour=9, minute=30),
            bars=3000,
            timeframe_minutes=tf_min,
            base_price=spec["base_price"],
            tick_size=spec["tick_size"],
        )

    # Build strategy
    if args.strategy == "ma":
        strategy = MACrossoverStrategy(fast=args.fast, slow=args.slow)
    elif args.strategy == "rsi":
        strategy = RSIMeanReversionStrategy(period=args.period, oversold=args.oversold, overbought=args.overbought)
    else:
        strategy = BreakoutStrategy(lookback=args.lookback, atr_mult=args.atr_mult)

    engine = BacktestEngine(
        data_provider=CSVDataProvider("data/historical"),
        strategy=strategy,
        symbol=args.symbol,
        timeframe=args.timeframe,
        initial_capital=args.capital,
        contracts_per_trade=args.contracts,
        tick_size=spec["tick_size"],
        tick_value=spec["tick_value"],
        point_value=spec["point_value"],
    )

    results = engine.run(start, end)

    print("\n" + "=" * 55)
    print(f"  {results.strategy_name}  |  {results.symbol}  |  {args.timeframe}")
    print("=" * 55)
    print(f"  Total Trades   : {results.total_trades}")
    print(f"  Win Rate       : {results.win_rate:.1f}%  ({results.winning_trades}W / {results.losing_trades}L)")
    print(f"  Total P&L      : ${results.total_pnl:,.0f}")
    print(f"  Return         : {results.total_return_pct:+.1f}%")
    print(f"  Sharpe Ratio   : {results.sharpe_ratio:.2f}")
    print(f"  Max Drawdown   : {results.max_drawdown_pct:.1f}%")
    print(f"  Profit Factor  : {results.profit_factor:.2f}")
    print(f"  Avg Win        : ${results.avg_win:,.0f}")
    print(f"  Avg Loss       : ${results.avg_loss:,.0f}")
    print(f"  Final Capital  : ${results.final_capital:,.0f}")
    print("=" * 55)


if __name__ == "__main__":
    main()
