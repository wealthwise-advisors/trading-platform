"""Backtest run + result sub-resource endpoints."""

from datetime import datetime, time as time_type

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from src.data.csv_provider import CSVDataProvider
from src.data.sample_data import generate_sample_data
from src.backtesting.engine import BacktestEngine
from src.backtesting.trade_quality import score_trades
from src.analysis.candlestick_patterns import detect_candlestick_patterns
from src.analysis.chart_patterns import find_chart_patterns
from ui.report import generate_html_report

from api.deps import get_contract_spec, BASE_PRICES
from api.strategy_registry import build_strategy, strategy_label
from api import store, serializers
from api.schemas.backtest import BacktestRequest

try:
    from src.data.external_csv_provider import ExternalCSVProvider
    _EXTERNAL_AVAILABLE = True
except Exception:
    _EXTERNAL_AVAILABLE = False
try:
    from src.data.schwab_provider import SchwabDataProvider
    _SCHWAB_AVAILABLE = True
except Exception:
    _SCHWAB_AVAILABLE = False
try:
    from src.data.rithmic_provider import RithmicDataProvider
    _RITHMIC_AVAILABLE = True
except ImportError:
    _RITHMIC_AVAILABLE = False

router = APIRouter(prefix="/backtests", tags=["backtests"])


def _build_provider(data_source: str, symbol: str, timeframe: str,
                    start_date, end_date, spec: dict):
    if data_source == "rithmic":
        if not _RITHMIC_AVAILABLE:
            raise HTTPException(400, "Rithmic data source unavailable — pyrithmic not installed.")
        return RithmicDataProvider(cache_dir="data/historical")
    if data_source == "schwab":
        if not _SCHWAB_AVAILABLE:
            raise HTTPException(400, "Schwab data source unavailable — check config/credentials.yaml.")
        provider = SchwabDataProvider()
        if not provider.is_authenticated():
            raise HTTPException(400, "Not authenticated with Schwab. Complete the auth flow first.")
        return provider
    if data_source == "external_csv":
        if not _EXTERNAL_AVAILABLE:
            raise HTTPException(400, "External CSV data source unavailable.")
        try:
            return ExternalCSVProvider()
        except FileNotFoundError as e:
            raise HTTPException(400, str(e))

    # synthetic (default)
    tf_min = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60}[timeframe]
    total_minutes = (end_date - start_date).days * 6.5 * 60
    bars = max(int(total_minutes / tf_min), 100)
    generate_sample_data(
        symbol=symbol,
        start=datetime.combine(start_date, datetime.min.time()).replace(hour=9, minute=30),
        bars=bars,
        timeframe_minutes=tf_min,
        base_price=BASE_PRICES.get(symbol, 4500.0),
        tick_size=spec["tick_size"],
        save_dir="data/historical",
        tf_label=timeframe,
    )
    return CSVDataProvider("data/historical")


@router.post("")
def run_backtest(req: BacktestRequest):
    spec = get_contract_spec(req.symbol)
    provider = _build_provider(req.data_source, req.symbol, req.timeframe,
                               req.start_date, req.end_date, spec)
    strategy = build_strategy(req.strategy_id, req.params)

    engine = BacktestEngine(
        data_provider=provider,
        strategy=strategy,
        symbol=req.symbol,
        timeframe=req.timeframe,
        initial_capital=req.initial_capital,
        commission_per_contract=req.commission_per_contract,
        contracts_per_trade=req.contracts_per_trade,
        session_start=req.session_start,
        session_end=req.session_end,
        **spec,
    )
    start_dt = datetime.combine(req.start_date, time_type(0, 0))
    end_dt = datetime.combine(req.end_date, time_type(23, 59))
    try:
        results = engine.run(start=start_dt, end=end_dt)
    except (ValueError, ImportError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))

    backtest_id = store.save(results, req.data_source, req.session_start, req.session_end)
    return serializers.results_to_summary(backtest_id, results, req.data_source,
                                          req.session_start, req.session_end)


def _get_or_404(backtest_id: str) -> store.StoredBacktest:
    stored = store.get(backtest_id)
    if stored is None:
        raise HTTPException(404, f"Backtest {backtest_id!r} not found — it may have expired "
                                 "(results are held in memory) or the id is wrong.")
    return stored


@router.get("/{backtest_id}")
def get_backtest(backtest_id: str):
    stored = _get_or_404(backtest_id)
    return serializers.results_to_summary(backtest_id, stored.results, stored.data_source,
                                          stored.session_start, stored.session_end)


@router.get("/{backtest_id}/trades")
def get_trades(backtest_id: str):
    stored = _get_or_404(backtest_id)
    quality = score_trades(stored.results)
    quality_by_index = {q.trade_index: q for q in quality}
    return serializers.trades_to_records(stored.results, quality_by_index)


@router.get("/{backtest_id}/price-data")
def get_price_data(backtest_id: str):
    stored = _get_or_404(backtest_id)
    return serializers.price_data_to_response(stored.results.price_data)


@router.get("/{backtest_id}/equity-curve")
def get_equity_curve(backtest_id: str):
    stored = _get_or_404(backtest_id)
    return serializers.equity_curve_to_records(stored.results)


@router.get("/{backtest_id}/zigzag")
def get_zigzag(backtest_id: str, dev_3: float = Query(0.003), dev_10: float = Query(0.003)):
    stored = _get_or_404(backtest_id)
    return serializers.zigzag_to_records(stored.results.price_data, dev_3, dev_10)


@router.get("/{backtest_id}/win-loss")
def get_win_loss(backtest_id: str):
    stored = _get_or_404(backtest_id)
    return serializers.win_loss(stored.results)


@router.get("/{backtest_id}/monthly-returns")
def get_monthly_returns(backtest_id: str):
    stored = _get_or_404(backtest_id)
    return serializers.monthly_returns(stored.results)


@router.get("/{backtest_id}/candlestick-patterns")
def get_candlestick_patterns(backtest_id: str, min_confidence: float = Query(70.0)):
    stored = _get_or_404(backtest_id)
    patterns = detect_candlestick_patterns(stored.results.price_data)
    return [
        {"timestamp": p.timestamp.isoformat(), "pattern": p.pattern,
         "direction": p.direction, "confidence": p.confidence}
        for p in patterns if p.confidence >= min_confidence
    ]


@router.get("/{backtest_id}/chart-patterns")
def get_chart_patterns(backtest_id: str):
    stored = _get_or_404(backtest_id)
    df = stored.results.price_data
    patterns = find_chart_patterns(df, left=2, right=2, min_move=0.0)
    return [
        {"pattern": p.pattern, "direction": p.direction,
         "start": df.index[p.start_index].isoformat(), "end": df.index[p.end_index].isoformat(),
         "neckline": round(p.neckline, 2), "metrics": p.metrics}
        for p in patterns
    ]


@router.get("/{backtest_id}/report")
def get_report(backtest_id: str, zz_dev: float = Query(0.015)):
    """Self-contained offline HTML report — reuses ui/report.py as-is (no
    Streamlit dependency in that module), same file the old dashboard's
    'Export Report' button produced."""
    stored = _get_or_404(backtest_id)
    html = generate_html_report(stored.results, zz_deviation=zz_dev)
    filename = f"backtest_{stored.results.symbol}_{stored.results.strategy_name}.html"
    return Response(
        content=html, media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
