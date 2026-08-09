"""Pydantic response models for the Elliott Wave endpoint.

Two shape decisions are load-bearing and mirror the SRS:

* There is NO ``confidence`` / ``score`` / ``probability`` field anywhere
  (FR-7.4). The reference states no weighting function, so there is nothing
  truthful to put in one.
* ``state`` and ``blocked_by`` are on every record, and ``blocked_rules`` is on
  the response, because FE-3 requires a partial analysis to never look
  complete. A client must be able to tell a confirmed structure from one whose
  acceptance depends on an unresolved Open Question.
"""

from typing import Optional

from pydantic import BaseModel


class PivotRecord(BaseModel):
    """One detected pivot.

    ``confirm_index`` is always greater than ``index``: a consumer standing at
    bar t may only use pivots whose confirm_index <= t (SRS FR-1b.2). Both are
    exposed so the client can respect that rather than re-derive it.
    """

    index: int
    confirm_index: int
    t: str
    price: float
    kind: str          # "H" | "L"
    scale: int         # ladder index, NOT an Elliott degree (OQ-17 open)


class WaveRecord(BaseModel):
    id: str
    scale: int
    state: str                      # gated | undecidable | enumerated | measured
    label: Optional[str] = None     # "1".."5", "A".."C" -- None for a structure
    structure_type: Optional[str] = None
    direction: Optional[str] = None
    start_t: str
    start_price: float
    end_t: str
    end_price: float
    parent_id: Optional[str] = None
    child_ids: list[str] = []
    measurements: dict = {}         # raw guideline ratios; never "matched"
    blocked_by: list[str] = []      # OQ / rule ids that prevented a decision


class BlockedRuleRecord(BaseModel):
    rules: list[str]
    oq: str
    reason: str


class ElliottWaveResponse(BaseModel):
    engine_version: str
    config: dict
    pivots: list[PivotRecord]
    waves: list[WaveRecord]
    blocked_rules: list[BlockedRuleRecord]
    notes: list[str]
    counts: dict
