# Elliott Wave — Implementation Record

**Final documentation for the from-scratch Elliott Wave rebuild.**
Written 2026-08-10. Branch `feature/elliott-wave-rebuild` (local, unpushed).

**Sole rule source:** <https://elliottwave-forecast.com/elliott-wave-theory/>
**Companion documents:** [ELLIOTT_WAVE_RULES.md](ELLIOTT_WAVE_RULES.md) (96 rules, 27 Open
Questions) · [ELLIOTT_WAVE_SRS.md](ELLIOTT_WAVE_SRS.md) (requirements) ·
[ELLIOTT_WAVE_ARCHITECTURE.md](ELLIOTT_WAVE_ARCHITECTURE.md) (module design, D-13 calibration)

> **Read this first.** This engine is deliberately incomplete, and its incompleteness is
> reported at runtime rather than hidden. Roughly half the reference's rules cannot be
> implemented because the source does not define them precisely enough. **22 of 27 Open
> Questions remain unresolved.** Every affected rule is registered in
> `AnalysisResult.blocked_rules` and surfaced in both the UI and the exported report. Nothing
> here fabricates a value the reference does not supply.
>
> **V2 Step 5 addendum — 2026-08-10.** **OQ-12/OQ-13 investigated and left open.** A 13th
> module, `triangle.py`, measures Triangle candidates and classifies nothing — no `TRIANGLE`
> structure type. TRI-01/TRI-03 turned out to be **exact and selective (8.4%, 328 of 3,912
> windows)**, not the "near-vacuous" gate previously recorded — corrected — but they still
> cannot gate: the strict reading finds 1 candidate in 3,912 (so OQ-25 is inherited), TRI-02's
> host rule is guideline-tier and matches 6 of 328, and **21% of candidates are plainly
> trending**, contradicting the reference's own definition of the word. Suite is **344 tests**.
>
> **V2 Step 4 addendum — 2026-08-10.** **OQ-05 investigated and left open. No behaviour
> change.** Fibonacci matching stays uncomputed on three independent grounds: the reference
> states no tolerance anywhere *and* demonstrably writes an explicit range where it means one
> (3 rules do), so the discrete lists are discrete by intent; real ratios show no clustering
> on the stated values once the data's own density is controlled for (**0 of 5** families
> significant); and the width any tolerance would need varies **11×** across families, ruling
> out a single global ±%. One attribution bug fixed: **OQ-05 blocks 14 rules, not 16** —
> FLE-F02 and FLU-F02 state ranges and are blocked by OQ-11, while IMP-F04 carries both OQ-05
> and OQ-07. Suite is **314 tests**.
>
> **V2 Step 3 addendum — 2026-08-10.** **OQ-09/OQ-10 investigated and left open.** No cliff
> in 356 real flats in either dimension, so Regular and Expanded stay unseparated and the
> quantities are measured instead (`measurements.record_flat_subtype`). **A stale claim was
> corrected**: Regular and Expanded are NOT separated only by slightly-vs-substantially —
> **FLE-01** (*wave B terminates beyond the starting level of wave A*) is a second, *exact*
> discriminator that needs no threshold and was simply never actioned; 33.5% of real flats
> satisfy it. It is measured but does not gate, pending the new **OQ-27**: 29 of 34 structures
> satisfying FLE-01 also satisfy FLU-01, and the reference states no precedence between
> Expanded and Running. Suite is **312 tests**.
>
> **V2 Step 2 addendum — 2026-08-10.** **OQ-24 investigated and deliberately left open.**
> Extension is now MEASURED but never classified: `measurements.record_extension` records
> EXT-01/EXT-02 quantities on every 5-leg motive structure, all tagged `blocked_by: ["OQ-24"]`,
> and no `IMPULSE_WITH_EXTENSION` type is ever emitted. Data derivation was attempted with the
> D-13 method and **failed to yield a defensible threshold** — five formulations over 1,142
> impulses all decay smoothly with no cliff. Confirmed **independent of OQ-05**. §5.1's
> "zero scale-≥2 impulses" claim is corrected below. Suite is **286 tests**.
>
> **V2 Step 1 addendum — 2026-08-10.** Double Three and Triple Three are now implemented in a
> 12th module, `combination.py`, resolving **OQ-18** with a recursion depth cap of 1 derived from
> the pivot ladder's expressive limit. Two rules the Phase-2 extraction missed — **DT-05/TT-05**,
> the 161.8% wave-Y ceiling — are extracted and enforced. A new unresolved **OQ-26** records the
> reference's 7-vs-9 swing-count contradiction; swing count is measured, never gated. Suite is
> **256 tests**. The commit table, file counts and per-commit test counts in §1, §2 and §9 below
> describe the **v1 branch state** and are left as the historical record.

---

## 1. What was built

A ground-up replacement for a previously deleted Elliott Wave implementation. None of the old
code or architecture was reused — the removal landed first, as its own commit, and the rebuild
started from an empty directory.

**Branch: 9 commits, 115 files changed, +6,693 / −24,787 lines** (23 added, 60 deleted,
32 modified).

| # | Commit | Scope |
|---|---|---|
| `6bb2c82` | Pre-existing v1.0.0 work | Baseline, **not authored by this rebuild** |
| `c74fcf1` | Removal | 70 files, −24,218 lines |
| `6c785cf` | Core engine | 11 modules + 3 governing docs |
| `6d1d09d` | API | endpoint + schema + serializer |
| `67fa8b4` | Frontend | dedicated tab + chart |
| `7768ede` | Tests | 186 tests |
| `c48ceb3` | CI | full suite on push (D-05) |
| `0b9ef29` | Report integration | timeout fix + report section |
| `d1404b9` | Chart labelling | hierarchical nested labels |

---

## 2. Files

### 2.1 Created (23)

**Engine — `src/analysis/elliott_wave/` (11 modules, 1,570 lines)**

| Module | Lines | Responsibility |
|---|---:|---|
| `__init__.py` | 83 | Public surface: `run_analysis`, config defaults, engine version |
| `models.py` | 167 | Immutable types: `Pivot`, `Wave`, `LifecycleState`, `StructureType`, `EngineConfig`, `AnalysisResult`. No logic |
| `pivots.py` | 154 | Threshold-based directional-change detector; multi-scale ladder; confirmation-aware |
| `momentum.py` | 92 | RSI(13) divergence for IMP-06. The only module allowed to import shared analysis code |
| `hierarchy.py` | 100 | Leg windows, `SpanIndex` containment lookups, cross-scale containment measurement |
| `impulse.py` | 231 | IMP-01 … IMP-06 |
| `diagonal.py` | 238 | Leading / Ending Diagonal, incl. sub-wave grouping enumeration |
| `correction.py` | 180 | Zigzag, generic Flat, Running Flat |
| `measurements.py` | 95 | Records guideline ratios. Exposes **no** comparison or match function |
| `validation.py` | 120 | Blocked-rule registry and lifecycle census |
| `pipeline.py` | 110 | The one correct call order |

**API** — `api/schemas/elliott_wave.py`
**Docs** — `ELLIOTT_WAVE_RULES.md`, `ELLIOTT_WAVE_SRS.md`, `ELLIOTT_WAVE_ARCHITECTURE.md`, and this file
**Tests** — `tests/test_elliott_wave/` (6 files, 186 tests) + `tests/test_swing_zigzag_regression.py` (pre-existing, brought under version control)

### 2.2 Modified

`api/serializers.py` (+1 function) · `api/routers/backtests.py` (+1 endpoint) ·
`api/report/report.py` (perf fix + report section) ·
`web/src/components/charts/ElliottWaveChart.tsx` (new component, then hierarchical labelling) ·
`web/src/lib/types.ts` (+6 interfaces) · `web/src/lib/api.ts` (+1 method) ·
`web/src/features/backtest/ResultsPage.tsx` (4 additions) ·
`.github/workflows/ci.yml` (D-05) · `CLAUDE.md`, `CHANGELOG.md`, `Dockerfile`

### 2.3 Deleted (60) — the previous implementation

9 `src/analysis/*.py` engine modules · `api/routers/elliott_wave.py`, `api/report/wave_layout.py` ·
`benchmark/` (17) · `validation/` (17) · `cli/` (2, the `elliott` CLI) · `tests/elliott/` (10) ·
2 web components · `docs/ELLIOTT_WAVE_NOTATION.md`

### 2.4 Untouched by design

`src/analysis/swing_identification.py` and `src/analysis/zigzag.py` — neither modified **nor
consumed** (FR-1f.2, OQ-21). `CandlestickChart.tsx` — Price & Trades remains a plain Price &
Trades chart. `api/report/charts.py` — its chart builders have zero call sites; adding to it
would be dead code.

---

## 3. Structures

### 3.1 Implemented

| Structure | Gates |
|---|---|
| **Impulse** | IMP-01 (5 legs) · IMP-02 (waves 1/3/5 subdivide) · IMP-03 (wave 2 no full retrace) · IMP-04 (wave 3 not shortest) · IMP-05 (wave 4 vs wave 1 territory) · IMP-06 (RSI(13) divergence) |
| **Leading Diagonal** | LD-01 (host = impulse wave 1) · LD-03 (5-3-5-3-5 or 3-3-3-3-3) |
| **Ending Diagonal** | ED-01 (host = impulse wave 5) · ED-03 (same subdivision set) |
| **Zigzag** | ZZ-01 (3 legs) · ZZ-02 (A and C are 5-wave) · ZZ-03 (B permissive) · ZZ-04 (5-3-5) |
| **Flat (generic)** | FL-01 (3-3-5) · FL-02 (wave A is 3, not 5) |
| **Running Flat** | FLU-01 (wave C falls short of wave A's end) |
| **Double Three** | DT-01 (3 legs W-X-Y) · DT-03 (W/Y hold a permitted component) · DT-04 (X permissive) · DT-05 (wave Y ≤ 161.8% of wave W) |
| **Triple Three** | TT-01 (5 legs W-X-Y-X-Z) · TT-03 (W/Y/Z hold components) · TT-04 (X permissive) · TT-05 (wave **Y** ≤ 161.8% of wave W) |

**LD-02 / ED-02 overlap is measured and recorded but NEVER gates** — the reference states
outright that overlap "is not a condition". Guarded by a dedicated test (TR-3).

### 3.2 Not implemented, and why

| Structure / feature | Blocked by | Reason |
|---|---|---|
| **Regular Flat** | OQ-09, OQ-10 | "Wave B terminates **near** the start of wave A", "wave C **slightly** beyond" — neither quantified; the paired ratio is a single point (exactly 90%) with no tolerance |
| **Expanded Flat** *(wave C half)* | OQ-10, OQ-27 | Needs "**substantially** beyond", unquantified and with no cliff in 356 real flats. **Corrected 2026-08-10:** this row previously said Regular and Expanded are separated *only* by slightly-vs-substantially. They are not — **FLE-01** (wave B beyond wave A start) is a second, *exact* discriminator, now measured. It does not gate pending **OQ-27** (29 of 34 structures satisfying it also satisfy FLU-01) |
| **Triangle** *(classification only; candidates measured)* | OQ-12, OQ-13 | No Fibonacci ratios, no rules for waves D/E, no discriminators between the four named variants, and a subdivision gate so permissive it would match almost any 5-leg sideways move. "RSI must support the triangle in every time frame" is undefined |
| ~~**Double / Triple Three**~~ | ~~OQ-18~~ | **IMPLEMENTED 2026-08-10** — recursion capped at depth 1, derived from the ladder. Their DT-02/TT-02 swing counts remain blocked by the new **OQ-26** (recorded, never gated) |
| **Impulse with Extension** *(classification only)* | OQ-24 *(investigated 2026-08-10, no cliff in data; independent of OQ-05)* | "Extension" / "elongated" / "exaggerated subdivisions" have no numeric definition anywhere |
| **Motive Sequence** | OQ-14 | Defined entirely by reference to "the numbers in the motive sequence" — **and those numbers are never stated**. Not implementable at any effort |
| **Fibonacci matching** | OQ-05 *(investigated 2026-08-10; blocks 14 rules, not 16)* | All 16 ratios are discrete exact values with no stated tolerance. Ratios **are computed and recorded**; they are never declared "matched" |
| **Named wave degrees** | OQ-17 | Only 2 of 9 degrees map to a timeframe and no rule assigns degree from price. Pivots carry an integer `scale` index only |
| **Confidence / scoring** | FR-7.4 | The reference states no weighting function anywhere. No such field exists in the model, the API, or the UI |

Each is registered in `validation.BLOCKED_RULES` and reported at runtime — absent, not silently
missing.

---

## 4. Decisions settled

All are **project decisions**, tier **EN** — the reference contributes nothing to any of them and
each is labelled as such wherever it appears.

| ID | Settled | Detail |
|---|---|---|
| **OQ-02** | Wave 3 "shortest" measure | **Absolute price distance** from pivot prices. Percentage, logarithmic and bar-count measures rejected. Gate: `len(w3) > min(len(w1), len(w5))` |
| **OQ-03** | Wave 4 "price territory" | **Pivot-price interval overlap**. Violated iff `territory(w4) ∩ territory(w1) ≠ ∅`. Scanning all bars inside wave 1's span rejected |
| **OQ-04** | Wave 5 momentum divergence | **RSI(13), strict directional comparison.** Up: wave 5 above wave 3 *and* RSI lower. Down: mirrored. No tolerance, no epsilon, no OB/OS levels. `NaN` RSI ⇒ UNDECIDABLE, never pass/fail |
| **OQ-21** | Pivot source | **Own detector**, threshold-based directional change. Neither modifies nor consumes `swing_identification.py` / `zigzag.py`. Chosen over an N-bar fractal specifically because that is what the existing module already is |
| **OQ-25** | Diagonal sub-wave grouping | Group finer legs into 5 sub-waves under alternation + LD-03/ED-03 shape only. All consistent groupings emitted as alternates, none preferred. **Still open as a question** — the leg→sub-wave mapping is a reading, not a stated rule; every diagonal carries `blocked_by: ["OQ-25"]` |
| **D-02b** | "Extreme" definition | Terminal **pivot price** (bar high/low), RSI read at that same bar. Confirmed, no change |
| **D-02c** | Exact-equality boundaries | **Reject on tie.** IMP-04 strict `>`; IMP-05 closed-interval intersection. Reachable on tick-quantised data, so deliberate |
| **D-13 rev 1** | Pivot thresholds | θ=0.20%, r=2.5, S=4 — calibrated on pivot *density*. **Superseded** |
| **D-13 rev 2** | Pivot thresholds | **θ=0.10%, r=4.0, S=4** (ladder 0.10/0.40/1.60/6.40%). Rev 1 could never satisfy IMP-02: at r=2.5 a coarse leg holds a median of 2 finer pivots where 4+ are needed, and **zero** impulses reached GATED above scale 1. Rev 2 is calibrated against the *gate-pass rate* (~6%), not pivot count (~24%) |
| **D-14** | IMP-02 recursion floor | At scale 1 there is no finer scale, so IMP-02 resolves to **UNDECIDABLE** — never a silent pass or fail |
| **D-05** | CI coverage | `pytest tests/` instead of `pytest tests/test_engine.py`. Previously 5 of 220 tests ran on push |

---

## 5. Known limitations

### 5.1 Motive-parent nesting does not occur — accepted, not a bug

**The classic "1-2-3-4-5 impulse with (i)-(v) sub-waves" figure is rare with the current design.**
Impulses overwhelmingly confirm at **scale 1**, where IMP-02 is UNDECIDABLE by D-14, and such an
impulse can never host sub-waves.

> **Corrected 2026-08-10.** This section previously read *"impulses **only ever** confirm at
> scale 1"* and *"**zero** scale-≥2 impulses in every one"*, measured across five configurations
> up to 7,189 bars / 113 structures. That measurement was correct but **the conclusion drawn from
> it was too strong — the limitation is dataset-size-dependent, not absolute.** Re-measured during
> the OQ-24 investigation over 60,000-bar slices of CL 5m, NQ 5m, CL 15m and ES 15m: **14 GATED
> scale-2 impulses do occur**, alongside 1,128 UNDECIDABLE scale-1 ones. The correct statement is
> that scale-≥2 impulses are *vanishingly rare* (roughly 1.2% of motive structures) and will not
> appear at all on small samples — not that they cannot exist.

Re-measured population, 60k-bar slices:

| | count |
|---|---|
| Impulses, UNDECIDABLE at scale 1 (IMP-02 unevaluable, D-14) | 1,128 |
| Impulses, **GATED at scale 2** | **14** |
| Leading / Ending Diagonals, GATED at scale 1 | 72 |

The nesting that *does* appear is the mirror image: scale-2 **corrective** structures (Flat,
Zigzag) whose A or C legs contain scale-1 impulses — a red `A–B–C` with an orange `(i)–(v)`
impulse inside wave C.

Root cause is the interaction of the D-13 ladder with strict recursive IMP-02: a single-scale
impulse pass rate of ~6% must hold for three legs simultaneously (ARCHITECTURE §5.6). Changing it
means either loosening IMP-02 — which the reference does not license — or a different scale
model. **Neither was done.**

### 5.2 Other limitations

- **Diagonals only in impulse wave 1/5 hosts.** Zigzag waves A/C are also valid hosts per
  LD-01/ED-01, but corrections are classified *after* diagonals in the pipeline, so those are not
  searched. Reported in `AnalysisResult.notes`.
- **Diagonal grouping is capped** at 64 alternates per host (FR-2.6). Truncation is reported in
  `notes`, never silent.
- **No alternate selection.** Overlapping candidates are all surfaced; FR-2.4 (ranking/pruning) is
  UNDEFINED. For *rendering* only, a nested structure claimed by two overlapping parents is drawn
  once under the tightest containing leg — a display decision that discards no analysis.
- **Cross-scale containment is measured, never assumed** — 99–100% in practice, but not 1.0, so
  hierarchy construction handles the exception.
- **Volume rules unimplemented** (OQ-22): all qualitative, and volume is synthetic on the default
  data source.
- **Report integration is one-way**: the report renders Elliott but `/report` gained no Elliott
  query parameters.

---

## 6. API

**One new read-only endpoint.** No existing endpoint changed; OpenAPI paths went 23 → 24, and
`/report` keeps exactly its original four parameters.

```
GET /api/backtests/{backtest_id}/elliott-wave
    ?theta_base=0.001&ratio=4.0&scales=4      # all optional, D-13 defaults
```

Response: `engine_version`, `config`, `pivots[]`, `waves[]`, `blocked_rules[]`, `notes[]`,
`counts{}`.

- Every pivot carries `index` **and** `confirm_index` (`confirm_index > index` always) so clients
  can respect no-look-ahead rather than re-derive it.
- Every wave carries `state` and `blocked_by`.
- Query parameters are validated: `theta_base ∈ (0,1)`, `ratio > 1`, `scales ∈ [1,8]` → 422
  otherwise; unknown backtest id → 404.
- Defaults come from the engine itself so client and server cannot drift (FR-1e.4).

---

## 7. UI

**Tab** — a 9th top-level tab, `🌊 Elliott Wave`, in `ResultsPage.tsx`. Four additions only
(import, query, `TabsTrigger`, `TabsContent`).

**Chart** — a standalone single-panel component. Does not import, extend or parameterise
`CandlestickChart.tsx`. Hierarchical labelling:

| Depth | Motive | Corrective |
|---|---|---|
| 0 | `1 2 3 4 5` | `A B C` |
| 1 | `(i)…(v)` | `(a) (b) (c)` |
| 2 | `((1))…((5))` | `((a)) ((b)) ((c))` |

Labels attach to pivots by arrow leader lines. Three colour roles: motive amber, corrective red,
and a third colour marking a structure's position inside its **actual** parent — not an assumed
degree. Controls: scale filter, nesting depth, show/hide undecidable — all backed by real data.
Opens on the last 260 bars with y fitted to that window.

**Report section** — `🌊 Elliott Wave` in the exported HTML, with a nav entry, the same chart
convention, and a completeness panel. Uses the **same serializer** as the live endpoint; verified
byte-identical payloads, so live and report can never disagree.

**FE-3 throughout.** Confirmed structures draw solid; UNDECIDABLE ones dashed, dimmed, labelled
"(undecidable)", with `blocked_by` in hover text. Sub-labels appear **only** where a subdivision
was actually detected — legs without one are left unlabelled rather than given invented markings.
No confidence value is displayed anywhere, because none exists.

---

## 8. Tests and CI

**220 tests, all passing** (5 engine + 29 swing/zigzag regression + 186 Elliott).

| Module | Tests | Covers |
|---|---:|---|
| `test_guards.py` | 71 | **TR-2 blocked-rule guards** |
| `test_pipeline_and_api.py` | 42 | RSI warmup, 20-run determinism, edge cases, endpoint |
| `test_impulse_rules.py` | 33 | IMP-01…06, one pass + one fail fixture per gate |
| `test_pivots.py` | 20 | No-look-ahead, alternation, determinism, containment |
| `test_structures.py` | 20 | Diagonals, Zigzag, Flat, Running Flat |

The guard tests are the load-bearing ones: they assert that **no blocked rule has been silently
implemented** — no Fibonacci constant or tolerance identifier anywhere, no Triangle / Motive
Sequence / DT / TT / wedge / extension logic, no Regular-vs-Expanded distinction, no scoring
field, and independence verified against the **resolved import graph** rather than a text grep.
They are written to be deleted deliberately when an Open Question is resolved, not to start
failing by accident.

**CI (D-05):** `.github/workflows/ci.yml` ran `pytest tests/test_engine.py` — **5 of 220 tests,
2%**, leaving every TR-2 guard unenforced on push. Now `pytest tests/ -v`.

---

## 9. Performance

**The report endpoint was timing out before any Elliott content existed.** Profiling ruled out the
obvious suspects (1,848 per-trade traces: 0.62s; pattern detection and zigzag: ≤2.6s at 20k bars)
and found `fig.add_shape()` / `fig.add_annotation()` called once per swing — both quadratic in
plotly.py:

| `add_annotation` calls | Time |
|---:|---:|
| 100 | 0.79s |
| 500 | 28.96s |
| 1,000 | 140.92s |

A 78,000-bar backtest yields **2,509 swings**, extrapolating to **~890s**. Both are now
accumulated and applied in one `update_layout` call — 2,000 in **0.425s**. Verified
output-preserving: before/after HTML byte-identical at 1,107,255 chars.

**Report generation:**

| Bars | Trades | Before | After fix | After fix + Elliott |
|---:|---:|---:|---:|---:|
| 2,000 | 54 | ~1.4s | 1.41s | **1.49s** |
| 20,000 | 635 | — | 6.33s | **4.08s** |
| 78,000 | 2,317 | **timeout (~890s)** | 22.29s | **14.99s** |

**Engine:** ~19,780 pivots and 1,315 structures on 78,210 bars, within a normal request. Fully
deterministic — byte-identical output across 20 repeated runs.

---

## 10. Remaining Open Questions — 22 of 27 unresolved

**Resolved (4):** OQ-02, OQ-03, OQ-04, OQ-21.

**Unresolved (21):**

| OQ | Subject |
|---|---|
| **OQ-01** | Whether the grammar-based Mandatory/Guideline split is the adopted classification. *Partially constrained* (blanket-non-gating ruled out) but not answered |
| **OQ-05** | Fibonacci tolerance — blocks all 16 ratio rules from ever "matching" |
| OQ-06 | "of wave 1-2" base undefined |
| OQ-07 | "inverse retracement" never defined |
| OQ-08 | Wave 4: §3.1 says ≤50%, §4.3 says <38.2% |
| OQ-09 / OQ-10 | "near" / "slightly beyond" / "substantially beyond" unquantified |
| OQ-11 | "wave AB" base undefined |
| OQ-12 / OQ-13 | Triangle gates vacuous; "RSI must support in every time frame" undefined |
| OQ-14 | Motive Sequence numbers never stated |
| OQ-15 | Wedge shape unquantified |
| OQ-16 | LD and ED permit identical subdivisions |
| OQ-17 | Degree assignment from price data |
| **OQ-26** | *(new)* DT-02/TT-02 swing count: the reference's 7 contradicts DT-04 + GEN-06's 9 |
| **OQ-27** | *(new)* Expanded vs Running Flat precedence: FLE-01 and FLU-01 are both exact and 29 of 34 real structures satisfy both, with no stated priority |
| OQ-19 | Zigzag-vs-impulse tiebreak, circular via OQ-24 |
| **OQ-20** | A 3-swing move is both possibly-motive and possibly-corrective, with no discriminator |
| OQ-22 | Volume statements qualitative |
| OQ-23 | Expanded and Running Flat share wave-B = 123.6% |
| OQ-24 | "Extension" has no numeric definition |
| **OQ-25** | *(new)* Diagonal leg→sub-wave mapping |

OQ-01, OQ-05 and OQ-20 were explicitly preserved unresolved by instruction throughout. **No Open
Question was resolved by substituting classical Elliott Wave knowledge** — where the reference is
silent, the engine says UNDECIDABLE.

---

## 11. Documentation Summary

**Files created (1 this step):** `docs/ELLIOTT_WAVE_IMPLEMENTATION.md` — this document, 11
sections: what was built, full file inventory, structures implemented vs deferred with reasons,
settled decisions, known limitations (incl. §5.1 motive-parent nesting), API, UI, tests and CI,
performance, remaining Open Questions, and this summary.

**Files created (branch total, 23):** 11 engine modules · 1 API schema · 4 docs · 7 test files.

**Files modified (branch total, 32):** including `api/serializers.py`, `api/routers/backtests.py`,
`api/report/report.py`, `ElliottWaveChart.tsx`, `types.ts`, `api.ts`, `ResultsPage.tsx`,
`ci.yml`, `CLAUDE.md`, `CHANGELOG.md`, `Dockerfile`.

**Files deleted (60):** the entire previous implementation — 9 engine modules, 2 API modules,
`benchmark/` (17), `validation/` (17), `cli/` (2), `tests/elliott/` (10), 2 web components, 1 doc.

**Modules and responsibilities:** §2.1.
**Structures implemented vs not, with reasons:** §3.
**Resolved decisions:** §4 — OQ-02, OQ-03, OQ-04, OQ-21, OQ-25 (partial), D-02b, D-02c, D-13
rev 1 + rev 2, D-14, D-05.
**Known limitations:** §5, with the motive-parent nesting limitation stated first and explicitly
recorded as accepted rather than a defect.
**API changes:** §6 — one new read-only endpoint, no existing endpoint altered.
**UI changes:** §7 — dedicated tab, dedicated chart with hierarchical labelling, and a report
section.
**Test coverage and CI:** §8 — 220 tests passing; D-05 raised CI coverage from 2% to 100%.
**Performance:** §9 — the quadratic-annotation timeout fix and measured generation times.
**Remaining Open Questions:** §10 — **22 of 27 unresolved**, listed individually.

**No code changed in this step** — documentation only.
