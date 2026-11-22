"""Strategy research (upgrade plan, Feature 6): walk-forward testing as a background job.

WALK-FORWARD. The date range is cut into equal blocks of whole days. Each fold optimises
on `train_blocks` consecutive blocks with the Strategy Optimizer's own sweep, then runs
the winning parameters once on the NEXT block, which the choice never saw. The windows
roll forward one block per fold. The folds' test results are joined into one equity curve
-- the only honest picture of what optimising this strategy would have earned -- and the
walk-forward efficiency compares the test windows' daily return with the training
windows': near 1 the optimised edge carried over, near 0 or below it was fitted noise.

JOBS. A walk-forward is dozens of backtests, so it runs in a thread and the page asks for
progress. One job per account at a time; cancel stops it between backtests. Jobs live in
memory (like stored runs) and the newest 20 are kept.
"""
from __future__ import annotations

import threading
import uuid
from datetime import date, datetime, time as time_type, timedelta
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from api import auth, serializers
from api.routers.optimize import _METRICS, combo_count, sweep
from api.schemas.optimize import OptimizeRequest

router = APIRouter(prefix="/research", tags=["research"])


def windows(start: date, end: date, folds: int, train_blocks: int) -> list[tuple[date, date, date, date]]:
    """(train start, train end, test start, test end) per fold, all inclusive dates."""
    days = (end - start).days + 1
    blocks = folds + train_blocks
    if days < blocks:
        raise ValueError(f"The date range is too short: {days} day(s) for {blocks} blocks "
                         f"({train_blocks} training + {folds} test). Widen it or use fewer folds.")
    edge = [start + timedelta(days=round(i * days / blocks)) for i in range(blocks + 1)]
    out = []
    for f in range(folds):
        out.append((edge[f], edge[f + train_blocks] - timedelta(days=1),
                    edge[f + train_blocks], edge[f + train_blocks + 1] - timedelta(days=1)))
    return out


def _span(d0: date, d1: date) -> tuple[datetime, datetime]:
    return datetime.combine(d0, time_type(0, 0)), datetime.combine(d1, time_type(23, 59))


def walk_forward(req: OptimizeRequest, folds: int, train_blocks: int,
                 progress: Callable[[int, int], None] | None = None,
                 cancelled: Callable[[], bool] | None = None, provider=None) -> dict:
    win = windows(req.start_date, req.end_date, folds, train_blocks)
    # ONE series for the whole range, sliced by every window. Built per window, the demo
    # source generated the same prices for each (it seeds from the window's start), and a
    # real source would download the same bars dozens of times.
    from api.deps import get_contract_spec
    from api.routers.backtests import _build_provider
    spec = get_contract_spec(req.symbol)
    provider = provider or _build_provider(req.data_source, req.symbol, req.timeframe, req.start_date,
                                           req.end_date, spec, session_start=req.session_start)
    per_fold = combo_count(req.strategy_id) + 1
    total, done = per_fold * len(win), 0

    def tick():
        nonlocal done
        done += 1
        if progress:
            progress(done, total)

    out_folds, notes, test_trades = [], [], []
    stopped = False
    for i, (tr_s, tr_e, te_s, te_e) in enumerate(win, 1):
        if cancelled and cancelled():
            stopped = True
            break
        trained = sweep(req, *_span(tr_s, tr_e), provider=provider, contract_spec=spec,
                        progress=tick, cancelled=cancelled)
        ranked = [t for t in trained if t[0] == t[0]]          # NaN never wins (see the optimizer)
        if cancelled and cancelled():
            stopped = True
            break
        if not ranked:
            notes.append(f"Fold {i}: no training run worked ({tr_s} to {tr_e}); skipped.")
            tick()
            continue
        metric, params, train_res = max(ranked, key=lambda t: t[0])
        tested = _run_once(req, params, *_span(te_s, te_e), provider=provider, spec=spec)
        tick()
        if tested is None:
            notes.append(f"Fold {i}: no bars to test on ({te_s} to {te_e}); skipped.")
            continue
        test_trades += tested.trades
        out_folds.append({
            "train_start": tr_s.isoformat(), "train_end": tr_e.isoformat(),
            "test_start": te_s.isoformat(), "test_end": te_e.isoformat(),
            "params": params, "train_metric": serializers._safe(metric),
            "train_return_pct": serializers._safe(train_res.total_return_pct) or 0.0,
            "test_return_pct": serializers._safe(tested.total_return_pct) or 0.0,
            "test_sharpe": serializers._safe(tested.sharpe_ratio),
            "test_trades": tested.total_trades, "test_win_rate": tested.win_rate,
            "test_max_drawdown_pct": tested.max_drawdown_pct,
            "train_days": (tr_e - tr_s).days + 1, "test_days": (te_e - te_s).days + 1,
        })

    equity = [{"t": win[0][2].isoformat(), "equity": req.initial_capital}]
    level = req.initial_capital
    for tr in sorted(test_trades, key=lambda t: t.exit_time or t.entry_time):
        level += tr.pnl
        equity.append({"t": (tr.exit_time or tr.entry_time).isoformat(), "equity": round(level, 2)})

    train_daily = sum(f["train_return_pct"] for f in out_folds) / max(1, sum(f["train_days"] for f in out_folds))
    test_daily = sum(f["test_return_pct"] for f in out_folds) / max(1, sum(f["test_days"] for f in out_folds))
    return {
        "folds": out_folds, "notes": notes, "cancelled": stopped, "equity": equity,
        "test_return_pct": round((level / req.initial_capital - 1) * 100, 4),
        "test_trades": len(test_trades),
        # None when training made no money: a ratio to a loss says nothing.
        "efficiency": round(test_daily / train_daily, 3) if train_daily > 0 and out_folds else None,
    }


def _run_once(req: OptimizeRequest, params: dict, start_dt: datetime, end_dt: datetime, provider, spec):
    from api.strategy_registry import build_strategy
    from src.backtesting.engine import BacktestEngine
    engine = BacktestEngine(
        data_provider=provider, strategy=build_strategy(req.strategy_id, params), symbol=req.symbol,
        timeframe=req.timeframe, initial_capital=req.initial_capital,
        commission_per_contract=req.commission_per_contract, contracts_per_trade=req.contracts_per_trade,
        session_start=req.session_start, session_end=req.session_end, **spec)
    try:
        return engine.run(start=start_dt, end=end_dt)
    except (ValueError, ImportError, RuntimeError):
        return None


# ── jobs ────────────────────────────────────────────────────────────────────

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
KEEP = 20


class WalkForwardRequest(OptimizeRequest):
    folds: int = Field(default=4, ge=2, le=8)
    train_blocks: int = Field(default=3, ge=1, le=6)


def _public(job: dict) -> dict:
    return {k: job[k] for k in ("id", "kind", "status", "progress", "result", "error", "started_at")}


@router.post("/walk-forward")
def start_walk_forward(req: WalkForwardRequest, user=Depends(auth.require_user)):
    if req.metric not in _METRICS:
        raise HTTPException(400, f"metric must be one of {sorted(_METRICS)}")
    try:
        windows(req.start_date, req.end_date, req.folds, req.train_blocks)
    except ValueError as e:
        raise HTTPException(400, str(e))
    with _LOCK:
        if any(j["user"] == user.id and j["status"] == "running" for j in _JOBS.values()):
            raise HTTPException(409, "A research job is already running. Wait for it or cancel it.")
        job = {"id": uuid.uuid4().hex[:12], "user": user.id, "kind": "walk-forward", "status": "running",
               "progress": {"done": 0, "total": 0}, "result": None, "error": None,
               "started_at": datetime.now().isoformat(timespec="seconds"), "cancel": threading.Event()}
        _JOBS[job["id"]] = job
        while len(_JOBS) > KEEP:
            oldest = next((k for k, j in _JOBS.items() if j["status"] != "running"), None)
            if oldest is None:
                break
            _JOBS.pop(oldest)

    def run():
        try:
            res = walk_forward(req, req.folds, req.train_blocks,
                               progress=lambda d, t: job["progress"].update(done=d, total=t),
                               cancelled=job["cancel"].is_set)
            job["result"] = res
            job["status"] = "cancelled" if res["cancelled"] else "done"
        except Exception as e:                      # surfaced to the page, not swallowed
            job["error"], job["status"] = str(e), "failed"
    threading.Thread(target=run, name=f"walk-forward-{job['id']}", daemon=True).start()
    return {"job_id": job["id"]}


def _job(job_id: str, user) -> dict:
    job = _JOBS.get(job_id)
    if job is None or job["user"] != user.id:
        raise HTTPException(404, "No such research job.")
    return job


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user=Depends(auth.require_user)):
    return _public(_job(job_id, user))


@router.delete("/jobs/{job_id}")
def cancel_job(job_id: str, user=Depends(auth.require_user)):
    job = _job(job_id, user)
    job["cancel"].set()
    return _public(job)
