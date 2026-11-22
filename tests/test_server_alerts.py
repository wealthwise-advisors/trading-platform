"""Server-side price alerts (upgrade plan, Feature 4).

The alerts are the ones the chart's Alert button already makes; since Phase 1 they sit in
the server's settings document. The server checks them against the live price, records each
firing once, and the app reports events it has not shown yet -- including ones that fired
while no browser was open.
"""
import json

import pytest
from fastapi.testclient import TestClient

from api import alerts
from api.main import app
from db import connection
from db import users as repo


def alert(id_, symbol, price, direction, note=""):
    return {"id": id_, "symbol": symbol, "price": price, "direction": direction,
            "note": note, "createdAt": "2026-11-22T10:00:00Z"}


# ── the rule ────────────────────────────────────────────────────────────────

def test_above_fires_at_or_over_the_level_below_at_or_under():
    a = [alert("1", "ES", 6900, "above"), alert("2", "ES", 6800, "below"), alert("3", "ES", 7000, "above")]
    got = alerts.due(a, {"ES": 6900.0}, fired=set())
    assert [x["id"] for x, _ in got] == ["1"]
    got = alerts.due(a, {"ES": 6800.0}, fired=set())
    assert [x["id"] for x, _ in got] == ["2"]


def test_fired_alerts_and_symbols_without_a_price_are_skipped():
    a = [alert("1", "ES", 6900, "above"), alert("2", "NQ", 1, "above")]
    assert alerts.due(a, {"ES": 7000.0}, fired={"1"}) == []


def test_bad_entries_are_ignored_not_fatal():
    a = [{"id": "x"}, "junk", alert("1", "ES", "high", "above"), alert("2", "ES", 1, "sideways"),
         alert("3", "es", 1, "above")]
    assert [x["id"] for x, _ in alerts.due(a, {"ES": 5.0}, fired=set())] == ["3"]


# ── one pass: settings -> prices -> events ──────────────────────────────────

@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "alerts.db")
    uid = repo.create_user("owner", "!", full_name="Owner", email="o@example.com", country="IN",
                           has_password=False)
    return uid


def save_alerts(uid, lst):
    repo.put_settings(uid, json.dumps({"priceAlerts": json.dumps(lst)}),
                      (repo.get_settings(uid) or {"version": 0})["version"])


def test_a_pass_records_each_firing_once_even_across_restarts(db):
    save_alerts(db, [alert("a1", "ES", 6900, "above", "breakout")])
    assert alerts.check_once(db, prices=lambda syms: {"ES": 6950.0}) == 1
    assert alerts.check_once(db, prices=lambda syms: {"ES": 6960.0}) == 0      # already fired
    ev = repo.alert_events(db, after=0)
    assert len(ev) == 1 and ev[0]["alert_id"] == "a1" and ev[0]["price"] == 6950.0
    assert ev[0]["symbol"] == "ES" and ev[0]["level"] == 6900 and ev[0]["note"] == "breakout"
    assert ev[0]["fired_at"][-6:] in ("-05:00", "-04:00")          # Eastern, whatever the server's clock


def test_only_the_symbols_with_alerts_are_priced(db):
    save_alerts(db, [alert("a1", "ES", 1, "above"), alert("a2", "NQ", 1, "below")])
    asked = []
    alerts.check_once(db, prices=lambda syms: asked.append(sorted(syms)) or {})
    assert asked == [["ES", "NQ"]]


def test_no_alerts_no_price_request(db):
    asked = []
    assert alerts.check_once(db, prices=lambda syms: asked.append(syms) or {}) == 0
    assert asked == []


def test_a_price_source_failure_is_not_fatal(db):
    save_alerts(db, [alert("a1", "ES", 1, "above")])
    def boom(syms):
        raise RuntimeError("Schwab tokens are missing or expired.")
    assert alerts.check_once(db, prices=boom) == 0


# ── the app reads events ────────────────────────────────────────────────────

def test_events_after_an_id(db):
    save_alerts(db, [alert("a1", "ES", 1, "above"), alert("a2", "ES", 99999, "below")])
    alerts.check_once(db, prices=lambda s: {"ES": 5.0})
    with TestClient(app) as c:
        everything = c.get("/api/alerts/events").json()
        assert [e["alert_id"] for e in everything] == ["a1", "a2"]
        assert c.get(f"/api/alerts/events?after={everything[0]['id']}").json() == everything[1:]


def test_a_long_history_still_returns_the_newest(db):
    for i in range(205):
        repo.record_alert_event(db, alert(f"a{i}", "ES", 1, "above"), 2.0)
    got = repo.alert_events(db, after=0)
    assert len(got) == 200 and got[-1]["alert_id"] == "a204" and got[0]["id"] < got[-1]["id"]
