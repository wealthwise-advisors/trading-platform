"""The economic calendar (upgrade plan, Feature 8): official US release schedules only.

  BEA    www.bea.gov/news/schedule/ics -- GDP, Personal Income and Outlays (PCE), trade
  FOMC   www.federalreserve.gov/monetarypolicy/fomccalendars.htm -- the statement at
         2:00 PM ET on each meeting's last day ("*" meetings also publish projections)
  BLS    www.bls.gov/schedule/news_release/bls.ics -- CPI, the jobs report, PPI. BLS refuses
         automated requests that do not identify themselves, so it is fetched only when
         config/credentials.yaml (git-ignored) sets calendar.bls_contact (an address BLS may write to);
         without one the calendar says BLS was skipped and why.
  manual anything else, added by hand

Dates and times only: official schedules carry no forecasts or actual values. Times are
stored as Eastern wall-clock, like every bar in the app. A source that fails, or whose
page changed shape (a parser that finds nothing raises), keeps its last good events.
"""
from __future__ import annotations

import html
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from db.connection import connect

log = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")
USER_AGENT = "AutoTrader economic calendar"

BEA_URL = "https://www.bea.gov/news/schedule/ics"
FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
BLS_URL = "https://www.bls.gov/schedule/news_release/bls.ics"

#: What moves index futures. Matched against the start of the release's title.
#: National GDP only: "GDP by County" and "Gross Domestic Product by State" share the
#: words and move nothing.
HIGH = ("Gross Domestic Product,", "GDP (", "Personal Income and Outlays", "Consumer Price Index",
        "Employment Situation", "Producer Price Index", "FOMC")
MEDIUM = ("U.S. International Trade in Goods and Services", "Job Openings", "Real Earnings",
          "Employment Cost Index", "Productivity and Costs", "Import and Export Price")


def impact_of(title: str) -> str:
    if title.startswith(HIGH):
        return "high"
    if title.startswith(MEDIUM):
        return "medium"
    return "low"


# ── parsers ─────────────────────────────────────────────────────────────────

def parse_ics(text: str, source: str) -> list[dict]:
    """RFC 5545 VEVENTs: unfolded lines, unescaped text, DTSTART in UTC (Z), with a TZID,
    or a bare date. Everything else in the file is ignored."""
    lines = re.sub(r"\r?\n[ \t]", "", text).splitlines()              # unfold
    events, cur = [], None
    for line in lines:
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT" and cur is not None:
            if "SUMMARY" in cur and "DTSTART" in cur:
                title = cur["SUMMARY"]
                events.append({"source": source, "uid": cur.get("UID") or f"{source}-{cur['DTSTART'][1]}-{title}",
                               "title": title, "at": cur["DTSTART"][0], "impact": impact_of(title), "note": ""})
            cur = None
        elif cur is not None and ":" in line:
            key, val = line.split(":", 1)
            name, *params = key.split(";")
            if name == "SUMMARY":
                cur["SUMMARY"] = re.sub(r"\\([,;\\])", r"\1", val).replace("\\n", " ").strip()
            elif name == "UID":
                cur["UID"] = val.strip()
            elif name == "DTSTART":
                cur["DTSTART"] = (_ics_time(val.strip(), params), val)
    if not events:
        raise ValueError(f"{source}: no events found -- the feed may have changed shape")
    return events


#: Zone names feeds use that are not IANA names (BLS writes TZID=US-Eastern).
_TZ_ALIASES = {"US-Eastern": "America/New_York", "US/Eastern": "America/New_York"}


def _ics_time(val: str, params: list[str]) -> datetime:
    if len(val) == 8:                                                   # a whole day
        return datetime.strptime(val, "%Y%m%d")
    t = datetime.strptime(val.rstrip("Z"), "%Y%m%dT%H%M%S")
    tz = next((p.split("=", 1)[1] for p in params if p.startswith("TZID=")), None)
    if val.endswith("Z"):
        return t.replace(tzinfo=timezone.utc).astimezone(ET).replace(tzinfo=None)
    if tz:
        zone = _TZ_ALIASES.get(tz, tz)
        return t.replace(tzinfo=ZoneInfo(zone)).astimezone(ET).replace(tzinfo=None)
    return t


_MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July",
                                       "August", "September", "October", "November", "December"], 1)}
_SHORT = {m[:3]: i for m, i in _MONTHS.items()}


def parse_fomc(page: str) -> list[dict]:
    """Each scheduled meeting on the Fed's calendars page: the statement at 2:00 PM ET on
    its last day. Notation votes are not meetings and are skipped."""
    events = []
    years = [(m.start(), int(m.group(1))) for m in re.finditer(r">\s*(\d{4}) FOMC Meetings", page)]
    for i, (pos, year) in enumerate(years):
        block = page[pos:years[i + 1][0] if i + 1 < len(years) else len(page)]
        months = re.findall(r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>', block)
        days = re.findall(r'fomc-meeting__date[^>]*>([^<]+)<', block)
        for mon, day in zip(months, days):
            mon, day = html.unescape(mon).strip(), html.unescape(day).strip()
            if "notation" in day.lower() or "unscheduled" in day.lower():
                continue
            last_month = mon.split("/")[-1].strip()
            m = _MONTHS.get(last_month) or _SHORT.get(last_month[:3])
            d = re.findall(r"\d+", day)
            if not m or not d:
                continue
            projections = "*" in day
            events.append({
                "source": "FOMC", "uid": f"FOMC-{year}-{m:02d}-{int(d[-1]):02d}",
                "title": "FOMC statement" + (" and economic projections" if projections else ""),
                "at": datetime(year, m, int(d[-1]), 14, 0), "impact": "high",
                "note": f"Meeting {mon} {day.rstrip('*')}, {year}",
            })
    if not events:
        raise ValueError("FOMC: no meetings found -- the Fed's calendar page may have changed shape")
    return events


# ── fetching ────────────────────────────────────────────────────────────────

def bls_contact() -> str | None:
    try:
        from api.deps import get_config
        return (get_config().get("calendar") or {}).get("bls_contact") or None
    except Exception:
        return None


def _get(url: str, ua: str = USER_AGENT) -> str:
    import requests
    r = requests.get(url, headers={"User-Agent": ua}, timeout=30)
    r.raise_for_status()
    return r.text


def default_fetchers() -> dict[str, Callable[[], str]]:
    def bls():
        contact = bls_contact()
        if not contact:
            raise ValueError("skipped: BLS requires a contact address; set calendar.bls_contact in "
                             "config/credentials.yaml to include CPI, the jobs report and PPI")
        return _get(BLS_URL, f"{USER_AGENT} ({contact})")
    return {"BEA": lambda: _get(BEA_URL), "FOMC": lambda: _get(FOMC_URL), "BLS": bls}


_PARSE = {"BEA": lambda t: parse_ics(t, "BEA"), "BLS": lambda t: parse_ics(t, "BLS"), "FOMC": parse_fomc}
_status: dict[str, dict] = {}


def refresh(fetchers: dict[str, Callable[[], str]] | None = None) -> dict[str, dict]:
    """Fetch and store every source. A source that fails keeps its last good events."""
    now = datetime.now(ET).replace(tzinfo=None).isoformat(timespec="seconds")
    for source, fetch in (fetchers or default_fetchers()).items():
        try:
            events = _PARSE[source](fetch())
            _store(source, events, now)
            _status[source] = {"ok": True, "events": len(events), "fetched_at": now, "error": None}
        except Exception as exc:
            log.warning("calendar %s: %s", source, exc)
            _status[source] = {"ok": False, "events": 0, "fetched_at": now, "error": str(exc)[:300]}
    return dict(_status)


def status() -> dict[str, dict]:
    return dict(_status)


def _store(source: str, events: list[dict], fetched_at: str) -> None:
    conn = connect()
    try:
        with conn:
            conn.execute("DELETE FROM econ_events WHERE source = ?", (source,))
            conn.executemany(
                "INSERT OR REPLACE INTO econ_events (uid, source, title, event_time, impact, note, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(e["uid"], source, e["title"], e["at"].isoformat(timespec="minutes"), e["impact"],
                  e.get("note", ""), fetched_at) for e in events])
    finally:
        conn.close()


def events_between(start: datetime, end: datetime, impact: str | None = None) -> list[dict]:
    conn = connect()
    try:
        sql = "SELECT uid, source, title, event_time AS at, impact, note FROM econ_events WHERE event_time BETWEEN ? AND ?"
        args: list = [start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes")]
        if impact:
            sql += " AND impact = ?"
            args.append(impact)
        return [dict(r) for r in conn.execute(sql + " ORDER BY event_time", args)]
    finally:
        conn.close()


def add_manual(title: str, at: datetime, impact: str, note: str = "") -> str:
    uid = f"manual-{uuid.uuid4().hex[:10]}"
    conn = connect()
    try:
        with conn:
            conn.execute("INSERT INTO econ_events (uid, source, title, event_time, impact, note, fetched_at) "
                         "VALUES (?, 'manual', ?, ?, ?, ?, ?)",
                         (uid, title, at.isoformat(timespec="minutes"), impact, note,
                          datetime.now(ET).replace(tzinfo=None).isoformat(timespec="seconds")))
        return uid
    finally:
        conn.close()


def delete_manual(uid: str) -> bool:
    conn = connect()
    try:
        with conn:
            return conn.execute("DELETE FROM econ_events WHERE uid = ? AND source = 'manual'", (uid,)).rowcount == 1
    finally:
        conn.close()


def start_daily_refresh() -> None:
    """Refresh at start-up and every 24 h, in a daemon thread. Off when
    AUTOTRADER_STREAM=0 (the test suites): nothing in a test run reaches the internet."""
    import os
    import threading
    import time
    if os.environ.get("AUTOTRADER_STREAM", "1") == "0":
        return

    def loop():
        while True:
            refresh()
            time.sleep(24 * 3600)
    threading.Thread(target=loop, name="econ-calendar", daemon=True).start()
