"""Strategy research (upgrade plan, Feature 6): walk-forward, Monte Carlo on a run, and the
list of saved runs the comparison picks from."""
import time
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from api import research
from api.main import app
from api.routers.optimize import sweep
from api.schemas.optimize import OptimizeRequest

client = TestClient(app)

BASE = {"data_source": "synthetic", "symbol": "ES", "timeframe": "15m", "strategy_id": "ma_crossover",
        "metric": "total_return_pct", "session_start": "00:00:00", "session_end": "23:59:00"}


# ── the windows ─────────────────────────────────────────────────────────────

def test_windows_roll_forward_and_every_test_is_unseen():
    w = research.windows(date(2026, 11, 1), date(2026, 11, 20), folds=3, train_blocks=2)
    assert len(w) == 3
    for tr_s, tr_e, te_s, te_e in w:
        assert tr_s <= tr_e < te_s <= te_e
    assert w[0][2] < w[1][2] < w[2][2]                   # test windows move forward
    assert w[-1][3] == date(2026, 11, 20)
    assert w[1][0] > w[0][0]                             # rolling, not anchored


def test_too_short_a_range_for_the_windows_is_refused():
    with pytest.raises(ValueError, match="too short"):
        research.windows(date(2026, 11, 1), date(2026, 11, 3), folds=3, train_blocks=2)


# ── walk-forward ────────────────────────────────────────────────────────────

def req(**kw):
    return OptimizeRequest(**{**BASE, "start_date": "2026-11-02", "end_date": "2026-11-13", **kw})


class Frame:
    """Bars across the whole range. The demo source fills only ~6.5 h per calendar day
    from the start, so later windows of a long demo range have no bars at all."""
    def __init__(self, df):
        self.df = df

    def load(self, symbol, start, end, timeframe):
        out = self.df.loc[start:end]
        if out.empty:
            raise ValueError("No data")
        return out


@pytest.fixture(scope="module")
def frame(tmp_path_factory):
    from src.data.sample_data import generate_sample_data
    df = generate_sample_data("ES", datetime(2026, 11, 2), bars=12 * 96, timeframe_minutes=15,
                              save_dir=str(tmp_path_factory.mktemp("wf")))
    return Frame(df[["open", "high", "low", "close", "volume"]])


def full_provider(r, frame):
    return frame


def test_each_fold_trades_the_params_its_training_window_chose(frame):
    r = req()
    prov = full_provider(r, frame)
    out = research.walk_forward(r, folds=2, train_blocks=1, provider=prov)
    assert len(out["folds"]) == 2
    for f in out["folds"]:
        trained = sweep(r, datetime.fromisoformat(f["train_start"]),
                        datetime.combine(date.fromisoformat(f["train_end"]), datetime.max.time()), provider=prov)
        top = max(trained, key=lambda t: t[0] if t[0] == t[0] else float("-inf"))
        assert f["params"] == top[1]
        assert f["train_end"] < f["test_start"]
    assert "efficiency" in out and "test_return_pct" in out
    assert out["equity"][0]["equity"] == r.initial_capital


def test_windows_see_different_prices(frame):
    out = research.walk_forward(req(), folds=2, train_blocks=1, provider=frame)
    a, b = out["folds"]
    assert (a["train_return_pct"], a["test_return_pct"]) != (b["train_return_pct"], b["test_return_pct"])


def test_every_window_reads_one_series_loaded_once(monkeypatch):
    """Built per window, the demo source produced identical prices in every window."""
    from api.routers import backtests
    built = []
    real = backtests._build_provider
    monkeypatch.setattr(backtests, "_build_provider", lambda *a, **k: built.append(a) or real(*a, **k))
    research.walk_forward(req(), folds=2, train_blocks=1)
    assert len(built) == 1 and built[0][3:5] == (date(2026, 11, 2), date(2026, 11, 13))


def test_progress_counts_every_run_and_cancel_stops_early(frame):
    r = req()
    seen = []
    research.walk_forward(r, folds=2, train_blocks=1, progress=lambda d, t: seen.append((d, t)), provider=frame)
    assert seen[-1][0] == seen[-1][1] and seen[-1][1] > 2
    calls = []
    out = research.walk_forward(r, folds=2, train_blocks=1, provider=frame,
                                progress=lambda d, t: calls.append(d), cancelled=lambda: len(calls) >= 3)
    assert out["cancelled"] is True and len(calls) <= 4


# ── the job and its endpoints ───────────────────────────────────────────────

def test_walk_forward_runs_as_a_job_with_progress():
    body = {**BASE, "start_date": "2026-11-02", "end_date": "2026-11-13", "folds": 2, "train_blocks": 1}
    r = client.post("/api/research/walk-forward", json=body)
    assert r.status_code == 200, r.text
    job = r.json()["job_id"]
    for _ in range(300):
        st = client.get(f"/api/research/jobs/{job}").json()
        if st["status"] != "running":
            break
        time.sleep(0.2)
    assert st["status"] == "done", st
    assert st["progress"]["done"] == st["progress"]["total"]
    # Demo data covers only the start of a long range: a fold with no bars is skipped
    # with a note rather than reported as a flat result.
    assert len(st["result"]["folds"]) + len(st["result"]["notes"]) == 2


def test_one_job_at_a_time_and_cancel():
    body = {**BASE, "start_date": "2026-11-02", "end_date": "2026-11-13", "folds": 2, "train_blocks": 1}
    job = client.post("/api/research/walk-forward", json=body).json()["job_id"]
    second = client.post("/api/research/walk-forward", json=body)
    assert second.status_code == 409
    assert client.delete(f"/api/research/jobs/{job}").status_code == 200
    for _ in range(300):
        st = client.get(f"/api/research/jobs/{job}").json()
        if st["status"] != "running":
            break
        time.sleep(0.2)
    assert st["status"] in ("cancelled", "done")


def test_an_unknown_job_is_404():
    assert client.get("/api/research/jobs/nope").status_code == 404


def test_bad_windows_are_a_400():
    body = {**BASE, "start_date": "2026-11-02", "end_date": "2026-11-03", "folds": 4, "train_blocks": 3}
    assert client.post("/api/research/walk-forward", json=body).status_code == 400


# ── Monte Carlo on a stored run, and the runs to compare ────────────────────

@pytest.fixture(scope="module")
def run_id():
    r = client.post("/api/backtests", json={
        "symbol": "ES", "timeframe": "5m", "data_source": "synthetic", "strategy_id": "rsi_mean_reversion",
        "params": {"period": 5, "oversold": 30, "overbought": 70},
        "start_date": "2026-11-09", "end_date": "2026-11-13",
        "session_start": "00:00:00", "session_end": "23:59:00"})
    assert r.status_code == 200, r.text
    return r.json()["backtest_id"]


def test_monte_carlo_of_a_stored_run(run_id):
    r = client.post(f"/api/backtests/{run_id}/monte-carlo", json={"runs": 300, "seed": 1, "loss_threshold": 500})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["runs"] == 300 and body["trades"] >= 2
    assert set(body["bootstrap"]) >= {"final_pnl", "max_drawdown_pct", "prob_loss", "prob_loss_over", "equity_fan"}


def test_monte_carlo_limits_its_runs(run_id):
    assert client.post(f"/api/backtests/{run_id}/monte-carlo", json={"runs": 999_999}).status_code == 422


def test_saved_runs_are_listed_newest_first(run_id):
    rows = client.get("/api/backtests").json()
    assert rows[0]["id"] == run_id
    assert {"symbol", "strategy_name", "timeframe", "total_return_pct", "sharpe_ratio"} <= set(rows[0])
