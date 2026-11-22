"""Monte Carlo on a run's trades (upgrade plan, Feature 6).

Shuffle: the same trades in another order -- the final P&L cannot change, the drawdown
can. Bootstrap: trades drawn with replacement -- the final P&L spreads too.
"""
import numpy as np
import pytest

from src.backtesting.monte_carlo import monte_carlo

PNLS = [500, -200, 300, -400, 800, -100, 250, -300, 600, -150] * 5


def test_repeatable_with_a_seed():
    assert monte_carlo(PNLS, 100_000, runs=500, seed=7) == monte_carlo(PNLS, 100_000, runs=500, seed=7)


def test_shuffling_never_changes_the_final_pnl():
    r = monte_carlo(PNLS, 100_000, runs=300, seed=1)["shuffle"]
    assert r["final_pnl"]["p5"] == r["final_pnl"]["p95"] == sum(PNLS)
    assert r["prob_loss"] == 0.0


def test_percentiles_match_a_brute_force_check():
    runs, seed = 400, 3
    r = monte_carlo(PNLS, 100_000, runs=runs, seed=seed)["bootstrap"]
    rng = np.random.default_rng(seed)
    rng.permuted(np.tile(PNLS, (runs, 1)), axis=1)          # the shuffle pass draws first
    finals = rng.choice(PNLS, size=(runs, len(PNLS)), replace=True).sum(axis=1)
    assert r["final_pnl"]["p50"] == pytest.approx(float(np.percentile(finals, 50)))
    assert r["prob_loss"] == pytest.approx(float((finals < 0).mean()))


def test_max_drawdown_is_measured_from_the_peak_including_the_start():
    r = monte_carlo([-1000, 2000, -500], 10_000, runs=1, seed=0)
    dd = r["actual"]["max_drawdown"]
    assert dd == 1000                                       # from 10,000 down to 9,000
    assert r["actual"]["max_drawdown_pct"] == pytest.approx(10.0)


def test_the_fan_has_one_band_per_trade():
    r = monte_carlo(PNLS, 100_000, runs=200, seed=2)
    fan = r["bootstrap"]["equity_fan"]
    assert len(fan["p50"]) == len(PNLS) + 1 and fan["p5"][0] == fan["p95"][0] == 100_000
    assert all(lo <= mid <= hi for lo, mid, hi in zip(fan["p5"], fan["p50"], fan["p95"]))


def test_the_chance_of_losing_a_set_amount():
    r = monte_carlo(PNLS, 100_000, runs=300, seed=4, loss_threshold=1000)
    assert 0.0 <= r["bootstrap"]["prob_loss_over"] <= r["bootstrap"]["prob_loss"] <= 1.0


def test_too_few_trades_is_an_error():
    with pytest.raises(ValueError, match="at least 2 trades"):
        monte_carlo([100], 100_000)
