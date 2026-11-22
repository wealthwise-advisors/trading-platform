"""The economic calendar (upgrade plan, Feature 8). See src/data/econ_calendar.py."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import PROTECTED
from src.data import econ_calendar as cal

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("")
def list_events(start: date = Query(...), end: date = Query(...),
                impact: Literal["high", "medium", "low"] | None = None, user=PROTECTED):
    """Events from `start` to `end` (inclusive days, Eastern), and how each source last fared."""
    if (end - start).days > 400:
        raise HTTPException(400, "Ask for at most 400 days at a time.")
    return {"events": cal.events_between(datetime.combine(start, time(0, 0)), datetime.combine(end, time(23, 59)), impact),
            "sources": cal.status()}


class ManualEvent(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    #: Eastern wall-clock time, like every time in the app.
    at: datetime
    impact: Literal["high", "medium", "low"] = "medium"
    note: str = Field(default="", max_length=300)


@router.post("")
def add_event(ev: ManualEvent, user=PROTECTED):
    """Add an event the official schedules do not carry."""
    return {"uid": cal.add_manual(ev.title.strip(), ev.at.replace(tzinfo=None), ev.impact, ev.note)}


@router.delete("/{uid}")
def delete_event(uid: str, user=PROTECTED):
    """Delete an event added by hand. Official events are not deletable: the next refresh would
    bring them back, so pretending otherwise would only mislead."""
    if not cal.delete_manual(uid):
        raise HTTPException(404, "No event added by hand has that id.")
    return {"ok": True}
