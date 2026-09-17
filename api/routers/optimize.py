"""Strategy Optimizer — sweeps a strategy's own parameter grid (from
strategy_registry.STRATEGIES) through the real BacktestEngine and ranks the
results. Pure computation, no external calls; reuses the exact same engine/
provider path as a normal backtest run, just looped over combinations.
"""

import itertools
from datetime import datetime, time as time_type

from fastapi import APIRouter, HTTPException

from src.backtesting.engine import BacktestEngine

from api.deps import get_contract_spec
from api.strategy_registry import STRATEGIES, build_strategy
from api.routers.backtests import _build_provider
from api.auth import PROTECTED
from api import store, serializers
from api.schemas.optimize import OptimizeRequest, OptimizeResponse, OptimizeCombo

router = APIRouter(prefix="/optimize", tags=["optimize"])

MAX_COMBOS = 30
_METRICS = {"sharpe_ratio", "total_return_pct", "profit_factor"}


def _grid_size_for(n_params: int) -> int:
    if n_params == 0:
        return 1
    if n_params == 1:
        return 8
    return max(2, int(round(MAX_COMBOS ** (1.0 / n_params))))


def _param_grid(param_spec: dict, n_values: int) -> list:
    lo, hi = param_spec["min"], param_spec["max"]
    if n_values <= 1:
        return [param_spec["default"]]
    step = (hi - lo) / (n_values - 1)
    raw = [lo + step * i for i in range(n_values)]
    if param_spec["type"] == "int":
        return sorted(set(int(round(v)) for v in raw))
    return sorted(set(round(v, 3) for v in raw))


def _strategy_spec(strategy_id: str) -> dict:
    for s in STRATEGIES:
        if s["id"] == strategy_id:
            return s
    raise HTTPException(400, f"Unknown strategy id: {strategy_id!r}")


@router.post("", response_model=OptimizeResponse)
def run_optimizer(req: OptimizeRequest, user=PROTECTED):
    if req.metric not in _METRICS:
        raise HTTPException(400, f"metric must be one of {sorted(_METRICS)}")

    spec = _strategy_spec(req.strategy_id)
    param_names = [p["name"] for p in spec["params"]]
    grid_size = _grid_size_for(len(param_names))
    grids = [_param_grid(p, grid_size) for p in spec["params"]]

    combos = [dict(zip(param_names, values)) for values in itertools.product(*grids)] if grids else [{}]
    combos = combos[:MAX_COMBOS]

    contract_spec = get_contract_spec(req.symbol)
    provider = _build_provider(req.data_source, req.symbol, req.timeframe,
                               req.start_date, req.end_date, contract_spec,
                               session_start=req.session_start)
    start_dt = datetime.combine(req.start_date, time_type(0, 0))
    end_dt = datetime.combine(req.end_date, time_type(23, 59))

    results_list = []
    best = None  # (metric_value, params, results_object)
    for params in combos:
        strategy = build_strategy(req.strategy_id, params)
        engine = BacktestEngine(
            data_provider=provider, strategy=strategy, symbol=req.symbol, timeframe=req.timeframe,
            initial_capital=req.initial_capital, commission_per_contract=req.commission_per_contract,
            contracts_per_trade=req.contracts_per_trade,
            session_start=req.session_start, session_end=req.session_end, **contract_spec,
        )
        try:
            results = engine.run(start=start_dt, end=end_dt)
        except (ValueError, ImportError, RuntimeError):
            continue

        metric_value = getattr(results, req.metric) or 0.0
        results_list.append((metric_value, OptimizeCombo(
            params=params,
            total_return_pct=serializers._safe(results.total_return_pct) or 0.0,
            sharpe_ratio=serializers._safe(results.sharpe_ratio) or 0.0,
            win_rate=results.win_rate,
            total_trades=results.total_trades,
            # null, not 0.0 -- see api/serializers.py. Sent as-is so the table
            # reports what the run actually produced.
            profit_factor=serializers._safe(results.profit_factor),
            max_drawdown_pct=results.max_drawdown_pct,
        )))
        # NaN never wins, and never blocks a winner either. `nan > x` is False
        # for every x, so once a NaN candidate landed in `best` -- which the
        # first one always did -- no later combination could ever displace it,
        # and the optimiser returned an undefined run as the best of the grid.
        if metric_value == metric_value and (best is None or metric_value > best[0]):
            best = (metric_value, params, results)

    if not results_list:
        raise HTTPException(400, "No combination produced a valid backtest — check the date range and data source.")

    # Rank on the RAW metric, not on the serialised row. An infinite profit
    # factor serialises to null, and sorting the rows by that put the single
    # flawless combination last in the table while best_backtest_id pointed
    # straight at it -- the summary and the ranking disagreeing about the same
    # run. NaN is undefined rather than worst, but it cannot be ordered, so it
    # is placed last explicitly instead of landing wherever the sort leaves it.
    results_list.sort(key=lambda pair: (pair[0] == pair[0], pair[0] if pair[0] == pair[0] else 0.0),
                      reverse=True)
    ranked = [combo for _, combo in results_list]

    best_backtest_id = None
    if best is not None:
        _, _, best_results = best
        best_backtest_id = store.save(best_results, req.data_source, req.session_start,
                                      req.session_end, user_id=user.id)

    return OptimizeResponse(
        metric=req.metric,
        combos_tested=len(ranked),
        results=ranked[:10],
        best_backtest_id=best_backtest_id,
    )
