"""The quote path: Schwab's several shapes in, one shape out — or nothing.

A watchlist is the one panel where a wrong number is indistinguishable from a
real one. There is no chart to sanity-check it against and no units to look
odd: 0.00 next to ES reads as a market that has crashed, not as a field this
code failed to find. So the rules under test are (1) every field name Schwab
is known to use is understood, and (2) anything not understood is ABSENT,
never zero.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.data.schwab_provider import SchwabDataProvider

client = TestClient(app)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeClient:
    """Records what was asked for and replays a canned Schwab payload."""

    def __init__(self, payload):
        self.payload = payload
        self.asked: list[str] = []

    def quotes(self, symbols, *a, **k):
        self.asked = list(symbols)
        return FakeResponse(self.payload)


def _provider_with(payload) -> tuple[SchwabDataProvider, FakeClient]:
    provider = SchwabDataProvider.__new__(SchwabDataProvider)
    client = FakeClient(payload)
    provider._client = client
    # _ensure_client() returns early once a client exists, so no auth is needed.
    return provider, client


class TestQuoteParsing:
    def test_a_futures_root_is_sent_in_schwabs_slash_form(self):
        provider, client = _provider_with(
            {"/ES": {"quote": {"lastPrice": 5600.25, "netChange": 12.5,
                               "netPercentChange": 0.22}}})
        rows = provider.quotes(["ES"])
        assert client.asked == ["/ES"], "ES must reach Schwab as /ES"
        assert rows == [{"symbol": "ES", "last": 5600.25, "change": 12.5,
                         "change_pct": 0.22, "contract": "/ES"}]

    def test_the_symbol_comes_back_as_the_caller_wrote_it(self):
        """The UI keyed its rows on "ES"; handing back "/ES" loses the match."""
        provider, _ = _provider_with({"/NQ": {"quote": {"lastPrice": 20000.0}}})
        assert provider.quotes(["NQ"])[0]["symbol"] == "NQ"

    @pytest.mark.parametrize("field,value", [
        ("lastPrice", 101.5),
        ("mark", 101.5),
        ("closePrice", 101.5),
        ("lastPriceInDouble", 101.5),
    ])
    def test_every_known_spelling_of_the_price_is_read(self, field, value):
        provider, _ = _provider_with({"$SPX": {"quote": {field: value}}})
        assert provider.quotes(["$SPX"])[0]["last"] == value

    @pytest.mark.parametrize("field", ["netPercentChange", "netPercentChangeInDouble"])
    def test_either_spelling_of_the_percent_change_is_read(self, field):
        provider, _ = _provider_with({"$VIX": {"quote": {"lastPrice": 17.4, field: -0.84}}})
        assert provider.quotes(["$VIX"])[0]["change_pct"] == -0.84

    def test_a_symbol_with_no_price_is_dropped_rather_than_zeroed(self):
        """THE POINT OF THE WHOLE MODULE. An entitlement error or an unknown
        root returns no quote block; reporting it as 0.00 would put a crashed
        market on the watchlist."""
        provider, _ = _provider_with({
            "/ES": {"quote": {"lastPrice": 5600.0}},
            "/ZZ": {"errors": [{"message": "not entitled"}]},
        })
        rows = provider.quotes(["ES", "ZZ"])
        assert [r["symbol"] for r in rows] == ["ES"]

    def test_a_futures_root_resolves_to_its_active_contract(self):
        """VERIFIED AGAINST THE LIVE API. Ask for /ES and Schwab answers under
        /ESZ26. Looking the root up directly is why this first shipped
        returning an empty watchlist against a working, authenticated
        account."""
        provider, _ = _provider_with({
            "/ESZ26": {"symbol": "/ESZ26",
                       "quote": {"lastPrice": 7667.25, "netChange": 44.25,
                                 "futurePercentChange": 0.58}},
        })
        row = provider.quotes(["ES"])[0]
        assert row["symbol"] == "ES", "the row is keyed by what the caller asked for"
        assert row["last"] == 7667.25
        assert row["contract"] == "/ESZ26", "and it says which contract that price is"

    def test_a_future_reports_its_move_as_futurePercentChange(self):
        """A FUTURE carries no netPercentChange at all -- reading only that
        name reported every future as unchanged on the day."""
        provider, _ = _provider_with({
            "/GCZ26": {"symbol": "/GCZ26",
                       "quote": {"lastPrice": 4336.1, "netChange": -51.4,
                                 "futurePercentChange": -1.17}},
        })
        assert provider.quotes(["GC"])[0]["change_pct"] == -1.17

    def test_an_index_keeps_its_own_symbol_and_netPercentChange(self):
        provider, _ = _provider_with({
            "$SPX": {"symbol": "$SPX",
                     "quote": {"lastPrice": 7551.81, "netChange": 12.0,
                               "netPercentChange": 0.16}},
        })
        row = provider.quotes(["$SPX"])[0]
        assert (row["symbol"], row["last"], row["change_pct"]) == ("$SPX", 7551.81, 0.16)

    def test_a_missing_change_is_zero_but_a_missing_price_is_not_a_row(self):
        provider, _ = _provider_with({"/GC": {"quote": {"lastPrice": 2573.1}}})
        row = provider.quotes(["GC"])[0]
        assert (row["change"], row["change_pct"]) == (0.0, 0.0)

    def test_a_string_price_is_not_accepted_as_a_number(self):
        """Schwab has returned "NaN" as text on a halted symbol."""
        provider, _ = _provider_with({"/CL": {"quote": {"lastPrice": "NaN"}}})
        assert provider.quotes(["CL"]) == []


class TestQuotesEndpoint:
    """Both branches, pinned.

    These used to assert "disconnected" and passed only on a machine with no
    Schwab tokens -- on a connected one they failed, and on ANY machine they
    reached out to the live API from inside the unit suite. The provider is
    substituted here so the endpoint's own behaviour is what is measured.
    """

    @staticmethod
    def _install(monkeypatch, provider):
        import src.data.schwab_provider as mod
        monkeypatch.setattr(mod, "SchwabDataProvider", lambda *a, **k: provider)

    def test_connected_passes_the_rows_straight_through(self, monkeypatch):
        class P:
            def is_authenticated(self): return True
            def quotes(self, symbols):
                return [{"symbol": "ES", "last": 7667.25, "change": 44.25,
                         "change_pct": 0.58, "contract": "/ESZ26"}]
        self._install(monkeypatch, P())
        body = client.get("/api/quotes?symbols=ES").json()
        assert body["connected"] is True
        assert body["quotes"][0]["symbol"] == "ES"
        assert body["quotes"][0]["last"] == 7667.25

    def test_no_tokens_says_so_instead_of_failing(self, monkeypatch):
        """With no Schwab login the panel must still render. A 500 here would
        take the whole results page down with it."""
        class P:
            def is_authenticated(self): return False
        self._install(monkeypatch, P())
        r = client.get("/api/quotes")
        assert r.status_code == 200
        body = r.json()
        assert body["connected"] is False
        assert body["quotes"] == []
        assert "Schwab" in body["reason"], "a disconnected panel has to say why"

    def test_a_dead_upstream_is_reported_not_raised(self, monkeypatch):
        class P:
            def is_authenticated(self): return True
            def quotes(self, symbols): raise RuntimeError("upstream exploded")
        self._install(monkeypatch, P())
        r = client.get("/api/quotes")
        assert r.status_code == 200, "one bad quote call must not 500 the page"
        body = r.json()
        assert body["connected"] is False and body["quotes"] == []
        assert "upstream exploded" in body["reason"]

    def test_it_never_invents_a_price(self, monkeypatch):
        """The whole reason this endpoint reports `connected` at all."""
        class P:
            def is_authenticated(self): return False
        self._install(monkeypatch, P())
        assert client.get("/api/quotes?symbols=ES,NQ").json()["quotes"] == []
