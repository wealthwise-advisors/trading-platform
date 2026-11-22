"""The economic calendar (upgrade plan, Feature 8): official schedules only, parsed from
saved copies of the real pages, stored, refreshed, and served."""
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from db import connection
from src.data import econ_calendar as cal

FIX = Path(__file__).parent / "fixtures" / "calendar"
BEA = (FIX / "bea_schedule.ics").read_text(encoding="utf-8")
FOMC = (FIX / "fomc_calendars.html").read_text(encoding="utf-8")


# ── parsers ─────────────────────────────────────────────────────────────────

def test_bea_ics_events_in_eastern_time_with_impact():
    ev = cal.parse_ics(BEA, source="BEA")
    assert len(ev) == 169
    gdp = next(e for e in ev if e["title"].startswith("Gross Domestic Product, 4th Quarter and Year 2024"))
    assert gdp["at"] == datetime(2025, 1, 30, 8, 30)                # 13:30 UTC in January = 08:30 ET
    assert gdp["impact"] == "high" and gdp["source"] == "BEA" and gdp["uid"]
    trade = next(e for e in ev if e["title"].startswith("U.S. International Trade in Goods and Services, November 2024"))
    assert trade["impact"] == "medium"
    assert "\\" not in gdp["title"] and "\n" not in gdp["title"]    # unescaped and unfolded


def test_summer_releases_keep_eastern_daylight_time():
    ev = cal.parse_ics(BEA, source="BEA")
    july = [e for e in ev if e["at"].month == 7 and e["at"].year == 2025]
    assert july and all(e["at"].hour == 8 and e["at"].minute == 30 for e in july if e["title"].startswith("Personal Income and Outlays"))


def test_fomc_meetings_statement_at_two_pm_on_the_last_day():
    ev = cal.parse_fomc(FOMC)
    jan26 = next(e for e in ev if e["at"].date() == datetime(2026, 1, 28).date())
    assert jan26["at"].hour == 14 and jan26["impact"] == "high" and jan26["source"] == "FOMC"
    assert "projections" in next(e for e in ev if e["at"].date() == datetime(2026, 3, 18).date())["title"].lower()


def test_a_meeting_across_two_months_ends_in_the_second():
    ev = cal.parse_fomc(FOMC)
    across = [e for e in ev if "/" in e["note"]]
    assert across and all(e["at"].day <= 2 for e in across)          # e.g. Apr/May 30-1 -> May 1


def test_notation_votes_are_not_meetings():
    assert not any("notation" in e["title"].lower() for e in cal.parse_fomc(FOMC))


def test_every_fomc_year_on_the_page():
    years = {e["at"].year for e in cal.parse_fomc(FOMC)}
    assert {2021, 2025, 2026, 2027} <= years


def test_a_page_that_changed_shape_fails_loudly():
    with pytest.raises(ValueError, match="no meetings"):
        cal.parse_fomc("<html>redesigned</html>")
    with pytest.raises(ValueError, match="no events"):
        cal.parse_ics("BEGIN:VCALENDAR\nEND:VCALENDAR", source="BEA")


# ── store and refresh ───────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "cal.db")
    return tmp_path


def test_refresh_stores_each_source_and_keeps_the_last_good_data_on_failure(db):
    fetch = {"BEA": lambda: BEA, "FOMC": lambda: FOMC}
    status = cal.refresh(fetchers=fetch)
    assert status["BEA"]["ok"] and status["FOMC"]["ok"]
    n = len(cal.events_between(datetime(2020, 1, 1), datetime(2030, 1, 1)))

    def broken():
        raise ValueError("page changed")
    status = cal.refresh(fetchers={"BEA": broken, "FOMC": lambda: FOMC})
    assert not status["BEA"]["ok"] and "page changed" in status["BEA"]["error"]
    assert len(cal.events_between(datetime(2020, 1, 1), datetime(2030, 1, 1))) == n   # BEA kept


def test_bls_needs_a_contact_address(db, monkeypatch):
    monkeypatch.setattr(cal, "bls_contact", lambda: None)
    status = cal.refresh(fetchers=cal.default_fetchers())
    assert status["BLS"]["ok"] is False and "contact" in status["BLS"]["error"]


def test_filter_by_impact_and_range(db):
    cal.refresh(fetchers={"BEA": lambda: BEA, "FOMC": lambda: FOMC})
    high = cal.events_between(datetime(2026, 1, 1), datetime(2026, 12, 31), impact="high")
    assert high and all(e["impact"] == "high" for e in high)
    assert all(datetime(2026, 1, 1) <= datetime.fromisoformat(e["at"]) <= datetime(2026, 12, 31) for e in high)


# ── API ─────────────────────────────────────────────────────────────────────

def test_api_lists_events_and_adds_and_deletes_manual_ones(db):
    cal.refresh(fetchers={"FOMC": lambda: FOMC})
    with TestClient(app) as c:
        r = c.get("/api/calendar", params={"start": "2026-01-01", "end": "2026-12-31"})
        assert r.status_code == 200 and len(r.json()["events"]) >= 8
        assert "FOMC" in r.json()["sources"]
        add = c.post("/api/calendar", json={"title": "Treasury refunding", "at": "2026-11-25T08:30:00", "impact": "medium"})
        assert add.status_code == 200
        uid = add.json()["uid"]
        got = c.get("/api/calendar", params={"start": "2026-11-25", "end": "2026-11-25"}).json()["events"]
        assert any(e["uid"] == uid and e["source"] == "manual" for e in got)
        assert c.delete(f"/api/calendar/{uid}").status_code == 200
        assert c.delete("/api/calendar/not-manual").status_code == 404


def test_api_refuses_bad_input(db):
    with TestClient(app) as c:
        assert c.post("/api/calendar", json={"title": "", "at": "2026-11-25T08:30:00"}).status_code == 422
        assert c.post("/api/calendar", json={"title": "x", "at": "2026-11-25T08:30:00", "impact": "huge"}).status_code == 422


def test_only_national_gdp_and_pce_are_high_impact():
    assert cal.impact_of("GDP (Second Estimate) and Corporate Profits, 3rd Quarter 2026") == "high"
    assert cal.impact_of("Gross Domestic Product, 4th Quarter and Year 2024 (Advance Estimate)") == "high"
    assert cal.impact_of("Personal Income and Outlays, October 2026") == "high"
    assert cal.impact_of("GDP by County and Personal Income by County, 2025") == "low"
    assert cal.impact_of("Gross Domestic Product by State and Personal Income by State, 2nd Quarter 2025") == "low"
