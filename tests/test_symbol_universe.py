"""
The symbol list the UI offers must match what the backend can actually serve.

It did not. /api/symbols has been source-aware and correct for a while -- 12
symbols for external_csv, 16 for Schwab, 5 for synthetic -- and the Backtest
form consumed it, but Live Replay and Data Export each kept their own hardcoded
["ES","NQ","MES","CL"]. So gold, bitcoin and nine equities with real bundled
1-minute data were unreachable on those pages, while three of the four symbols
on offer had no CSV data at all.

These tests pin the contract in both directions: every symbol advertised for a
source is loadable from it, and every symbol with bundled data is advertised.
"""

from datetime import datetime, time

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _advertised(source: str):
    r = client.get(f"/api/symbols?data_source={source}")
    assert r.status_code == 200, r.text[:200]
    return r.json()


class TestCsvUniverse:
    def test_every_bundled_symbol_is_advertised(self):
        """Whatever sits in data/sample must be selectable."""
        from pathlib import Path

        from src.data.external_csv_provider import ExternalCSVProvider

        data_dir = Path(ExternalCSVProvider().data_dir)
        if not data_dir.exists():
            pytest.skip("no sample data directory in this checkout")

        advertised = {e["symbol"] for e in _advertised("external_csv")}
        # Derive expected symbols from the filenames the provider itself resolves.
        on_disk = set()
        for f in data_dir.glob("*.csv"):
            stem = f.stem
            for pat in ("_FULL", "FULL_"):
                if pat in stem:
                    sym = stem.replace("_FULL", "").replace("FULL_", "")
                    sym = sym.split("_")[0]
                    on_disk.add(sym)
        missing = on_disk - advertised
        assert not missing, f"bundled data not offered anywhere in the UI: {sorted(missing)}"

    def test_each_advertised_csv_symbol_actually_loads(self):
        """Advertising a symbol that cannot load is the bug this replaces."""
        from src.data.external_csv_provider import ExternalCSVProvider

        provider = ExternalCSVProvider()
        for e in _advertised("external_csv"):
            cov = e.get("coverage") or []
            assert cov, f"{e['symbol']} advertised with no coverage window"
            w = cov[-1]
            df = provider.load(
                e["symbol"],
                datetime.combine(datetime.fromisoformat(w["start"]).date(), time(0, 0)),
                datetime.combine(datetime.fromisoformat(w["end"]).date(), time(23, 59)),
                "5m",
            )
            assert df is not None and not df.empty, f"{e['symbol']} advertised but loaded empty"

    def test_every_advertised_symbol_has_real_contract_economics(self):
        """
        get_contract_spec falls back to the E-mini (0.25 tick, $50/point) for an
        unknown symbol, which would price a $130 stock as a futures contract and
        produce plausible-looking but meaningless P&L.
        """
        for source in ("external_csv", "schwab", "synthetic"):
            for e in _advertised(source):
                assert e["has_spec"], (
                    f"{e['symbol']} is offered for {source} with no contract spec; "
                    f"its P&L would use the E-mini fallback"
                )

    def test_equities_are_priced_as_shares_not_futures(self):
        from api.deps import get_contract_spec

        for sym in ("AAPL", "NVDA", "TSLA", "META"):
            spec = get_contract_spec(sym)
            assert spec["point_value"] == 1.0, f"{sym} should be $1 per point (1 share)"
            assert spec["tick_size"] == 0.01

    def test_futures_keep_their_own_economics(self):
        from api.deps import get_contract_spec

        assert get_contract_spec("ES")["point_value"] == 50.0
        assert get_contract_spec("MES")["point_value"] == 5.0
        assert get_contract_spec("CL")["point_value"] == 1000.0


class TestSourcesDifferDeliberately:
    def test_synthetic_offers_only_what_the_generator_models(self):
        """
        The generator has a starting price for five symbols. Offering NVDA would
        produce a series trading at E-mini levels, so it is excluded on purpose
        -- not an oversight to be "fixed" by widening the list.
        """
        from api.deps import BASE_PRICES

        assert {e["symbol"] for e in _advertised("synthetic")} == set(BASE_PRICES)

    def test_schwab_offers_every_configured_contract(self):
        advertised = {e["symbol"] for e in _advertised("schwab")}
        csv_syms = {e["symbol"] for e in _advertised("external_csv")}
        # Schwab streams on demand, so it is a superset of the file-backed set.
        assert csv_syms <= advertised, f"schwab missing {sorted(csv_syms - advertised)}"
        assert len(advertised) >= 16
