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
from src.analysis.elliott_wave import (
    DEFAULT_RATIO,
    DEFAULT_SCALES,
    DEFAULT_THETA_BASE,
)
from api.report.report import generate_html_report

from api.deps import get_contract_spec, BASE_PRICES
from api.strategy_registry import build_strategy
from api import store, serializers
from api.schemas.backtest import BacktestRequest
from api.schemas.elliott_wave import ElliottWaveResponse

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
                    start_date, end_date, spec: dict, session_start=None):
    """
    `session_start` only anchors resample bins (see ExternalCSVProvider._resample).
    Passing it keeps the backtest's bars on the same grid the replay uses; leaving
    it None keeps the calendar-day default, which is right for a 24-hour chart.
    """
    if data_source == "rithmic":
        if not _RITHMIC_AVAILABLE:
            raise HTTPException(400, "Rithmic data source unavailable — pyrithmic not installed.")
        return RithmicDataProvider(cache_dir="data/historical")
    if data_source == "schwab":
        if not _SCHWAB_AVAILABLE:
            raise HTTPException(400, "Schwab data source unavailable — check config/credentials.yaml.")
        # session_start was accepted here and then dropped on the floor for
        # Schwab, so the six timeframes it has to build itself came back on a
        # midnight grid while the replay built them on the session grid.
        provider = SchwabDataProvider(session_start=session_start)
        if not provider.is_authenticated():
            raise HTTPException(400, "Not authenticated with Schwab. Complete the auth flow first.")
        return provider
    if data_source == "external_csv":
        if not _EXTERNAL_AVAILABLE:
            raise HTTPException(400, "External CSV data source unavailable.")
        try:
            return ExternalCSVProvider(session_start=session_start)
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


def _explain_run_failure(exc: Exception, req) -> str:
    """Turn an engine/provider error into something a user can act on.

    The bare provider message reads
    "No bars found for ES between 2026-08-07 00:00:00 and 2026-08-07 23:59:00
    in ['ES_FULL.csv']" -- accurate, but it never says which dates WOULD work,
    so the only way forward was guessing. When the CSV source is in play we
    know exactly what is on disk, so say so.
    """
    msg = str(exc)
    if req.data_source != "external_csv" or "No bars found" not in msg:
        return msg
    try:
        from pathlib import Path
        from src.data.external_csv_provider import ExternalCSVProvider
        from api.routers.meta import csv_coverage

        cov = csv_coverage(Path(ExternalCSVProvider().data_dir), req.symbol)
    except Exception:
        return msg
    if not cov:
        return (f"No sample data is bundled for {req.symbol}. "
                f"Pick another symbol, or point data.external_dir at an archive that has it.")
    ranges = ", ".join(f"{c['start']} to {c['end']}" for c in cov)
    plural = "ranges" if len(cov) > 1 else "range"
    return (f"No {req.symbol} data between {req.start_date} and {req.end_date}. "
            f"Available {plural}: {ranges}.")


@router.post("")
def run_backtest(req: BacktestRequest):
    spec = get_contract_spec(req.symbol)
    provider = _build_provider(req.data_source, req.symbol, req.timeframe,
                               req.start_date, req.end_date, spec,
                               session_start=req.session_start)
    # The provider does not touch the filesystem until run() asks it to, so a
    # missing CSV surfaced here as an unhandled FileNotFoundError -> bare 500.
    # Probed explicitly so the caller gets told which input to change.
    if req.data_source == "external_csv":
        try:
            provider.load(
                req.symbol,
                datetime.combine(req.start_date, time_type(0, 0)),
                datetime.combine(req.end_date, time_type(23, 59)),
                req.timeframe,
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                400,
                f"No '{req.data_source}' data for {req.symbol}. {exc} "
                f"Pick a symbol that has been exported, or switch the data source "
                f"to Synthetic or Live (Schwab).",
            )
    # Task 10.1 verification found this crashed with a raw, unhandled
    # KeyError (500) instead of a clean validation error when `params` is
    # missing a required strategy param (e.g. ma_crossover needs
    # fast/slow) -- build_strategy() indexes params["fast"] directly with
    # no default. Same try/except-to-HTTPException(400) pattern already
    # used below for engine.run().
    try:
        strategy = build_strategy(req.strategy_id, req.params)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(400, f"Invalid or missing strategy parameter for '{req.strategy_id}': {exc}")

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
        raise HTTPException(400, _explain_run_failure(exc, req))

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
    return serializers.price_data_to_response(stored.results.price_data, stored.session_start)


@router.get("/{backtest_id}/equity-curve")
def get_equity_curve(backtest_id: str):
    stored = _get_or_404(backtest_id)
    return serializers.equity_curve_to_records(stored.results)


@router.get("/{backtest_id}/zigzag")
def get_zigzag(backtest_id: str, dev_3: float = Query(0.0005), dev_10: float = Query(0.0010)):
    stored = _get_or_404(backtest_id)
    return serializers.zigzag_to_records(stored.results.price_data, dev_3, dev_10)


@router.get("/{backtest_id}/elliott-wave", response_model=ElliottWaveResponse)
def get_elliott_wave(
    backtest_id: str,
    theta_base: float = Query(DEFAULT_THETA_BASE, gt=0, lt=1),
    ratio: float = Query(DEFAULT_RATIO, gt=1),
    scales: int = Query(DEFAULT_SCALES, ge=1, le=8),
):
    """Elliott Wave analysis of a stored backtest's price data.

    Read-only: reads `price_data` from the in-memory store, never re-runs the
    backtest and never re-fetches market data.

    The only query parameters are the pivot ladder's D-13 values -- the sole
    configurable knobs the SRS defines (FR-1e.3 / API-1.4). Defaults are the
    engine's own, and FR-1e.4 requires those two to stay in lockstep.

    The response deliberately surfaces what was NOT evaluated: every wave
    carries `state` and `blocked_by`, and the payload carries `blocked_rules`
    plus `notes`. A client must never be able to render a partial analysis as
    though it were complete (FE-3).
    """
    stored = _get_or_404(backtest_id)
    return serializers.elliott_wave_to_records(
        stored.results.price_data, theta_base, ratio, scales
    )


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
    # _safe() also narrows numpy scalars: confidence is derived from the price
    # frame, which ExternalCSVProvider loads as float32 -- and float32 cannot
    # be JSON-encoded by FastAPI. See api/serializers._safe.
    return [
        {"timestamp": p.timestamp.isoformat(), "pattern": p.pattern,
         "direction": p.direction, "confidence": serializers._safe(p.confidence)}
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
         # Same float32 narrowing as above -- round() on a numpy scalar returns
         # a numpy scalar, and metrics values come straight off the frame.
         "neckline": serializers._safe(round(float(p.neckline), 2)),
         "metrics": {k: serializers._safe(v) for k, v in (p.metrics or {}).items()}}
        for p in patterns
    ]


@router.get("/{backtest_id}/report")
def get_report(backtest_id: str, zz_dev: float = Query(0.0010), zz_dev_3: float = Query(0.0005),
               format: str = Query("html")):
    """Backtest report, downloadable as HTML (full charts, via
    api/report/report.py) or as CSV/Excel/PDF/Word (metrics summary + trade
    log table only -- those formats can't carry interactive Plotly charts)."""
    stored = _get_or_404(backtest_id)
    r = stored.results
    base_name = f"backtest_{r.symbol}_{r.strategy_name}"

    if format == "html":
        html = generate_html_report(r, zz_deviation=zz_dev, zz_deviation_3=zz_dev_3,
                                    session_start=stored.session_start)
        return Response(
            content=html, media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.html"'},
        )

    if format not in ("csv", "xlsx", "pdf", "docx"):
        raise HTTPException(400, "format must be one of: html, csv, xlsx, pdf, docx")

    from api.export import formats as fmt
    from api.export.report_export import build_metrics_df, build_trades_df

    metrics_df = build_metrics_df(r)
    trades_df = build_trades_df(r)
    title = f"{r.symbol} — {r.strategy_name}"
    subtitle = f"{r.start_date.date()} to {r.end_date.date()} · {r.timeframe}"
    filename = f"{base_name}.{format}"

    if format == "csv":
        # CSV is single-table -- metrics as a leading block, trade log below.
        content = (
            metrics_df.to_csv().encode("utf-8") + b"\n" + trades_df.to_csv().encode("utf-8")
        )
    elif format == "xlsx":
        content = fmt.excel_bytes({"Summary": metrics_df, "Trades": trades_df})
    elif format == "pdf":
        content = fmt.pdf_bytes(title, [("Summary", metrics_df), ("Trade Log", trades_df)], subtitle=subtitle)
    else:
        content = fmt.docx_bytes(title, [("Summary", metrics_df), ("Trade Log", trades_df)], subtitle=subtitle)

    return Response(
        content=content, media_type=fmt.media_type_for(format),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
