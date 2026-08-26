"""
A provider that cannot serve the requested symbol is a BAD REQUEST, not a
server defect.

The CSV corpus only holds symbols someone has actually exported -- ES here --
so picking NQ, MES or CL raised FileNotFoundError deep inside the provider and
escaped as a bare 500 "Internal Server Error". That response threw away the one
piece of information the user needed: which input to change. It stayed hidden
for a long time because the Symbol field was locked once a session loaded, so
nobody could switch symbols to trip it.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

_PARAMS = {"rsi_overbought": 94, "rsi_oversold": 2, "swing_lookback": 5}


def _replay_body(symbol: str, source: str = "external_csv") -> dict:
    return {
        "symbol": symbol, "timeframe": "5m", "data_source": source,
        "strategy_id": "rsi_divergence", "params": _PARAMS,
        "start_date": "2025-01-01", "end_date": "2025-01-07",
        "session_start": "09:30", "session_end": "16:00",
    }


class TestMissingCsvSymbol:
    @pytest.mark.parametrize("symbol", ["NQ", "MES", "CL"])
    def test_replay_returns_400_not_500(self, symbol):
        r = client.post("/api/replay", json=_replay_body(symbol))
        assert r.status_code == 400, (
            f"{symbol} with no CSV should be a 400 bad request, got {r.status_code}"
        )

    @pytest.mark.parametrize("symbol", ["NQ", "MES", "CL"])
    def test_the_message_says_what_to_change(self, symbol):
        detail = client.post("/api/replay", json=_replay_body(symbol)).json()["detail"]
        assert symbol in detail                       # which symbol failed
        assert "external_csv" in detail               # which source failed
        assert "Synthetic" in detail or "Schwab" in detail   # what to do instead

    @pytest.mark.parametrize("symbol", ["NQ", "MES", "CL"])
    def test_backtest_returns_400_not_500(self, symbol):
        body = _replay_body(symbol)
        body.pop("session_start")
        body.pop("session_end")
        r = client.post("/api/backtests", json=body)
        assert r.status_code == 400, f"got {r.status_code}: {r.text[:160]}"

    def test_the_symbol_that_does_have_data_still_works(self):
        """The guard must not have made ES collateral damage."""
        r = client.post("/api/replay", json=_replay_body("ES"))
        assert r.status_code == 200, r.text[:200]
        assert r.json()["total_bars"] > 0

    @pytest.mark.parametrize("symbol", ["ES", "NQ", "MES", "CL"])
    def test_synthetic_serves_every_symbol(self, symbol):
        """Synthetic data is generated, never read from disk, so it cannot 404."""
        r = client.post("/api/replay", json=_replay_body(symbol, source="synthetic"))
        assert r.status_code == 200, r.text[:200]


class TestUnhandledErrorsCarryAMessage:
    """
    The global handler exists so a future unhandled error is still actionable.
    A bare "Internal Server Error" body is what made this bug opaque.

    Registered on a THROWAWAY app rather than the real one: adding a route to
    the shared app leaks into the test that asserts the API surface has not
    grown, and FastAPI caches its OpenAPI schema once generated, so the leak
    outlives the test that caused it.
    """

    def test_handler_reports_type_and_message(self):
        from fastapi import FastAPI

        from api.main import _unhandled_exception

        probe_app = FastAPI()
        probe_app.add_exception_handler(Exception, _unhandled_exception)

        @probe_app.get("/boom")
        def _boom():
            raise RuntimeError("kaboom for the test")

        # raise_server_exceptions=False so the handler runs instead of the test
        # client re-raising -- what a real HTTP client would see.
        c = TestClient(probe_app, raise_server_exceptions=False)
        r = c.get("/boom")

        assert r.status_code == 500
        body = r.json()

        # The detailed message is for someone SIGNED IN. This probe app has no
        # auth, so the caller is anonymous and gets the generic form -- an
        # exception message can carry a filesystem path, a query, or a driver's
        # own text, and none of that should reach a stranger.
        assert body["detail"] == "Internal server error."
        assert body["path"] == "/boom"
        # An id ties the response to the traceback in the log, so "it broke"
        # can still be traced without the response carrying the details.
        assert len(body["error_id"]) == 12

    def test_a_signed_in_caller_still_gets_the_actionable_message(self):
        """The original reasoning stands for the operator: a missing CSV and a
        genuine defect must not look identical to the person who can fix it."""
        from fastapi import FastAPI, Request

        from api.main import _unhandled_exception

        probe_app = FastAPI()
        probe_app.add_exception_handler(Exception, _unhandled_exception)

        @probe_app.middleware("http")
        async def _pretend_signed_in(request: Request, call_next):
            request.state.user = object()      # what require_user sets
            return await call_next(request)

        @probe_app.get("/boom")
        def _boom():
            raise RuntimeError("kaboom for the test")

        c = TestClient(probe_app, raise_server_exceptions=False)
        body = c.get("/boom").json()
        assert "RuntimeError" in body["detail"]
        assert "kaboom for the test" in body["detail"]
        # The bare default is exactly what this replaces.
        assert body["detail"] != "Internal Server Error"


class TestSessionEndIsStrict:
    """
    A session ending at 17:00 must not contain a bar that closes at 17:01.

    The end comparison was inclusive, so a bar whose OPEN sat exactly on
    session_end was kept -- and that bar runs one interval past the end. It
    showed up once bars were labelled by close: a 09:30-17:00 request ended with
    a row reading 17:01. It also made RTH come out one bar long.
    """

    @staticmethod
    def _bars(session_end: str, tf: str = "1m", start: str = "09:30"):
        body = {
            "symbol": "ES", "timeframe": tf, "timeframes": [tf],
            "data_source": "external_csv", "strategy_id": "rsi_divergence",
            "params": _PARAMS,
            "start_date": "2025-01-02", "end_date": "2025-01-02",
            "session_start": start, "session_end": session_end,
        }
        r = client.post("/api/replay", json=body)
        assert r.status_code == 200, r.text[:200]
        return r.json()["total_bars"]

    def test_rth_is_390_one_minute_bars_not_391(self):
        """09:30 to 16:00 is 390 minutes, so 390 one-minute bars."""
        assert self._bars("16:00") == 390

    def test_a_session_to_1700_is_450_one_minute_bars(self):
        """09:30 to 17:00 is 450 minutes."""
        assert self._bars("17:00") == 450

    @pytest.mark.parametrize("tf,minutes", [("1m", 1), ("5m", 5), ("15m", 15), ("30m", 30)])
    def test_bar_count_is_exactly_the_span_divided_by_the_interval(self, tf, minutes):
        """No off-by-one at any interval: 09:30-17:00 is 450 minutes."""
        assert self._bars("17:00", tf=tf) == 450 // minutes

    def test_the_last_bar_closes_exactly_on_the_session_end(self):
        """The property the whole change is about."""
        from datetime import datetime, time

        from api.routers.replay import _apply_session
        from src.data.external_csv_provider import ExternalCSVProvider
        import pandas as pd

        df = ExternalCSVProvider().load(
            "ES", datetime(2025, 1, 2, 0, 0), datetime(2025, 1, 2, 23, 59), "1m")
        kept = _apply_session(df, time(9, 30), time(17, 0))
        last_open = kept.index[-1]
        last_close = last_open + pd.Timedelta(minutes=1)
        assert last_close.strftime("%H:%M") == "17:00", (
            f"last bar opens {last_open} and closes {last_close}, not on the 17:00 end"
        )


class TestOvernightSessionFetchWindow:
    """
    An overnight session begins the PREVIOUS calendar day, so fetching only the
    requested day truncates its first session.

    The bars that remain are still filtered correctly, which is what made this
    hard to see: nothing errors, nothing looks empty. But VWAP anchors on the
    first bar present -- midnight -- instead of the 18:00 session open, so every
    VWAP and band for that morning is quietly computed over the wrong window.
    """

    def test_overnight_session_reaches_back_one_day(self):
        from datetime import date, time

        from api.routers.replay import _fetch_start
        from api.schemas.replay import ReplayCreateRequest

        req = ReplayCreateRequest(
            symbol="ES", strategy_id="rsi_divergence",
            start_date=date(2026, 8, 13), end_date=date(2026, 8, 13),
            session_start=time(18, 0), session_end=time(17, 0),
        )
        assert _fetch_start(req) == date(2026, 8, 12)

    def test_a_normal_session_fetches_exactly_what_was_asked(self):
        from datetime import date, time

        from api.routers.replay import _fetch_start
        from api.schemas.replay import ReplayCreateRequest

        req = ReplayCreateRequest(
            symbol="ES", strategy_id="rsi_divergence",
            start_date=date(2026, 8, 13), end_date=date(2026, 8, 13),
            session_start=time(9, 30), session_end=time(16, 0),
        )
        assert _fetch_start(req) == date(2026, 8, 13)

    def test_a_24_hour_session_fetches_exactly_what_was_asked(self):
        from datetime import date

        from api.routers.replay import _fetch_start
        from api.schemas.replay import ReplayCreateRequest

        req = ReplayCreateRequest(
            symbol="ES", strategy_id="rsi_divergence",
            start_date=date(2026, 8, 13), end_date=date(2026, 8, 13),
            session_start=None, session_end=None,
        )
        assert _fetch_start(req) == date(2026, 8, 13)

    def test_overnight_is_detected_by_end_preceding_start(self):
        from datetime import time

        from api.routers.replay import _is_overnight

        assert _is_overnight(time(18, 0), time(17, 0))     # Globex
        assert _is_overnight(time(23, 0), time(1, 0))
        assert not _is_overnight(time(9, 30), time(16, 0))  # RTH
        assert not _is_overnight(None, None)                # 24h
        assert not _is_overnight(time(9, 30), None)

    def test_the_response_reports_the_earlier_fetch(self):
        """Silently pulling an extra day would be its own surprise."""
        body = {
            "symbol": "ES", "timeframe": "5m", "timeframes": ["5m"],
            "data_source": "synthetic", "strategy_id": "rsi_divergence",
            "params": {}, "start_date": "2025-01-02", "end_date": "2025-01-02",
            "session_start": "18:00", "session_end": "17:00",
        }
        r = client.post("/api/replay", json=body)
        assert r.status_code == 200, r.text[:200]
        assert r.json()["fetch_start_date"] == "2025-01-01"

        body["session_start"], body["session_end"] = "09:30", "16:00"
        r = client.post("/api/replay", json=body)
        assert r.status_code == 200, r.text[:200]
        assert r.json()["fetch_start_date"] is None
