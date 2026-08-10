# Elliott Wave — Architecture

**Phase 4 deliverable.** Version 1.0 (DRAFT — not approved for implementation).
Written 2026-08-09.

**Governing documents:** [ELLIOTT_WAVE_RULES.md](ELLIOTT_WAVE_RULES.md) (96 rules, 26 OQs — 5
resolved) and [ELLIOTT_WAVE_SRS.md](ELLIOTT_WAVE_SRS.md) (requirements, rev 0.5). Where this
document and the SRS disagree, **the SRS wins** and this document is the bug.

> **No production code exists.** Function signatures below are *illustrative*, included only
> where prose would be ambiguous. They are not files, and are not binding on the implementer
> beyond the contracts the SRS already fixes.

---

## 1. Scope this architecture serves

**In (the v1 core path):** pivot detection → Impulse → Leading/Ending Diagonal, Zigzag, generic
Flat, Running Flat → serialization → one API sub-resource → one dedicated tab with one dedicated
chart.

**Out (deferred, each blocked by its own Open Question):** Regular Flat and Expanded Flat
(OQ-09/OQ-10) · Triangle (OQ-12/OQ-13) · Impulse with Extension
(OQ-24) · Motive Sequence (OQ-14, not implementable) · Fibonacci **matching** (OQ-05 — ratios are
still *computed and recorded*, just never declared "matched").

---

## 2. Package layout

```
src/analysis/elliott_wave/
├── __init__.py        public surface only — re-exports, engine version, defaults
├── models.py          Pivot, Wave, LifecycleState, AnalysisResult, StructureType
├── pivots.py          directional-change detector (SRS §4a)
├── momentum.py        RSI(13) divergence evaluation for IMP-06
├── hierarchy.py       scale ladder → wave tree; parent/child linking
├── impulse.py         IMP-01…IMP-06
├── diagonal.py        Leading / Ending Diagonal (LD-*, ED-*)
├── correction.py      Zigzag, generic Flat, Running Flat
├── combination.py     Double Three, Triple Three (OQ-18 depth cap)
├── measurements.py    guideline ratio recording — computes, never matches
├── validation.py      lifecycle transitions + blocked-rule registry
└── pipeline.py        orchestration; the one correct call order
```

**12 files** (11 at v1; `combination.py` added 2026-08-10 with the OQ-18 resolution).
Every one earns its place below.

### 2.1 Modules deliberately NOT created

The Phase-4 brief listed several candidate modules. Six are **not** created, because creating an
empty or speculative module for deferred scope is how placeholder code becomes accidental
implementation.

| Suggested | Verdict | Reason |
|---|---|---|
| `motive_sequence.py` | ❌ Not created | OQ-14 — the reference never states the sequence numbers. **Not implementable at any effort.** |
| `advanced.py` | ❌ Not created *(split)* | It would have held Diagonals + Double/Triple Three. At v1 DT/TT were deferred, so a module named "advanced" would have shipped with half its scope missing. The split still stands now that DT/TT exist: `diagonal.py` and `combination.py` each name what they actually do. |
| `fibonacci.py` | ❌ Not created *(renamed)* | Fibonacci **matching** is deferred (OQ-05). A module called `fibonacci.py` would imply matching exists. `measurements.py` computes and records ratios and cannot match — the name states the actual capability. |
| `targets.py` | ❌ Not created | Wave-5 targets are IMP-F04, blocked on OQ-05 **and** OQ-07 ("inverse retracement" undefined). Nothing to build. |
| `alternates.py` | ❌ Not created | Ranking/pruning between overlapping candidates is **FR-2.4 — UNDEFINED**. v1 keeps every alternate (no selection), which is zero code. A module here would be an empty hook inviting an invented ranking rule. |
| `scoring.py` | ❌ Not created | **FR-7.4 forbids** any confidence/probability/score field — the reference states no weighting function anywhere. A `scoring.py` would be a standing invitation to violate that. Its absence is a design guarantee, not an omission. |

**`validation.py` IS created**, despite being small: it owns the lifecycle transitions (FR-5.2/5.3)
and the `blocked_rules` registry (DM-3). Concentrating "what did we *not* evaluate, and why" in one
auditable place is the mechanism that keeps ~40 blocked rules honest instead of silently absent.

---

## 3. Dependency graph

Strictly layered, acyclic. An arrow means "imports".

```
                         pipeline.py
                              │
        ┌────────────┬────────┼─────────┬──────────────┐
        ▼            ▼        ▼         ▼              ▼
   impulse.py   diagonal.py  correction.py     measurements.py
        │            │            │                    │
        │            └────┬───────┘                    │
        │                 │  (diagonal & correction     │
        │                 │   consult impulse results)  │
        └────────┬────────┴──────────┬─────────────────┘
                 ▼                   ▼
            hierarchy.py       validation.py
                 │                   │
                 ▼                   │
             pivots.py               │
                 │                   │
                 └────────┬──────────┘
                          ▼
                      models.py          momentum.py ──► models.py
                                              │
                                              ▼
                              src/analysis/indicators.py (read-only)
```

**Enforced properties:**

| # | Rule |
|---|---|
| A-1 | `models.py` imports nothing from the package. Leaf. |
| A-2 | Only `momentum.py` may import outside the package (`indicators.calc_rsi`, FR-1f.3). Every other module's external imports are limited to stdlib / pandas / numpy. |
| A-3 | **No module imports `swing_identification` or `zigzag`, or consumes their output** (FR-1f.2). Enforced by TR-7 against the resolved import graph, not a text grep. |
| A-4 | No cycles. `pipeline.py` is the only module that knows the full ordering. |
| A-5 | Nothing in the package imports from `api/` or `web/`. Analysis stays framework-free (API-2.1). |

---

## 4. Data flow

```
BacktestResults.price_data  (OHLCV DataFrame, already in api/store.py)
        │
        ├──────────────► pivots.detect_pivots(df, config)
        │                    └─► list[Pivot]  per scale  (index, confirm_index, price, kind, scale)
        │
        ├──────────────► momentum.rsi_series(df)          ── calc_rsi(close, 13), read-only
        │
        ▼
   hierarchy.build(pivots)          → Wave tree, ENUMERATED
        ▼
   impulse.classify(...)            → IMP-01…06 gates      (uses momentum for IMP-06)
        ▼
   diagonal.classify(...)           → needs impulse hosts
   correction.classify(...)         → needs 5-wave A/C
        ▼
   measurements.record(...)         → ratios recorded, never matched
        ▼
   validation.finalize(...)         → GATED / UNDECIDABLE + blocked_rules
        ▼
   AnalysisResult  ──► api/serializers.py ──► GET /api/backtests/{id}/elliott-wave ──► tab + chart
```

The engine **never re-fetches data** (FR-1a.2) and never mutates the input frame (FR-1a.3).

---

## 5. D-13 — pivot threshold defaults (calibrated, not guessed)

> ### ⚠ REVISED 2026-08-10 — rev 2 supersedes rev 1
>
> **Current values: `theta_base = 0.001` (0.10%), ladder ratio `r = 4.0`, `S = 4`.**
> Ladder: **0.10% · 0.40% · 1.60% · 6.40%**
>
> Rev 1 (0.20% / 2.5) was calibrated on **pivot density**. Building the engine and running it
> proved that ladder can never satisfy IMP-02's recursive subdivision requirement — **zero**
> impulses reached GATED above scale 1 on any dataset. §5.6 records the measurement that found
> it and the reasoning for the new values. §5.1–§5.3 below are the **superseded rev-1**
> calibration, kept visible because the density findings in them remain valid and are what §5.6
> corrects.

### 5.1 [SUPERSEDED — rev 1] Why θ_base = 0.20%

Pivot density across a θ sweep, measured on five datasets:

| θ | CL 5m | CL 1m | ES 5m | ES 1h | ES 5m synth | median leg | median confirm lag |
|---|---|---|---|---|---|---|---|
| 0.05% | 2.3 | 2.7 | 2.3 | 2.7 | 2.6 | 0.24% | 1 bar |
| 0.10% | 2.7 | 3.5 | 2.9 | 3.2 | 3.4 | 0.28% | 1 bar |
| **0.20%** | **5.6** | **8.5** | **5.6** | **5.9** | **6.4** | **0.40%** | **1–2 bars** |
| 0.30% | 9.1 | 14.4 | 9.1 | 11.5 | 11.5 | 0.53% | 3 bars |
| 0.50% | 33.3 | 55.7 | 33.3 | 39.0 | 31.2 | ~1.5–2.4% | 7–11 bars |

*(cells are bars per pivot)*

**The reasoning:**

1. **0.20% is inside the stable band; 0.50% falls off a cliff.** Between 0.30% and 0.50% pivot
   count collapses by 3–5× on every dataset. Sitting at 0.20% keeps the finest scale well clear
   of that edge, so a modest change in market character does not silently starve the engine.
2. **It generalises across instruments and timeframes.** At 0.20% the bars-per-pivot figure is
   5.6–8.5 across CL 5m, CL 1m, ES 5m, ES 1h and synthetic data. That spread is narrow enough to
   justify **one** default rather than per-symbol tuning — and it is the empirical evidence for
   FR-1e.1 (relative threshold) and FR-1e.2 (fixed, not volatility-adaptive) being adequate in v1.
3. **The resulting legs are real moves, not noise.** Median leg at 0.20% is ~0.40%, roughly 18 ES
   points — comfortably above tick noise (ES tick = 0.25).
4. **Confirmation stays responsive.** Median confirm lag is 1–2 bars, so the non-repainting delay
   (FR-1b.1) costs little. At 0.50% it rises to 7–11 bars.
5. **Enumeration cost is tractable.** ~911 pivots per 6,000 bars at the finest scale ⇒ ~900
   candidate windows per structure type per scale; roughly 7,000 windows across the whole ladder.
   Comfortably within a request budget.

**Trade-off accepted:** 0.20% is deliberately *finer* than the 0.30% the existing display ZigZag
uses. Elliott needs sub-wave detail that a display overlay does not, and the finest scale is the
one feeding IMP-02's subdivision requirement. The cost is more candidates and therefore more
alternates surfaced — acceptable, because v1 does no pruning anyway (FR-2.4).
*(The 0.30% comparison is a sanity cross-check only. No code or output from the zigzag module is
used — FR-1f.2.)*

### 5.2 [SUPERSEDED — rev 1] Why ratio r = 2.5

The decisive test is IMP-02: a leg at scale *k* must typically contain **≥5 pivots** from scale
*k−1*, or the ladder cannot express subdivision at all. Measured on 6,000-bar datasets,
θ_base = 0.20%:

| r | Ladder | Scale 1→2 nesting | Scale 2→3 nesting | Usable scales |
|---|---|---|---|---|
| 2.0 | 0.20 / 0.40 / 0.80 / 1.60% | **7–12%** ✗ | 12% | 4 |
| **2.5** | **0.20 / 0.50 / 1.25 / 3.13%** | **24–25%** | **48–52%** | **4** |
| 3.0 | 0.20 / 0.60 / 1.80 / 5.40% | 35–39% | 26–60% | 3 (4th too coarse) |
| 4.0 | 0.20 / 0.80 / 3.20 / 12.8% | **59–65%** ✓ | 17–36% | **3** ✗ |

*(nesting = share of coarse legs containing ≥5 finer pivots)*

**The trade-off is explicit:** larger *r* buys better per-level subdivision but burns through the
ladder faster. r = 4.0 has the best scale-1→2 nesting (59–65%) but exhausts by scale 3 — on the
shorter real datasets it produces a single pivot at scale 3 and nothing beyond. r = 2.0 keeps four
scales but its 7–12% nesting means the hierarchy is mostly flat, which defeats the point.

**r = 2.5 is chosen** because it is the largest ratio that still sustains four usable scales, and
its nesting improves with depth (25% → 50%) rather than collapsing.

### 5.3 Why S = 4 (unchanged in rev 2)

Four is the shallowest ladder that covers the deepest chain v1 actually needs:

```
scale 4   Zigzag                    (ZZ-01)
scale 3     └─ waves A and C are impulses      (ZZ-02)
scale 2         └─ their waves 1/3/5 are impulses  (IMP-02)
scale 1             └─ raw legs — the recursion floor
```

**The recursion floor is a real architectural decision — D-14, CONFIRMED CLOSED 2026-08-09.**
IMP-02 is recursive with no stated termination (the reference never bounds it). At **scale 1**,
waves 1/3/5 have no finer scale to subdivide into, so IMP-02 cannot be evaluated there. It
resolves to **UNDECIDABLE** (FR-5.3), never to a silent pass or fail. This is the same honesty
rule already applied to RSI warmup (FR-1b.3 / FR-3.1a.6), and it satisfies FR-2.6's termination
requirement without inventing a depth limit.

### 5.6 [CURRENT — rev 2] Why the rev-1 ladder failed, and what replaced it

**What rev 1 measured, and why it was the wrong quantity.** §5.2 chose r = 2.5 by measuring
*pivot density*: "does a coarse leg contain ≥5 finer **pivots**?" — 24–25% did, which looked
adequate. But IMP-02 does not require five finer pivots. It requires the coarse leg to contain a
finer window that **passes all six impulse gates**. Those are different questions, and the second
is roughly 15× stricter.

**The gate funnel that exposed it** (ESZZREPORT_5m, 2,000 bars, rev-1 ladder):

| Scale | Windows | pass IMP-03 | pass IMP-04 | pass IMP-05 | IMP-02 T/F/None | Kept |
|---|---|---|---|---|---|---|
| 1 | 309 | 154 | 93 | 41 | 0 / 0 / **41** | 18 (all UNDECIDABLE via D-14) |
| 2 | 59 | 28 | 22 | 14 | 0 / **14** / 0 | **0** |
| 3 | 3 | 2 | 2 | 1 | 0 / 1 / 0 | **0** |

Every scale-2 window that survived IMP-03/04/05 then failed IMP-02. The single-scale impulse pass
rate is ~6% (18 of 309); IMP-02 needs that to hold for **three** legs at once, so the joint
probability is ≈0.

**Root cause, measured directly:** at r = 2.5 the *median* coarse leg contains **2** finer pivots.
A five-leg sub-impulse needs **≥4**. The rev-1 ladder is structurally too shallow per step.

**Why raising r alone does not fix it** (θ_base held at 0.20%):

| r | 2.5 | 3.0 | 4.0 | 5.0 | 6.0 | 8.0 |
|---|---|---|---|---|---|---|
| Impulses by scale | `{1: 18}` | `{1: 18}` | `{1: 18}` | `{1: 18}` | `{1: 18}` | `{1: 18}` |
| GATED | 0 | 0 | 0 | 0 | 0 | 0 |

A bigger ratio thins the coarse scales faster than it deepens them — at r = 8 scale 2 holds only 6
pivots, one window. **Both** a finer base and a larger ratio are required:

| θ_base | r | Impulses by scale | GATED |
|---|---|---|---|
| 0.10% | 2.5 | `{1: 22}` | 0 |
| 0.10% | 3.0 | `{1: 22}` | 0 |
| **0.10%** | **4.0** | `{1: 22, 2: 1}` | **1** |
| 0.10% | 5.0 | `{1: 22, 2: 2}` | 2 |

**r = 4.0 is chosen over 5.0** because it is the smallest ratio that produces confirmed multi-scale
impulses, and §5.2's finding still holds that larger ratios exhaust the ladder faster. Rev-2
ladder: **0.10 / 0.40 / 1.60 / 6.40 %**.

**Calibrated expectation, stated so it is not mistaken for a fault:** confirmed multi-scale
impulses are *supposed* to be rare. A genuine impulse whose waves 1, 3 and 5 are themselves valid
impulses is a demanding structure. One or two per 2,000 bars is a plausible real rate, not a
number to tune upward until the output looks busy.

### 5.4 Cross-scale containment — measured, still not assumed

FR-1d.4 forbids assuming coarse-scale pivots are a subset of fine-scale pivots. Measured
containment is **99–100%** across every ratio and dataset tested.

**That does not change the requirement.** 99% is not 100%, so hierarchy construction must still
handle the non-contained pivot explicitly rather than crash or silently drop it. TR-7b requires
the rate to be *measured and reported*, not asserted — the number above is the current baseline,
not a guarantee.

### 5.5 Scale exhaustion

On short inputs a coarse scale may yield fewer than 2 pivots (observed on the 100–390 bar real
CSVs). A scale with <2 pivots contributes **no structures** and SHALL NOT raise. The result's
`blocked_rules` records that the scale was empty, so a thin analysis is visibly thin rather than
indistinguishable from "nothing found".

---

## 6. Module responsibilities

One line each, then the contract that matters.

| Module | Responsibility |
|---|---|
| `models.py` | Immutable data types and enums shared by every other module. No logic. |
| `pivots.py` | Turn OHLCV into scale-tagged, confirmation-aware pivots. |
| `momentum.py` | Answer one question: did RSI(13) diverge between two bars? |
| `hierarchy.py` | Turn pivot lists into a parent/child wave tree, per scale. |
| `impulse.py` | Apply IMP-01…IMP-06 to 5-leg windows. |
| `diagonal.py` | Apply LD-01/03 and ED-01/03 to 5-leg windows in valid host positions. |
| `correction.py` | Apply ZZ-01…04, FL-01/02 and FLU-01 to 3-leg windows. |
| `combination.py` | Apply DT-01/03/05 and TT-01/03/05; own the OQ-18 recursion depth cap. |
| `measurements.py` | Compute and record guideline ratios. **Cannot match.** |
| `validation.py` | Own lifecycle transitions and the blocked-rule registry. |
| `pipeline.py` | Run the layers in the one correct order and assemble the result. |
| `__init__.py` | Public surface: `run_analysis`, config defaults, engine version. |

### 6.1 `models.py`

Owns `Pivot`, `Wave`, `LifecycleState`, `StructureType`, `AnalysisResult`, `EngineConfig`.

- `Pivot` carries `index`, `confirm_index`, `timestamp`, `price`, `kind`, `scale` (DM-1).
- `Wave` carries `id`, `start_pivot`, `end_pivot`, `label`, `structure_type`, `scale`,
  `parent_id`, `child_ids`, `state`, `measurements`, `blocked_by` (DM-2).
- **`Wave` has no `confidence`, `score`, `probability`, `valid`, or `violated_rules` field**
  (DM-2.1, DM-2.2, FR-7.4). Their absence is enforced by TR-4.
- `LifecycleState`: `ENUMERATED → GATED → MEASURED`, plus `UNDECIDABLE`. **No INVALID/REJECTED**
  (FR-5.4) — a candidate failing an implementable gate is never constructed.

### 6.2 `pivots.py`

Implements SRS §4a in full. Single deterministic pass per scale.

```python
def detect_pivots(df, theta_base=0.002, ratio=2.5, scales=4) -> list[Pivot]: ...
```

- Emits `confirm_index > index` always; **never emits the final unconfirmed extreme** (FR-1b.3).
- Pivot price is the bar's own extreme — high for `H`, low for `L` (FR-1c.1).
- Alternation guaranteed by construction (FR-1c.2).
- **Owns no Elliott knowledge.** It knows nothing about waves, labels, or degrees. This is what
  keeps the "independent detector" claim auditable.

### 6.3 `momentum.py`

The single point of contact with shared indicator code (A-2).

```python
def has_divergence(rsi, price_idx_a, price_a, price_idx_b, price_b, direction) -> bool | None: ...
```

Returns `None` — meaning **UNDECIDABLE**, not False — when RSI is `NaN` at either bar
(FR-3.1a.6). Isolating this in its own module keeps `impulse.py` free of indicator coupling, and
means the one permitted external dependency lives in one greppable file.

### 6.4 `hierarchy.py`

Builds the wave tree from scale-tagged pivots. Handles the non-containment case explicitly
(§5.4). Assigns `scale`, never `degree` — degree naming is **OQ-17, still open** (FR-1d.3).

### 6.5 `impulse.py`

```python
def classify_impulses(tree, rsi, config) -> list[Wave]: ...
```

Gates in order, cheapest first: IMP-01 (leg count) → IMP-03 (wave 2 retrace) → IMP-04 (absolute
price distance, strict `>`) → IMP-05 (pivot-price interval overlap, closed intervals) → IMP-02
(recursive subdivision) → IMP-06 (RSI divergence, via `momentum`).

Ordering is a performance choice only; it must not change results. IMP-02 and IMP-06 are last
because they are the expensive ones, and both can yield UNDECIDABLE.

### 6.6 `diagonal.py`

LD-01/ED-01 (host position) and LD-03/ED-03 (subdivision). **LD-02/ED-02 overlap is recorded and
must never gate** — the reference is explicit that overlap "is not a condition" (FR-3.3.1), and
TR-3 exists solely to stop that regressing. Wedge geometry is **not** implemented (OQ-15).

#### 6.6.1 Sub-wave grouping — REVISED 2026-08-10 (rev 2 supersedes rev 1)

**Rev 1 (superseded).** A diagonal was only recognised when the host leg's finer subdivision
landed on *exactly* 5 legs. Measured on real data, only **18% of scale-2 legs** quantise that way
(distribution over 99 legs: 2 pivots ×26, 4 ×21, **6 ×18**, 8 ×8, 10+ ×23), and neither of the two
real impulse host legs did — they held 17 and 11 finer legs. Result: **0 diagonals on every one of
the 26 datasets**, while the code path itself was provably correct on hand-built input.

That was an artifact of the pivot ladder, not a requirement of the reference: a genuine diagonal's
five sub-waves need not align 1:1 with any detection threshold.

**Rev 2 (current).** Finer legs are *grouped* into 5 sub-waves. Grouping is constrained only by
things the reference actually states:

| Constraint | Source |
|---|---|
| The four interior boundaries alternate high/low | A 5-wave motive structure alternates direction; finer pivots already alternate, so this fixes each boundary's parity |
| **5-3-5-3-5**: sub-waves 1/3/5 each contain a five-wave structure, 2/4 contain none | LD-03 / ED-03 |
| **3-3-3-3-3**: no sub-wave contains a five-wave structure, and every sub-wave spans ≥2 finer legs | LD-03 / ED-03 + GEN-06 ("corrective waves move in three") |

**Every grouping satisfying those constraints is emitted as its own alternate.** Nothing ranks or
prunes between them — FR-2.4 is UNDEFINED, and inventing a preference would be a guess.
Enumeration is bounded at 64 accepted alternates per host (FR-2.6); truncation is **reported in
`AnalysisResult.notes`**, never silent.

**Result on real data:** diagonals **0 → 4** (four alternate groupings of one host leg on
ESZZREPORT_5m, all `3-3-3-3-3`, cap not reached). Determinism, no-look-ahead, TR-3 and the
existing 34 tests all still pass.

> **⚠ NEW OPEN QUESTION — OQ-25.** The reference constrains a diagonal's subdivision *shape* but
> never defines how detector-scale legs combine into an Elliott sub-wave. "Sub-wave 3 is a
> five-wave structure" is evaluated here as "the finer scale registers an impulse inside that
> span" — a reading, not a stated rule. Likewise the ≥2-finer-legs floor for a "three-wave"
> sub-wave is the permissive reading of a rule the reference states only as a shape. Every
> affected diagonal carries `blocked_by = ["OQ-25"]` so the caveat travels with the data.

### 6.7 `correction.py`

Zigzag (ZZ-01…04), generic Flat (FL-01/02), Running Flat (FLU-01). Regular and Expanded Flat are
**not** implemented (OQ-09/OQ-10) — `validation.py` records them as blocked so their absence is
reported rather than inferred.

### 6.7a `combination.py`

Double Three (W-X-Y) and Triple Three (W-X-Y-X-Z). Runs after `correction.py`, because DT-03/TT-03
consume the correctives it registers.

**OQ-18 - the depth cap.** `max_combination_depth = 1`, derived from the ladder rather than
picked: correctives exist only at scale 2, so a combination needs scale 3, a nested one scale 4,
and a doubly-nested one scale 5 - past the 4-scale ladder. Depth passes run shallowest-first and a
structure is never re-emitted at a deeper depth. Confirmed on real data: depth-0 combinations
appear at scale 3 and depth-1 at scale 4, exactly as the arithmetic predicts.

**DT-05/TT-05 and the scoped Fibonacci exception.** The reference states *"Wave Y can not pass
161.8% of wave W"*. That is an **inequality**, not a ratio match, so it needs no tolerance and
OQ-05 does not block it - unlike every other Fibonacci rule. The project's TR-2 guard bans
Fibonacci constants everywhere; it is narrowed to permit `161.8` **in this module only**, enforced
by a dedicated test that fails if the constant appears anywhere else, and by another asserting the
constant is used as a ceiling rather than an equality.

**OQ-26.** DT-02's "7 swing structure" contradicts DT-04 + GEN-06 (3+3+3 = 9, not 7). Swing count
is **measured and reported, never gated**, and every combination carries `blocked_by: ["OQ-26"]`.

### 6.8 `measurements.py`

Computes every guideline ratio the reference states (IMP-F01…F04, ZZ-F01/F02, …) and records the
raw value. **It exposes no comparison, tolerance, or match function at all** — the absence of the
capability is the enforcement mechanism for OQ-05, and TR-2 asserts no tolerance constant exists.

### 6.9 `validation.py`

Lifecycle transitions (FR-5.2/5.3) and the `blocked_rules` registry (DM-3). Given the set of rules
this build can evaluate, it produces the list of rule IDs that were **not** evaluated and why —
so a client can render an honest "what wasn't checked" panel (FE-3.2) instead of presenting a
partial analysis as complete.

### 6.10 `pipeline.py`

```python
def run_analysis(df, config=None) -> AnalysisResult: ...
```

The single correct ordering — corrections depend on impulses, diagonals depend on hosts. Ordering
lives here and nowhere else so it can be tested as one fact.

---

## 7. Cross-cutting guarantees

| Concern | Mechanism |
|---|---|
| **Determinism** (FR-6.1) | No randomness, no wall-clock, no I/O anywhere in the package. Wave IDs derived from `(scale, start_index, end_index, structure_type)` — stable across runs, no counters or UUIDs. |
| **No look-ahead** (FR-1b) | `confirm_index` on every pivot; `pivots.py` never emits the unconfirmed tail. TR-7a verifies by truncation. |
| **Immutability** (FR-1a.3, FR-5.5) | Input frame never mutated; later layers add waves and extend `child_ids`, never rewrite or delete an earlier layer's wave. |
| **Independence** (FR-1f.2) | No import of, or dependency on, existing swing/zigzag code. TR-7 checks the resolved import graph. |
| **No scoring** (FR-7.4) | No `scoring.py`, no score field on `Wave`. Two independent guarantees. |
| **Honest gaps** (DM-3) | `blocked_rules` on every result; `blocked_by` on every UNDECIDABLE wave. |

---

## 8. Integration points

**Backend.** One serializer function in `api/serializers.py` (additive) and one endpoint in
`api/routers/backtests.py`: `GET /api/backtests/{id}/elliott-wave`. Query params default to the
§5 values, and FR-1e.4 requires a parity test asserting the endpoint's defaults and the analysis
function's defaults cannot drift — the same class of check that already guards `zz_deviation`.

**Frontend.** One new chart component, one new tab in `ResultsPage.tsx` (four additions only:
import, query, `TabsTrigger`, `TabsContent`), additive types and one api client method.
**`CandlestickChart.tsx` is not modified, extended, parameterised, or imported** (FE-2.2).

**Untouched:** `swing_identification.py`, `zigzag.py`, `api/report/*`, all existing endpoints,
both existing test files (§12.1 of the SRS).

---

## 9. Testing architecture

| Test module | Covers |
|---|---|
| `test_ew_pivots.py` | §4a: alternation, `confirm_index > index`, unconfirmed tail withheld, **TR-7a truncation/no-look-ahead**, TR-7b containment measurement, scale exhaustion, determinism |
| `test_ew_impulse.py` | IMP-01…06 each isolated with a pass fixture and a violates-only-this fixture; **TR-2b** boundary cases; **TR-2a** IMP-06's four outcomes incl. `NaN` → UNDECIDABLE |
| `test_ew_diagonal.py` | LD/ED position + subdivision; **TR-3**: overlap never gates |
| `test_ew_correction.py` | Zigzag, generic Flat, Running Flat; Regular/Expanded absent and *reported* as blocked |
| `test_combination.py` | DT-01/03/05, TT-01/03/05, the OQ-18 depth-cap boundary, and OQ-26 swing count recorded-not-gated |
| `test_ew_guards.py` | **TR-2** no invented constants · **TR-4** no score field · **TR-7** independence via import graph · blocked-rule registry completeness |
| `test_ew_pipeline.py` | Ordering, determinism over ≥20 runs, serializer shape, live/report default parity (FR-1e.4) |

`tests/test_engine.py` and `tests/test_swing_zigzag_regression.py` must continue to pass
**unmodified** (TR-6). CI currently runs only `test_engine.py` — extending it is **D-05**, still
open.

---

## 10. Build order

Each step is independently testable; nothing later invalidates anything earlier.

1. `models.py` + `validation.py` — types and lifecycle, no logic to get wrong
2. `pivots.py` + `test_ew_pivots.py` — **the riskiest component; TR-7a must pass before anything consumes it**
3. `momentum.py` — small, isolated, unblocks IMP-06
4. `hierarchy.py`
5. `impulse.py` — the gate everything else depends on
6. `diagonal.py`, then `correction.py` — both need impulse results
7. `measurements.py`
8. `pipeline.py` + serializer + endpoint
9. Frontend tab + chart
10. Guard tests last, so they run against the finished surface

---

## 11. Constraints on implementation (Phase 5)

1. **Do not create the six modules in §2.1.** Their absence is load-bearing.
2. **Do not add a tolerance, epsilon, or buffer anywhere.** OQ-05 is open; TR-2 will catch it.
3. **Do not add a confidence/score field.** FR-7.4; TR-4 will catch it.
4. **Do not import or consume `swing_identification` / `zigzag`.** FR-1f.2; TR-7 will catch it.
5. **Do not implement wedge geometry, Regular/Expanded Flat, Triangle, DT/TT, Extension, Motive
   Sequence, or Fibonacci matching.** All blocked; register them in `blocked_rules` instead.
6. **Do not touch `CandlestickChart.tsx`.**
7. **When a rule cannot be evaluated, return UNDECIDABLE.** Never guess a pass or a fail.

---

## 12. Open items after this document

| Item | Status |
|---|---|
| D-13 threshold values | ✅ **Closed; revised 2026-08-10 to 0.10% / r=4.0 / S=4** (§5.6). Rev 1 was 0.20% / r=2.5 (§5.1–5.2, superseded) |
| D-02b, D-02c boundary confirmations | ✅ **Closed** — confirmed by decision 2026-08-09 |
| D-14 IMP-02 recursion floor | ✅ **Closed** — confirmed 2026-08-09: scale 1 ⇒ UNDECIDABLE (§5.3) |
| D-05 CI coverage | Open — the 29 swing/zigzag regression tests still aren't in CI |
| D-06 TypeScript test infrastructure | Open — none exists in this repo |
| D-07 Elliott in the exported HTML report | Open — out of v1 scope |
| D-12 UNDECIDABLE surfaced in UI or withheld | Open — now concrete (RSI warmup + scale-1 IMP-02 both produce it) |
| D-01, D-03, D-08, D-09, D-10 | Open — all govern deferred scope, none blocks v1 |

**None of the open items blocks implementation of the v1 core path.**

---

## 13. Documentation Summary

**Files created (1)** — `docs/ELLIOTT_WAVE_ARCHITECTURE.md`: package layout (11 modules), the six
modules deliberately not created and why, dependency graph with five enforced properties, data
flow, **D-13 calibration with measured evidence**, per-module responsibilities and illustrative
signatures, cross-cutting guarantees, integration points, test architecture, build order, seven
implementation constraints, open-items register.

**Files modified (2)** — `ELLIOTT_WAVE_SRS.md` and `ELLIOTT_WAVE_RULES.md`: D-13 values recorded;
D-02b/D-02c marked closed; OQ counts and revision notes updated.

**Files deleted** — none. **Production code written** — none.
