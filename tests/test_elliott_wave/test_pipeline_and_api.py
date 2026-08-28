"""Pipeline determinism, edge cases, momentum warmup, and the API endpoint."""

import json

import pandas as pd
import pytest

from src.analysis.elliott_wave import EngineConfig, momentum, run_analysis
from src.analysis.elliott_wave.models import Direction

from .conftest import bars_from_path


# ── IMP-06 / RSI(13): UNDECIDABLE on unavailable data ───────────────────────
class TestMomentumWarmup:
    def test_nan_rsi_returns_none_not_false(self):
        """FR-3.1a.6: unavailable data is UNDECIDABLE, never a failed gate."""
        rsi = pd.Series([float("nan")] * 20)
        assert momentum.has_divergence(rsi, 5, 100.0, 15, 120.0, Direction.UP) is None

    def test_nan_at_either_bar_alone_is_enough(self):
        rsi = pd.Series([50.0] * 20)
        rsi.iloc[5] = float("nan")
        assert momentum.has_divergence(rsi, 5, 100.0, 15, 120.0, Direction.UP) is None
        rsi2 = pd.Series([50.0] * 20)
        rsi2.iloc[15] = float("nan")
        assert momentum.has_divergence(rsi2, 5, 100.0, 15, 120.0, Direction.UP) is None

    def test_thirteen_bar_warmup_is_nan_by_construction(self):
        """calc_rsi uses min_periods=13, so the warmup window is unavoidable --
        this is the real-data path into UNDECIDABLE."""
        df = bars_from_path([100, 110, 100, 112], bars_per_leg=10)
        rsi = momentum.rsi_series(df, 13)
        assert rsi.iloc[:13].isna().all()
        assert momentum.has_divergence(rsi, 2, 100.0, 5, 110.0, Direction.UP) is None

    def test_out_of_range_index_is_undecidable(self):
        rsi = pd.Series([50.0] * 10)
        assert momentum.has_divergence(rsi, 3, 100.0, 999, 120.0, Direction.UP) is None

    def test_decidable_once_past_warmup(self):
        rsi = pd.Series([50.0] * 40)
        rsi.iloc[20] = 80.0
        rsi.iloc[30] = 60.0
        assert momentum.has_divergence(rsi, 20, 100.0, 30, 120.0, Direction.UP) is True


# ── determinism at scale ────────────────────────────────────────────────────
class TestDeterminism:
    def _sig(self, res):
        return json.dumps(
            {
                "engine": res.engine_version,
                "pivots": [(p.scale, p.index, p.confirm_index, p.price, p.kind.value)
                           for p in res.pivots],
                "waves": [(w.id, w.scale, w.state.value,
                           w.structure_type.value if w.structure_type else None,
                           w.label, sorted(w.blocked_by),
                           sorted((k, str(v)) for k, v in w.measurements.items()))
                          for w in res.waves],
                "blocked": res.blocked_rules,
                "notes": res.notes,
            },
            sort_keys=True, default=str,
        )

    def test_twenty_runs_byte_identical(self, reference_df):
        first = self._sig(run_analysis(reference_df))
        for i in range(19):
            assert self._sig(run_analysis(reference_df)) == first, f"run {i+2} differed"

    def test_input_frame_untouched_after_full_run(self, reference_df):
        before = reference_df.copy(deep=True)
        run_analysis(reference_df)
        pd.testing.assert_frame_equal(reference_df, before)

    def test_config_variation_changes_output_deterministically(self, reference_df):
        a = run_analysis(reference_df, EngineConfig(theta_base=0.002, ratio=3.0, scales=3))
        b = run_analysis(reference_df, EngineConfig(theta_base=0.002, ratio=3.0, scales=3))
        c = run_analysis(reference_df, EngineConfig(theta_base=0.001, ratio=4.0, scales=4))
        assert self._sig(a) == self._sig(b)
        assert self._sig(a) != self._sig(c)


# ── pipeline edge cases ─────────────────────────────────────────────────────
class TestPipelineEdgeCases:
    def test_empty_frame_returns_empty_result_without_raising(self):
        res = run_analysis(pd.DataFrame())
        assert res.waves == [] and res.pivots == []
        assert res.blocked_rules, "gaps must still be reported on an empty run"
        assert any("fewer than 2 bars" in n for n in res.notes)

    def test_none_input(self):
        res = run_analysis(None)
        assert res.waves == []

    def test_single_bar(self):
        df = bars_from_path([100, 101], bars_per_leg=1).iloc[:1]
        assert run_analysis(df).waves == []

    def test_too_few_bars_for_any_pivot(self):
        df = bars_from_path([100, 100.05], bars_per_leg=3)
        res = run_analysis(df)
        assert res.waves == []
        assert not [w for w in res.waves if w.structure_type is not None]

    def test_monotonic_series_emits_no_structures(self):
        """One-directional data has no wave structure. A handful of origin
        pivots is fine; a structure would be spurious."""
        df = bars_from_path([100, 500], bars_per_leg=100)
        res = run_analysis(df)
        assert not [w for w in res.waves if w.structure_type is not None]
        assert len(res.pivots) <= 4

    def test_exhausted_scales_are_reported(self):
        df = bars_from_path([100, 103, 100, 103], bars_per_leg=6)
        res = run_analysis(df, EngineConfig(theta_base=0.001, ratio=10.0, scales=4))
        assert any("too few to form any structure" in n for n in res.notes)

    def test_blocked_rules_always_present(self, reference_df):
        res = run_analysis(reference_df)
        assert len(res.blocked_rules) >= 15
        assert res.config["lifecycle_census"]

    def test_containment_reported_not_assumed(self, reference_df):
        res = run_analysis(reference_df)
        cont = res.config.get("cross_scale_containment", {})
        assert cont
        assert all(0.0 <= v <= 1.0 for v in cont.values())


# ── API ─────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def client():
    from starlette.testclient import TestClient
    from api.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def backtest_id(client):
    r = client.post("/api/backtests", json={
        "symbol": "ES", "strategy_id": "ma_crossover", "timeframe": "5m",
        "start_date": "2024-01-01", "end_date": "2024-02-01",
        "data_source": "synthetic", "initial_capital": 100000,
        "params": {"fast": 9, "slow": 21},
    })
    assert r.status_code == 200, r.text
    return r.json()["backtest_id"]


class TestElliottWaveEndpoint:
    def test_returns_200_and_expected_top_level_shape(self, client, backtest_id):
        r = client.get(f"/api/backtests/{backtest_id}/elliott-wave")
        assert r.status_code == 200
        body = r.json()
        assert set(body) == {"engine_version", "config", "pivots", "waves",
                             "blocked_rules", "notes", "counts"}

    def test_every_wave_exposes_state_and_blocked_by(self, client, backtest_id):
        """FE-3.1: a client must be able to tell confirmed from undecidable."""
        body = client.get(f"/api/backtests/{backtest_id}/elliott-wave").json()
        assert body["waves"]
        for w in body["waves"]:
            assert w["state"] in ("gated", "undecidable", "enumerated", "measured")
            assert isinstance(w["blocked_by"], list)

    def test_blocked_rules_are_surfaced(self, client, backtest_id):
        """FE-3.2: a partial analysis must never look complete."""
        body = client.get(f"/api/backtests/{backtest_id}/elliott-wave").json()
        assert len(body["blocked_rules"]) >= 15
        for e in body["blocked_rules"]:
            assert e["rules"] and e["oq"] and e["reason"]
        assert body["counts"]["blocked_rule_ids"] >= 50

    def test_no_score_field_anywhere_in_payload(self, client, backtest_id):
        """FR-7.4. Checks FIELD NAMES, not raw substrings.

        A blocked-rule *reason* legitimately explains that the reference gives
        no probability values -- that prose must not trip the guard. What must
        never exist is a field carrying such a number.
        """
        body = client.get(f"/api/backtests/{backtest_id}/elliott-wave").json()
        banned = {"confidence", "score", "probability", "rank", "weight"}
        for w in body["waves"]:
            assert not (set(w) & banned)
            assert not (set(w["measurements"]) & banned)
        for pivot in body["pivots"]:
            assert not (set(pivot) & banned)
        assert not (set(body) & banned)
        assert not (set(body["counts"]) & banned)

    def test_pivots_preserve_no_look_ahead(self, client, backtest_id):
        body = client.get(f"/api/backtests/{backtest_id}/elliott-wave").json()
        assert body["pivots"]
        assert all(p["confirm_index"] > p["index"] for p in body["pivots"])

    def test_query_params_are_honoured(self, client, backtest_id):
        r = client.get(f"/api/backtests/{backtest_id}/elliott-wave",
                       params={"theta_base": 0.004, "ratio": 2.0, "scales": 2})
        assert r.status_code == 200
        cfg = r.json()["config"]
        assert cfg["theta_base"] == pytest.approx(0.004)
        assert cfg["ratio"] == pytest.approx(2.0)
        assert cfg["scales"] == 2

    def test_defaults_match_the_engine(self, client, backtest_id):
        """FR-1e.4: endpoint defaults and engine defaults must not drift."""
        cfg = client.get(f"/api/backtests/{backtest_id}/elliott-wave").json()["config"]
        d = EngineConfig()
        assert cfg["theta_base"] == pytest.approx(d.theta_base)
        assert cfg["ratio"] == pytest.approx(d.ratio)
        assert cfg["scales"] == d.scales

    @pytest.mark.parametrize("params", [
        {"theta_base": 0}, {"theta_base": -0.1}, {"theta_base": 1.5},
        {"ratio": 1.0}, {"ratio": 0.5},
        {"scales": 0}, {"scales": 99},
    ])
    def test_invalid_params_rejected_with_422(self, client, backtest_id, params):
        r = client.get(f"/api/backtests/{backtest_id}/elliott-wave", params=params)
        assert r.status_code == 422, f"{params} -> {r.status_code}"

    def test_unknown_backtest_id_404(self, client):
        assert client.get("/api/backtests/NOPE/elliott-wave").status_code == 404


class TestExistingApiUnchanged:
    @pytest.mark.parametrize("path", [
        "", "/trades", "/price-data", "/equity-curve", "/win-loss",
        "/monthly-returns", "/chart-patterns", "/candlestick-patterns",
    ])
    def test_existing_endpoints_still_200(self, client, backtest_id, path):
        assert client.get(f"/api/backtests/{backtest_id}{path}").status_code == 200

    def test_zigzag_endpoint_unchanged(self, client, backtest_id):
        r = client.get(f"/api/backtests/{backtest_id}/zigzag",
                       params={"dev_3": 0.003, "dev_10": 0.003})
        assert r.status_code == 200
        assert set(r.json()) == {"zigzag_10", "zigzag_3"}

    def test_report_endpoint_gained_no_elliott_params(self, client):
        """Report integration is a later phase -- the endpoint must be untouched."""
        from api.main import app
        params = app.openapi()["paths"]["/api/backtests/{backtest_id}/report"]["get"]
        names = [p["name"] for p in params.get("parameters", [])]
        assert names == ["backtest_id", "zz_dev", "zz_dev_3", "format"]

    def test_only_one_new_path_added(self):
        """The Elliott Wave phase was allowed exactly one new route.

        The count is deliberately exact so that unrelated endpoints cannot be
        smuggled in under this work. It has been raised once since, from 24 to
        25, for /api/symbols -- added so the frontend's Symbol dropdown could
        stop hardcoding ["ES","NQ","MES","CL","HG"] and report what the
        selected data source can actually serve. That is a separate, declared
        change, not Elliott Wave scope creep.
        """
        from api.main import app
        paths = set(app.openapi()["paths"])
        assert "/api/backtests/{backtest_id}/elliott-wave" in paths
        assert "/api/symbols" in paths
        # 25 before authentication; +4 for /api/auth/{login,logout,me,register};
        # +3 for OAuth sign-in -- /api/auth/oauth/providers and the
        # {name}/start + {name}/callback pair shared by Google, LinkedIn and
        # Twitter. Those three are PUBLIC, so tests/test_auth.py's PUBLIC set
        # was widened to match and test_oauth_auth.py is what holds them shut.
        # +3 for open registration -- /api/auth/signup-config (the sign-up page
        # asks whether a CAPTCHA is configured), /api/auth/verify-email (reached
        # by clicking a link in an email, so it carries no session) and
        # /api/auth/resend-verification (which DOES need one and is guarded).
        # /api/auth/oauth/complete is GONE, and the count dropped by one with
        # it. X returns no email at any scope, so that sign-up used to stop and
        # ask for a username and an address. It no longer does: an account is
        # created straight from the X identity with no address, which the
        # schema has always allowed (email is NOT NULL DEFAULT '' and its
        # unique index is partial, WHERE email != '').
        # +2 for password recovery -- /api/auth/forgot-password and
        # /api/auth/reset-password. Open registration made a forgotten password
        # unrecoverable: there is no longer an administrator who knows who
        # anybody is.
        # This count is a guard against a route appearing unnoticed, so it
        # is restated rather than removed.
        # +1 for /api/auth/forgot-username.
        assert len(paths) == 38, sorted(paths)
