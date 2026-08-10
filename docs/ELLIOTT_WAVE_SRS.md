# Elliott Wave — Software Requirements Specification

**Phase 3 deliverable.** Version 0.1 (DRAFT — not approved for implementation).
Written 2026-08-09.

**Sole rule authority:** [docs/ELLIOTT_WAVE_RULES.md](ELLIOTT_WAVE_RULES.md) (94 rule records,
26 Open Questions), which in turn derives solely from
<https://elliottwave-forecast.com/elliott-wave-theory/>.

> **This document specifies requirements. It contains no production code and mandates none yet.**
>
> **Revision 0.8 — 2026-08-10.** **OQ-18 RESOLVED** — Double/Triple Three implemented with
> recursion capped at depth 1 (ARCHITECTURE §6.7a). Two rules the Phase-2 pass missed,
> **DT-05/TT-05** (the 161.8% wave-Y ceiling), are now extracted and specified — mandatory,
> and *not* blocked by OQ-05 since a ceiling is an inequality, not a match. **New unresolved
> OQ-26** records the reference's 7-vs-9 swing-count contradiction. Previously —
> **Revision 0.7 — 2026-08-10.** Diagonal sub-wave **grouping** revised so a diagonal no longer
> requires the host leg's finer subdivision to land on exactly 5 legs (ARCHITECTURE §6.6.1);
> diagonals went 0 → 4 on real data. **New unresolved OQ-25** records the leg→sub-wave
> mapping the reference never defines. Previously —
> **Revision 0.6 — 2026-08-10.** **D-13 revised to `theta_base = 0.10%`, ratio `r = 4.0`, `S = 4`** after Phase 5 implementation showed the rev-1 ladder could never
> satisfy IMP-02 (ARCHITECTURE §5.6). Previously — **D-13 closed** at
> `theta_base = 0.20%`, ratio `r = 2.5`, `S = 4` scales, with the measured evidence in
> [ELLIOTT_WAVE_ARCHITECTURE.md](ELLIOTT_WAVE_ARCHITECTURE.md) §5. **D-02b and D-02c are
> confirmed closed** (pivot-price reading kept; reject-on-tie kept). **Four Open Questions
> are RESOLVED by project decision:**
> **OQ-21** — the engine gets its own independent, Elliott-specific pivot detector, which neither
> modifies **nor consumes** `swing_identification.py` / `zigzag.py` (§4a). Plus, from revision 0.3:
> **OQ-02** (wave 3 "shortest" = absolute price distance) and **OQ-03** (wave 4 territory =
> pivot-price interval overlap), both §6.1b; and **OQ-04** (divergence = RSI(13) directional
> comparison), §6.1a. All three are tier **EN** — decisions, **not** source-defined behavior; the
> reference says nothing on any of them. **All six Impulse gates are now specified and the §8
> dependency chain is broken.** **The other 21 Open Questions remain unresolved**, and OQ-01 is
> *partially constrained* but explicitly **not** resolved (§8.3).
> Where a requirement depends on an open question it is marked **BLOCKED** or **UNDEFINED** and
> its behavior is deliberately left unspecified. No classical Elliott Wave knowledge
> (Prechter/Frost, Neely, or common practice) has been used to fill any gap.

---

## 1. Purpose and scope

### 1.1 Purpose

Define what an Elliott Wave analysis capability for this platform must do, given **only** what
the EWF reference actually states — and define with equal precision what it **cannot** do until
specific decisions are made.

### 1.2 In scope for v1

- A backend analysis module that consumes an ordered pivot sequence and emits labelled wave
  structure candidates with recorded measurements.
- One read-only API sub-resource exposing that output for a stored backtest.
- One **dedicated** frontend tab containing one **dedicated** chart.
- A test suite covering every implementable rule and guarding every blocked one.

### 1.3 Explicitly out of scope for v1

| Excluded | Reason |
|---|---|
| Any change to the Price & Trades chart | Elliott Wave is a dedicated tab with its own chart. The Price & Trades chart stays a plain Price & Trades chart. See §9. |
| Elliott Wave in the exported HTML report | Not requested for this phase, and the report path duplicates chart logic in Python (`api/report/charts.py`), doubling the surface. Deferred — see §12, D-07. |
| Trade signals, entries, exits, or any strategy influence | Analysis and display only. |
| Forecasting / projection of incomplete structures | The reference describes completed structures; it states no forecasting procedure. |
| Confidence scores or probability rankings | The reference states no weighting or scoring function anywhere. See §7.4. |
| Multi-timeframe analysis | Required by TRI-06 ("every time frame") but undefined — see OQ-13. |

### 1.4 Status of this specification

At revision 0.4 the core path is **fully specified end to end**: an independent pivot detector
(§4a) feeds Impulse, Diagonals, Zigzag, generic Flat and Running Flat, all of whose gates are
settled (§8.1). Regular/Expanded Flat, Triangle, Double/Triple Three, Extension and Motive
Sequence remain blocked on their own Open Questions and are **out of the v1 core**. One
configuration decision (**D-13**, threshold values) and two boundary confirmations
(**D-02b**, **D-02c**) are outstanding, but no *rule* gap remains on the core path.

---

## 2. Definitions

| Term | Meaning in this document |
|---|---|
| **Pivot** | A price turning point: (bar index, timestamp, price, high\|low). The atomic input. |
| **Leg** | The move between two consecutive pivots. |
| **Wave** | A leg that has been assigned a label within a structure. |
| **Structure** | A named pattern (Impulse, Zigzag, Flat, …) spanning several legs. |
| **Candidate** | A structure hypothesis under evaluation. Not yet accepted. |
| **Gate** | A rule whose failure prevents a candidate from being created. |
| **Measurement** | A recorded numeric observation (e.g. a ratio) that never gates. |
| **Degree** | One of the reference's 9 named scale levels (DEG-02). |
| **Blocked** | Cannot be specified or built until a named Open Question is answered. |

---

## 3. Requirement classification scheme

Every requirement below carries exactly one tier tag. The four tiers you asked for, plus one
clearly-separated category for requirements that are ours rather than the reference's:

| Tier | Name | Meaning |
|---|---|---|
| **SD** | **Source-Defined behavior** | The reference states this explicitly. Quotable. Implementable as written. |
| **EI** | **Explicit Inference from the source** | Not stated verbatim, but follows necessarily from a stated rule. **The inference is written out in full at each occurrence** so it can be audited and rejected. |
| **UD** | **Unresolved Decision** | Depends on an unresolved Open Question. Behavior deliberately left **UNDEFINED**. |
| **NI** | **Not Implementable from the reference alone** | The reference is silent. Cannot be built from this source at any level of effort. |
| **EN** | *Engineering requirement (not from the reference)* | Ours: determinism, immutability, performance, testing. Carries no Elliott Wave semantics. **Separated out so it is never mistaken for source-defined behavior.** |

**Tier counts across this SRS** (tier-tagged requirement statements, 132 total at revision 0.5):
SD 11 · EI 8 · UD 13 · NI 3 · EN 97.

The EN block now carries the three resolved rules — FR-3.1a.* (OQ-04), FR-3.1b.* (OQ-02, OQ-03) —
plus the input-contract additions OQ-04 forced (FR-1.6…1.8). All are tagged **EN, not SD**, on
purpose: they are project decisions, and the reference contributes nothing to any of them.

The **EN** count dominates because most of what an SRS must pin down — determinism, immutability,
layering, boundaries, test obligations, UI structure — is engineering, not Elliott Wave semantics.
That is the correct ratio for this project and not a sign of invented rules: **every** requirement
carrying Elliott Wave meaning is tagged SD, EI, UD or NI and traced to a rule ID in §15 — with the
single, deliberate exception of FR-3.1a.*, which carries Elliott meaning but is tagged **EN**
precisely because it originates from a project decision rather than the reference.

---

## 4. Functional requirements — Input

### FR-1 Pivot input contract

| ID | Tier | Requirement |
|---|---|---|
| FR-1.1 | **EI** | The engine SHALL consume an ordered sequence of pivots. **Inference:** every rule in the inventory that measures anything (IMP-03, IMP-F01, ZZ-F01, …) is expressed as a relationship between prices at wave boundaries; wave boundaries are pivots. Therefore a pivot sequence is a necessary input. The reference never says this, but no rule can be evaluated without it. |
| FR-1.2 | **EI** | Each pivot SHALL carry: bar index, timestamp, price, and kind ∈ {high, low}. **Inference:** index/timestamp are needed to order legs and to render; price is needed by every measurement; kind is needed because "retrace" and "beyond" (IMP-03, FLE-01, FLU-01) are direction-dependent. |
| FR-1.3 | **EI** | Pivots SHALL alternate high/low. **Inference:** a leg is defined between consecutive turning points; two consecutive highs do not bound a leg. |
| FR-1.4 | **EN — OQ-21 RESOLVED** | The pivot sequence SHALL be produced by a **new, Elliott-specific detector** inside `src/analysis/elliott_wave/`, specified in §4a. It SHALL NOT reuse, import, wrap, or consume the output of any existing pivot/swing code in this repository. |
| FR-1.5 | **EN** | Whatever provides pivots, the engine SHALL treat the input as immutable and SHALL NOT modify it. |
| FR-1.6 | **EN** | The engine SHALL additionally receive the **`close` price series** of the analysed bars, aligned to the same bar index as the pivots. **Added by the OQ-04 resolution:** IMP-06 requires RSI(13), which is derived from closes. Pivots alone are no longer a sufficient input. |
| FR-1.7 | **EN** | RSI(13) SHALL be obtained from the existing shared implementation `src/analysis/indicators.py::calc_rsi(close, 13)`, consumed **read-only**. That module SHALL NOT be modified (§12.1). |
| FR-1.8 | **EN** | Where RSI(13) is `NaN` at a bar required by IMP-06 — including the unavoidable 13-bar warmup, since `calc_rsi` uses `min_periods=13` — the affected candidate SHALL be marked **UNDECIDABLE** (FR-5.3), never passed or failed. |

#### FR-1.4 resolution — independent detection (project decision)

The reference contains **zero** content on locating pivots from raw price, so this was always
going to be invented engineering. Two structurally different options existed:

| Option | Description | Status |
|---|---|---|
| **A — Consume existing** | Read pivots from `swing_identification.py` (`identify_swings`) or `zigzag.py` (`calc_zigzag`). | X **Rejected 2026-08-09.** Would couple Elliott output to the Swing/3-Leg system's parameters. |
| **B — Independent detection** | The Elliott module detects its own pivots end to end. | **ADOPTED 2026-08-09.** Specified in §4a. |

**The "don't touch" boundary is hereby strengthened to "don't touch *and* don't consume."**
`swing_identification.py` and `zigzag.py` remain unmodified **and** must not appear as a
dependency of the Elliott package in any form — import, wrapper, subclass, or consumption of
their return values (§12.1, TR-7).

---

## 4a. Pivot detector requirements

> **Tier EN throughout. Nothing in this section derives from the reference**, which assumes waves
> are already identified. This is 100% project engineering, specified here because it is the
> engine's input contract.

### FR-1a — Mechanism

| ID | Tier | Requirement |
|---|---|---|
| FR-1a.1 | **EN** | The detector SHALL live in the new `src/analysis/elliott_wave/` package (e.g. `pivots.py`) and SHALL be self-contained. |
| FR-1a.2 | **EN** | It SHALL consume `BacktestResults.price_data` — the canonical OHLCV DataFrame already held in the store — and SHALL NOT re-fetch, reload, or re-derive market data. |
| FR-1a.3 | **EN** | It SHALL NOT mutate the input DataFrame. |
| FR-1a.4 | **EN** | **Detection SHALL use threshold-based directional change**, not an N-bar fractal. A single chronological pass maintains a direction and a running extreme; a pivot is emitted when price reverses from that extreme by at least the scale's threshold theta. |
| FR-1a.5 | **EN** | **Rationale for FR-1a.4, recorded so it can be challenged:** an N-bar fractal is exactly what `swing_identification.py` already implements. Re-deriving that design — even without importing it — would make the detector independent in name only. Directional change confirms on a **price event** rather than a **fixed bar lag**, which also supplies a non-arbitrary confirmation moment. |

### FR-1b — No look-ahead

| ID | Tier | Requirement |
|---|---|---|
| FR-1b.1 | **EN** | Every pivot SHALL carry **both** `index` (the bar where the extreme occurred) and `confirm_index` (the later bar at which the reversal completed). These SHALL be distinct fields; `confirm_index > index` always. |
| FR-1b.2 | **EN** | Any consumer evaluating bar *t* SHALL use only pivots with `confirm_index <= t`. Using `index` as if the pivot were known at that bar is look-ahead bias and is prohibited. |
| FR-1b.3 | **EN** | The **final, unconfirmed extreme SHALL NOT be emitted** as a pivot. It has no confirmation bar, and emitting it would be precisely the look-ahead FR-1b.1 exists to prevent. |
| FR-1b.4 | **EN** | A test SHALL verify no-look-ahead directly: truncating the input at bar *t* and re-running SHALL reproduce exactly the pivots whose `confirm_index <= t`, with identical prices and indices. |

### FR-1c — Output contract

| ID | Tier | Requirement |
|---|---|---|
| FR-1c.1 | **EN** | **Pivot price = the bar's own extreme** — `high` for a HIGH pivot, `low` for a LOW pivot. This is the same convention already fixed by FR-3.1a.7 (IMP-06), FR-3.1b.1 (IMP-04) and FR-3.1b.4 (IMP-05). **One convention across the entire engine.** |
| FR-1c.2 | **EN** | Pivots SHALL strictly alternate HIGH/LOW. Guaranteed by construction — direction flips on every emission — satisfying FR-1.3 without a separate post-filter. |
| FR-1c.3 | **EN** | Each pivot SHALL carry an integer `scale` index identifying which threshold produced it (FR-1d.1). |
| FR-1c.4 | **EN** | The emitted pivot record SHALL satisfy DM-1 exactly, so the already-specified Impulse, Diagonal, Zigzag and Flat gates (FR-3.1, FR-3.1b, FR-3.3, FR-3.6, FR-3.7) consume it with no adaptation layer. |

### FR-1d — Multi-scale ladder

| ID | Tier | Requirement |
|---|---|---|
| FR-1d.1 | **EN** | The detector SHALL run the same pass independently at *S* scales, with geometric thresholds theta_k = theta_base * r^(k-1); scale 1 is finest, scale *S* coarsest. |
| FR-1d.2 | **EN** | **Rationale:** Elliott is inherently hierarchical — IMP-02 requires waves 1/3/5 to subdivide into impulses, and DT-03/TT-03 reference structures "of smaller degree". A single-scale pivot list cannot support nesting at all. |
| FR-1d.3 | **EN** | **`scale` is NOT an Elliott degree.** The detector SHALL emit only an integer scale index. Mapping a scale to one of the reference's 9 named degrees remains **OQ-17, open** — the detector must not pre-empt it. |
| FR-1d.4 | **EN** | **Cross-scale nesting SHALL NOT be assumed.** Directional change at a coarse threshold does not guarantee its extremes are a subset of a finer threshold's extremes. Hierarchy construction SHALL handle non-nesting explicitly. A test SHALL measure the actual containment rate rather than assume it. |

### FR-1e — Threshold configuration

| ID | Tier | Requirement |
|---|---|---|
| FR-1e.1 | **EN** | The threshold SHALL be **relative (percentage)**, applied to the running extreme's price. |
| FR-1e.2 | **EN** | Volatility-adaptive thresholds (ATR- or stdev-scaled) SHALL NOT be used in v1. **Considered and deferred:** adaptation introduces a second undefined parameter set and makes determinism harder to reason about. It can be added later without changing the pivot contract (FR-1c). |
| FR-1e.3 | **EN — D-13 CLOSED (rev 2, 2026-08-10)** | Defaults: **`theta_base = 0.001` (0.10%), ratio `r = 4.0`, `S = 4` scales** → ladder 0.10 / 0.40 / 1.60 / 6.40%. **Supersedes rev 1 (0.20% / 2.5)**, which was calibrated on pivot density and proved unable to satisfy IMP-02's recursive requirement — zero impulses reached GATED above scale 1. Rev 2 is calibrated on the binding constraint: whether a coarse leg contains a finer window passing **all six** impulse gates (~6% pass rate), not merely ≥5 finer pivots (~24%). Evidence: ARCHITECTURE §5.6. **Configuration**, tunable per request via API-1.4. |
| FR-1e.4 | **EN** | Whatever values D-13 selects SHALL become the documented defaults of both the analysis function and the API endpoint, and a parity test SHALL assert the two cannot drift apart — the same class of check that already guards the `zz_deviation` defaults. |

### FR-1f — Determinism and independence

| ID | Tier | Requirement |
|---|---|---|
| FR-1f.1 | **EN** | Detection SHALL be a single deterministic pass per scale — no randomness, no wall-clock, no I/O. Identical input SHALL produce byte-identical pivots. |
| FR-1f.2 | **EN** | The Elliott package SHALL NOT import `src.analysis.swing_identification`, `src.analysis.zigzag`, or any other existing pivot/swing detection module, and SHALL NOT consume their return values. Enforced by TR-7. |
| FR-1f.3 | **EN** | `src/analysis/indicators.py::calc_rsi` remains the **one** permitted read-only dependency on shared analysis code (FR-1.7). It is an indicator, not a pivot/swing detector, so it does not conflict with FR-1f.2. |

---

## 5. Functional requirements — Candidate enumeration

### FR-2 Enumeration

| ID | Tier | Requirement |
|---|---|---|
| FR-2.1 | **EI** | The engine SHALL evaluate contiguous pivot windows. **Inference:** each structure has a stated leg count (IMP-01: 5; ZZ-01: 3; TRI-01: 5; DT-01: 3; TT-01: 5), and a structure occupies consecutive legs. A window of *n* legs requires *n+1* pivots. |
| FR-2.2 | **SD** | Window sizes, per the reference's stated leg counts: Impulse 5 legs (IMP-01) · Leading/Ending Diagonal 5 legs (LD-03/ED-03) · Zigzag 3 legs (ZZ-01) · Flat 3 legs (FL-01) · Triangle 5 legs (TRI-01) · Double Three 3 legs (DT-01) · Triple Three 5 legs (TT-01). |
| FR-2.3 | **EN — OQ-18 RESOLVED** | Recursion depth is capped at `max_combination_depth = 1` (FR-3.9a.1), derived from the ladder rather than chosen. The reference still states no limit; the cap is a project decision. |
| FR-2.4 | **UD** | Whether overlapping candidates are ranked, pruned, or all retained is **UNDEFINED**. The reference states no selection procedure between competing readings. (Related: ZZ-F03/OQ-19, where the reference acknowledges an ambiguity and offers a tiebreak that is itself undefined.) |
| FR-2.5 | **NI** | No search-order, completeness, or termination criterion can be derived. The reference describes patterns, never a procedure for finding them. |
| FR-2.6 | **EN** | Enumeration SHALL be bounded so that analysis of a bounded bar count terminates in bounded time. Concrete bounds: Phase 4 (§12, D-03). |

---

## 6. Functional requirements — Structure classification

Each subsection lists the reference's gates for that structure and their status. **A structure
whose gate set contains any BLOCKED gate cannot be classified.**

### FR-3.1 Impulse (§3.1)

| Gate | Rule | Tier | Status |
|---|---|---|---|
| Exactly 5 legs | IMP-01 | SD | Implementable |
| Waves 1, 3, 5 each subdivide as impulse | IMP-02 | SD | Implementable *but recursive* — see FR-2.3 |
| Wave 2 does not retrace beyond the start of wave 1 | IMP-03 | SD | Implementable. Direction-aware: up-impulse requires P(end 2) > P(start 1); down-impulse requires P(end 2) < P(start 1) |
| Wave 3 is not the shortest of 1/3/5 | IMP-04 | **EN — OQ-02 RESOLVED** | **Implementable.** Absolute price distance from pivot prices (§6.1b). |
| Wave 4 does not overlap wave 1's price territory | IMP-05 | **EN — OQ-03 RESOLVED** | **Implementable.** Pivot-price interval overlap (§6.1b). |
| Wave 5 ends with momentum divergence | IMP-06 | **EN — OQ-04 RESOLVED** | **Implementable.** Defined by project decision (§6.1a) as a directional RSI(13) comparison. Remains **MANDATORY**. |

**FR-3.1.1 [EN]** — ✅ **Impulse classification is UNBLOCKED.** All six gates (IMP-01…IMP-06) are
now specified: three by the reference (IMP-01/02/03) and three by project decision
(IMP-04 → OQ-02, IMP-05 → OQ-03, IMP-06 → OQ-04). See §8 for the resulting cascade.

**FR-3.1.2a [EN]** — Impulse classification remains subject to the engineering preconditions that
apply to every structure: a defined pivot source (**OQ-21**, still open — FR-1.4) and a
recursion/termination bound for IMP-02's sub-classification (FR-2.6). Neither is an Elliott-rule
blocker, but neither is satisfied yet.

### 6.1b IMP-04 and IMP-05 — resolved definitions (project decision, not source-defined)

> ⚠ **Tier EN, not SD.** The reference states both rules but defines neither measurement. Both
> definitions below were supplied by project decision on 2026-08-09. They are **not**
> source-defined behavior and must never be cited as such.

**Shared convention.** Both use **pivot prices** — the same convention as FR-3.1a.7. Checked for
contradiction with FR-3.1a.7: **none found**; the three decisions reinforce one another, so
FR-3.1a.7 is unchanged.

| ID | Tier | Requirement |
|---|---|---|
| FR-3.1b.1 | **EN** | **Wave length SHALL be absolute price distance**: `len(w) = abs(P(end pivot of w) − P(start pivot of w))`, using pivot prices. |
| FR-3.1b.2 | **EN** | Percentage distance, logarithmic distance, and bar count (time) SHALL NOT be used as the length measure. |
| FR-3.1b.3 | **EN** | **IMP-04 gate:** the candidate is rejected unless `len(wave 3) > min(len(wave 1), len(wave 5))`. No tolerance, threshold, or buffer SHALL be applied. |
| FR-3.1b.4 | **EN** | **Wave territory SHALL be the pivot-price interval**: `territory(w) = [min(P(start w), P(end w)), max(P(start w), P(end w))]`. |
| FR-3.1b.5 | **EN** | **IMP-05 gate:** the candidate is rejected iff `territory(wave 4)` intersects `territory(wave 1)`. Wave 4 is invalid **only** when its price enters/overlaps wave 1's territory; nothing else about wave 4's position gates. |
| FR-3.1b.6 | **EN** | IMP-05 SHALL NOT scan all bars spanned by wave 1 for a more extreme value than its two endpoint pivots. The full-intrabar-range reading is explicitly rejected. |
| FR-3.1b.7 | **EN** | No tolerance, percentage threshold, or arbitrary buffer SHALL be introduced into either gate. |
| FR-3.1b.8 | **EN** | **Exact-equality boundary handling** — the one detail neither decision states explicitly. Adopted defaults: IMP-04 uses **strict `>`**, so a wave 3 exactly equal to the shorter of waves 1/5 is treated as *being* a shortest wave and is rejected. IMP-05 uses **closed-interval intersection**, so territories that touch at exactly one price count as overlapping and are rejected. Both are the literal readings. **Confirmed 2026-08-09 (D-02c closed)** — reject-on-tie stands. See §14a. |

**Why FR-3.1b.8 matters in practice:** futures prices are tick-quantised (ES = 0.25), so exact
equality between two wave lengths, or an exact touch between two territories, is a genuinely
reachable case on real data — not a floating-point curiosity that can be waved away.

### 6.1a IMP-06 — resolved definition (project decision, not source-defined)

> ⚠ **Tier EN, not SD.** The reference names no indicator, period, or comparison procedure. This
> definition was supplied by project decision on 2026-08-09 because IMP-06 is mandatory and
> therefore had to be made computable. It is **not** source-defined behavior and must never be
> cited as such.

| ID | Tier | Requirement |
|---|---|---|
| FR-3.1a.1 | **EN** | IMP-06 SHALL remain a **MANDATORY gate**. "Guidelines" SHALL NOT be treated as non-gating as a blanket rule — that alternative was explicitly rejected because it would also have silently weakened IMP-03, IMP-04 and IMP-05, which sit under the same heading. |
| FR-3.1a.2 | **EN** | Divergence SHALL be evaluated with **RSI(13)** via `calc_rsi(close, 13)` (FR-1.7). |
| FR-3.1a.3 | **EN** | **Up-trending impulse:** divergence holds iff wave 5's extreme is **above** wave 3's extreme **and** RSI(13) at wave 5's extreme is **strictly LOWER** than RSI(13) at wave 3's extreme. |
| FR-3.1a.4 | **EN** | **Down-trending impulse:** divergence holds iff wave 5's extreme is **below** wave 3's extreme **and** RSI(13) at wave 5's extreme is **strictly HIGHER** than RSI(13) at wave 3's extreme. |
| FR-3.1a.5 | **EN** | The RSI comparison SHALL be **strictly directional**. No tolerance band, no epsilon, no minimum divergence magnitude, and no overbought/oversold levels SHALL be introduced. *(The platform's RSI(13) chart bands are 70/30; they play no part in this rule.)* |
| FR-3.1a.6 | **EN** | If RSI(13) is unavailable (`NaN`) at either comparison bar, IMP-06 SHALL evaluate to **UNDECIDABLE** (FR-1.8, FR-5.3) — never pass, never fail. |
| FR-3.1a.7 | **EN** | "Extreme" means the **pivot price** at the wave's terminal pivot (the bar high for a high pivot, the bar low for a low pivot), and RSI(13) is read at **that same bar**. Both sides of each comparison use the same convention. **Confirmed 2026-08-09 (D-02b closed)** — the pivot-price reading stands. See §14a. |
| FR-3.1a.8 | **EN** | If wave 5's extreme does **not** exceed wave 3's extreme, the price precondition fails and IMP-06 is **not satisfied** (a failed gate, not UNDECIDABLE). |

**FR-3.1.2 [SD]** — When unblocked, the engine SHALL record these guideline measurements without
ever gating on them: IMP-F01 (wave 2 / wave 1), IMP-F02 (wave 3 / wave 1-2), IMP-F03 (wave 4 /
wave 3), IMP-F04 (three independent wave-5 bases). All four are **UD — OQ-05** for matching; the
raw ratio may still be computed and recorded.

### FR-3.2 Impulse with Extension (§3.2)

| Gate | Rule | Tier | Status |
|---|---|---|---|
| Exactly one of waves 1/3/5 is "extended" | EXT-01 | **UD — OQ-24** | **BLOCKED.** "Extended" has no numeric definition. |
| "Elongated impulses with exaggerated subdivisions" | EXT-02 | **UD — OQ-24** | **BLOCKED.** "Elongated"/"exaggerated" unquantified. |
| Market-class priors (equities/FX → wave 3; commodities → wave 5) | EXT-03, EXT-04 | **NI** | Not a detector rule. The platform has no instrument-class taxonomy, and the reference gives no probability values. |

**FR-3.2.1 [UD]** — Extension detection is **BLOCKED** in its entirety. This transitively affects
ZZ-F03/OQ-19, whose tiebreak depends on "whether the third swing has extension or not".

### FR-3.3 Leading Diagonal (§3.3) / FR-3.4 Ending Diagonal (§3.4)

| Gate | Rule | Tier | Status |
|---|---|---|---|
| Host position: LD = impulse wave 1 or zigzag wave A | LD-01 | SD | Implementable — but depends on a classified host (see §8) |
| Host position: ED = impulse wave 5 or zigzag wave C | ED-01 | SD | Implementable — same dependency |
| Subdivision ∈ {5-3-5-3-5, 3-3-3-3-3} | LD-03, ED-03 | SD | Implementable |
| Wave 1/4 overlap | LD-02, ED-02 | **SD (explicitly non-gating)** | The reference states outright: *"overlap between wave 1 and 4 is **not a condition**, it may or may not happen."* MUST be recorded, MUST NOT gate. |
| Wedge shape | LD-02, ED-02 | **UD — OQ-15** | **BLOCKED.** "Wedge shape" is never quantified. |

**FR-3.3.1 [SD]** — Overlap MUST NOT gate a diagonal. This is one of the few places the reference
is explicit about a rule *not* applying.

**FR-3.3.2 [UD — OQ-15]** — With overlap non-gating and wedge undefined, the only remaining
discriminators are host position and subdivision. Whether that is sufficient to call something a
diagonal is **UNDEFINED**.

**FR-3.3.3 [UD — OQ-16]** — LD-03 and ED-03 permit **identical** subdivision sets. Leading and
Ending Diagonal are distinguishable **only** by host position. Confirmation required.

### FR-3.5 Motive Sequence (§3.5)

| Gate | Rule | Tier | Status |
|---|---|---|---|
| Swing count ∈ "the motive sequence" | MS-01, MS-02, MS-03 | **NI** | **NOT IMPLEMENTABLE.** The rule is defined entirely by reference to "the numbers in the motive sequence" — **and the reference never states those numbers.** |

**FR-3.5.1 [NI]** — Motive Sequence SHALL NOT be implemented in v1. No amount of care can extract
a number set that is absent from the source. Supplying one would be invention (OQ-14).

### FR-3.6 Zigzag (§5.1)

| Gate | Rule | Tier | Status |
|---|---|---|---|
| Exactly 3 legs, labelled A-B-C | ZZ-01 | SD | Implementable |
| Waves A and C each subdivide into 5 waves (impulse or diagonal) | ZZ-02 | SD | Implementable — **depends on impulse/diagonal classification** (§8) |
| Wave B is any corrective structure | ZZ-03 | SD | Implementable (permissive) |
| Overall 5-3-5 | ZZ-04 | SD | Implementable |
| Wave B / wave A ratio | ZZ-F01 | **UD — OQ-05** | Record, never gate |
| Wave C / wave A ratio | ZZ-F02 | **UD — OQ-05** | Record, never gate |
| Impulse-vs-zigzag disambiguation at C = 161.8% | ZZ-F03 | **UD — OQ-19** | **BLOCKED.** The reference's own tiebreak ("whether the third swing has extension") depends on OQ-24, which is also unresolved. Circular. |

### FR-3.7 Flat and subtypes (§5.2)

| Gate | Rule | Tier | Status |
|---|---|---|---|
| 3 legs, 3-3-5 subdivision | FL-01 | SD | Implementable |
| Wave A subdivides into 3 (this is what separates Flat from Zigzag) | FL-02 | SD | Implementable |
| **Regular:** wave B terminates *near* the start of wave A | FLR-01 | **UD — OQ-09** | **BLOCKED.** "Near" unquantified; paired ratio is a single point (90%) with no tolerance. |
| **Regular:** wave C terminates *slightly beyond* the end of wave A | FLR-02 | **UD — OQ-10** | **BLOCKED.** "Slightly" unquantified. |
| **Expanded:** wave B terminates beyond the start of wave A | FLE-01 | SD | Implementable — a clean directional price comparison |
| **Expanded:** wave C ends *substantially beyond* the end of wave A | FLE-02 | **UD — OQ-10** | **BLOCKED.** "Substantially" unquantified. |
| **Running:** wave C falls short of where wave A ended | FLU-01 | SD | Implementable — a clean directional price comparison |
| All flat Fibonacci ratios | FLR-F01/F02, FLE-F01/F02, FLU-F01/F02 | **UD — OQ-05, OQ-11** | Record, never gate. Additionally **OQ-11**: the base "wave AB" is undefined. |

**FR-3.7.1 [UD — OQ-10]** — Regular and Expanded Flat are separated *only* by "slightly beyond"
vs "substantially beyond". With both undefined, **the two subtypes are not distinguishable**.

**FR-3.7.2 [UD — OQ-23]** — Expanded and Running Flat state the **same** wave-B ratio (123.6%).
Wave B cannot discriminate between them; only wave C can (FLE-02 vs FLU-01).

**FR-3.7.3 [EI]** — Of the three subtypes, only **Running Flat** has a fully-specified,
non-Fibonacci mandatory gate (FLU-01). **Inference:** FLE-01 is also clean, but Expanded's second
gate FLE-02 is blocked, whereas Running's single stated gate is complete. This makes Running Flat
the only flat subtype whose structural test is fully derivable today.

### FR-3.8 Triangle (§5.3)

| Gate | Rule | Tier | Status |
|---|---|---|---|
| 5 legs, labelled A-B-C-D-E | TRI-01 | SD | Implementable |
| Every leg subdivides into 3 | TRI-03 | SD | Implementable |
| Host position (wave B or wave 4) | TRI-02 | SD (guideline — "usually") | Implementable, non-gating |
| Leg subdivision ∈ {abc, wxy, flat} | TRI-04 | **UD — OQ-12** | Permissive to the point of vacuity — covers nearly every corrective structure |
| Decreasing volume and volatility | TRI-05 | **UD — OQ-22** | **BLOCKED.** Qualitative, no threshold; and volume is synthetic on the default data source |
| "RSI also needs to support the triangle in every time frame" | TRI-06 | **UD — OQ-13** | **BLOCKED.** "Support" undefined; "every time frame" undefined in a single-timeframe backtest |
| Ascending / descending / contracting / expanding variants | TRI-07 | **UD — OQ-12** | **BLOCKED.** Named but given no distinguishing rules |
| Per-wave Fibonacci ratios | — | **NI** | The reference states **none** for any triangle wave |
| Rules for wave D or wave E individually | — | **NI** | The reference states **none** |

**FR-3.8.1 [UD — OQ-12]** — Triangle's implementable gates (5 legs, each subdividing into 3)
would match almost any 5-leg sideways move. **Whether Triangle is in scope for v1 at all is an
open decision.** This SRS does not resolve it, and does not invent geometry to prop it up.

### FR-3.9 Double Three (§5.4) / FR-3.10 Triple Three (§5.5)

| Gate | Rule | Tier | Status |
|---|---|---|---|
| DT: 3 legs W-X-Y; TT: 5 legs W-X-Y-X-Z | DT-01, TT-01 | SD | Implementable |
| DT: 7 sub-swings; TT: 11 sub-swings | DT-02, TT-02 | SD | Implementable |
| W/Y (DT) and W/Y/Z (TT) in {zigzag, flat, DT of smaller degree, TT of smaller degree} | DT-03, TT-03 | **EN — OQ-18 RESOLVED** | **Implementable.** Recursion capped at depth 1 (FR-3.9a). Uses the pivot ladder's `scale`, not a named degree, so OQ-17 is not involved. |
| X ∈ any corrective structure | DT-04, TT-04 | SD | Implementable (permissive) |
| DT: X/W and Y/W ratios; TT: X/W and Z/W ratios | DT-F01/F02, TT-F01/F02 | **UD — OQ-05** | Record, never gate |

**FR-3.9.1 [SD]** — The reference states **no** ratio for wave Y in a Triple Three, and none for
the second X. The engine SHALL NOT fabricate one. This asymmetry is in the source.

### FR-3.9a Double Three / Triple Three (§5.4, §5.5) — OQ-18 RESOLVED

| Gate | Rule | Tier | Status |
|---|---|---|---|
| 3 legs W-X-Y / 5 legs W-X-Y-X-Z | DT-01, TT-01 | SD | Implementable |
| W/Y (and Z) hold a zigzag, flat, DT or TT of smaller degree | DT-03, TT-03 | **EN — OQ-18 RESOLVED** | Implementable; recursion capped at depth 1 |
| X is any corrective structure | DT-04, TT-04 | SD (permissive) | Never gates |
| Wave Y must not pass 161.8% of wave W | **DT-05, TT-05** | **SD** | Implementable — a stated **ceiling**, so no tolerance is needed and OQ-05 does not apply |
| 7-swing / 11-swing structure | DT-02, TT-02 | **UD — OQ-26** | **Recorded, never gated** |

**FR-3.9a.1 [EN]** — `max_combination_depth = 1`. Derived, not chosen: correctives exist only at
scale 2, so a combination needs scale 3, a nested one scale 4, and a doubly-nested one scale 5 —
beyond the 4-scale ladder. Confirmed after implementation: depth-0 combinations appear at scale 3,
depth-1 at scale 4.

**FR-3.9a.2 [SD]** — TT-05 constrains wave **Y**, not wave Z. A large wave Z is not bounded by it.

**FR-3.9a.3 [EN]** — A structure found at depth *d* SHALL NOT be re-emitted at depth *d+1*; the
shallowest find wins, and `combination_depth` reports it.

### FR-3.11 Degree assignment (§1.4)

| ID | Tier | Requirement |
|---|---|---|
| FR-3.11.1 | **SD** | Nine degrees exist, named largest→smallest: Grand Super Cycle, Super Cycle, Cycle, Primary, Intermediate, Minor, Minute, Minuette, Subminuette (DEG-01, DEG-02). |
| FR-3.11.2 | **UD — OQ-17** | **How a degree is assigned to a structure is UNDEFINED.** The reference maps only 2 of 9 degrees to timeframes (GSC → weekly/monthly, Subminuette → hourly) and gives no rule for assigning degree from price data. |
| FR-3.11.3 | **EI** | Degree labelling, if implemented, SHALL be presentation-only and SHALL NOT affect classification. **Inference:** no rule in the inventory takes degree as an input to a gate, except DT-03/TT-03's "of smaller degree", which is resolved by the depth cap and keyed on the ladder's integer `scale`, never a named degree. |

---

## 7. Functional requirements — Measurement, evidence, and output

### FR-4 Measurement recording

| ID | Tier | Requirement |
|---|---|---|
| FR-4.1 | **SD** | Guideline measurements SHALL be recorded and SHALL NEVER gate. Every Fibonacci relationship in the inventory (16 rules) sits under the reference's "Fibonacci Ratio Relationship" heading, separate from its "Guidelines" list. |
| FR-4.2 | **UD — OQ-05** | **Whether a recorded ratio "matches" its stated Fibonacci value is UNDEFINED.** All 16 ratios are discrete exact values with no tolerance. Raw ratios MAY be computed; match/no-match MUST NOT be asserted. |
| FR-4.3 | **UD — OQ-22** | All volume-based observations (WP-02, WP-04, WP-08, WP-11, WP-12, WP-13, TRI-05) are **UNDEFINED**: qualitative wording, no thresholds, no measurement window — and volume is synthetic on the default data source, so any such rule would be meaningless in the common case. |
| FR-4.4 | **SD** | Wave-personality narrative statements (WP-01, WP-09) SHALL NOT be implemented as detectors. They are prose. |
| FR-4.5 | **EI** | WP-03 duplicates IMP-03. The engine SHALL implement it once. **Inference:** §4.1's "can never extend beyond the starting point of wave one" and §3.1's "can't retrace more than the beginning of wave 1" are the same constraint stated twice. |
| FR-4.6 | **SD** | WP-05 (wave 3 usually largest) and WP-06 (gaps indicate wave 3) are implementable as recorded observations, never as gates. |

### FR-5 Candidate lifecycle

| ID | Tier | Requirement |
|---|---|---|
| FR-5.1 | **EN** | Each candidate SHALL carry an explicit lifecycle state. |
| FR-5.2 | **EN** | States: **ENUMERATED** (window formed) → **GATED** (passed every *implementable* mandatory gate) → **MEASURED** (guideline measurements recorded). |
| FR-5.3 | **EN** | A fourth state **UNDECIDABLE** SHALL exist for candidates that pass every implementable gate but whose acceptance depends on a blocked gate. This is required by this project's actual situation: e.g. an Impulse whose IMP-06 comparison bars have `NaN` RSI(13) (FR-3.1a.6) is genuinely neither valid nor invalid, and collapsing that into either would misreport. |
| FR-5.4 | **EN** | There SHALL be **no INVALID/REJECTED state.** A candidate failing an implementable gate is simply never created. Rationale: the reference describes only what patterns *are*; it never describes a rejected pattern as an object. |
| FR-5.5 | **EN** | Later processing SHALL NOT mutate or delete a wave created by earlier processing. |

### FR-6 Determinism and purity

| ID | Tier | Requirement |
|---|---|---|
| FR-6.1 | **EN** | Identical input SHALL produce byte-identical serialized output across repeated runs. |
| FR-6.2 | **EN** | The engine SHALL be free of wall-clock time, randomness, and I/O. |
| FR-6.3 | **EN** | The engine SHALL NOT mutate its input DataFrame or pivot sequence. |

### FR-7 Serialization

| ID | Tier | Requirement |
|---|---|---|
| FR-7.1 | **EN** | Output SHALL be JSON-serializable with NaN/Inf normalized to null. |
| FR-7.2 | **EN** | Every emitted record SHALL carry its lifecycle state, so a consumer can distinguish GATED from UNDECIDABLE. |
| FR-7.3 | **EN** | Output SHALL carry an engine version string and the configuration used. |
| FR-7.4 | **SD** | Output SHALL NOT contain a confidence, probability, or score field. The reference states no weighting function anywhere — every ratio is given standalone, with no rule for combining ratios into a single number. Emitting one would be invention. |

---

## 8. Dependency chain — ✅ **BROKEN** *(revised 2026-08-09 after OQ-02 / OQ-03)*

The chain that blocked every structure through revisions 0.1–0.2 **is now cleared at the root.**
All six Impulse gates are specified, so the structures that depended on Impulse are no longer
blocked *by Impulse*.

```
  OQ-02 ✅  ──→  IMP-04  absolute price distance
  OQ-03 ✅  ──→  IMP-05  pivot-price interval overlap
  OQ-04 ✅  ──→  IMP-06  RSI(13) directional divergence
  IMP-01/02/03  already source-defined
        │
        ▼
  ✅ IMPULSE fully specified
        │
        ├──→ ✅ DIAGONALS   (LD-01/03, ED-01/03 — host + subdivision)   ⚠ OQ-15 permissiveness
        ├──→ ✅ ZIGZAG      (ZZ-01…04 — A and C now classifiable)       ⚠ OQ-19 disambiguation
        └──→ ✅ FLAT generic (FL-01/02 — 5-wave C now classifiable)
                  ├── ✅ Running Flat   (FLU-01 fully specified)
                  ├── ❌ Regular Flat   — OQ-09, OQ-10
                  └── ❌ Expanded Flat  — OQ-10
                        │
                        ▼
              DOUBLE / TRIPLE THREE — DT-03/TT-03 partially satisfied:
              the {zigzag, flat} branch is ✅ available; the
              "of smaller degree" nesting branch is ✅ OQ-18 RESOLVED (depth cap)

  TRIANGLE — never depended on Impulse; still ❌ OQ-12, OQ-13
  EXTENSION — still ❌ OQ-24 (and this keeps OQ-19 circular)
```

### 8.1 What is now unblocked

| Structure | Status | Caveat |
|---|---|---|
| **Impulse** | ✅ **Fully specified** — all 6 gates | — |
| **Leading / Ending Diagonal** | ✅ **All gates specified** (position + subdivision) | **OQ-15** open as a *permissiveness* concern, not a gate: with overlap explicitly non-gating and "wedge" unquantified, the detector may be very permissive. Quality question, your call. |
| **Zigzag** | ✅ **All gates specified** | **OQ-19** open: the reference's own impulse-vs-zigzag tiebreak at C = 161.8% depends on "extension" (OQ-24). Affects labelling preference, not gating. |
| **Flat (generic)** | ✅ **Gates specified** | — |
| **Running Flat** | ✅ **Fully specified** (FLU-01) | The only fully-specified flat subtype (FR-3.7.3) |
| **Regular Flat** | ❌ Blocked | **OQ-09** ("near"), **OQ-10** ("slightly beyond") |
| **Expanded Flat** | ❌ Blocked | **OQ-10** ("substantially beyond") |
| **Double / Triple Three** | ✅ **Implemented 2026-08-10** | OQ-18 resolved by a depth-1 cap (FR-3.9a). DT-02/TT-02's swing counts remain **OQ-26** — recorded, never gated. OQ-17 is not involved: the gate keys on the ladder's integer `scale`, not a named degree. |
| **Triangle** | ❌ Blocked | **OQ-12**, **OQ-13** — independent of Impulse throughout |
| **Impulse with Extension** | ❌ Blocked | **OQ-24** |
| **Motive Sequence** | ❌ Not implementable | **OQ-14** — excluded from v1 |

### 8.2 The input is now defined too — the core path is complete

**OQ-21 is resolved** (§4a): the engine detects its own pivots, independently of
`swing_identification.py` and `zigzag.py`, which it neither modifies nor consumes. Together with
the `close` series that OQ-04 added (FR-1.6), the engine's full input contract is now specified.

**The v1 core path is therefore complete end to end:**

```
price_data (OHLCV, already in the store)
      |
      v
  Pivot detector (SS4a)  ---- own implementation, no existing swing/zigzag code
      |
      v
  Impulse  ->  Diagonals / Zigzag / Flat (generic) / Running Flat
      |
      v
  Serializer  ->  API  ->  dedicated Elliott Wave tab + chart
```

**No rule gap remains on this path.** What is outstanding is one configuration choice (**D-13**:
threshold values, FR-1e.3) and two boundary confirmations (**D-02b**, **D-02c**).

**OQ-05** (Fibonacci tolerance) is deliberately *not* a blocker for classification: all 16
Fibonacci rules are non-gating measurements (FR-4.1). The engine can classify structures without
it; it simply cannot report whether a ratio "matches" (FR-4.2).

### 8.3 OQ-01 remains open — and is now purely a validation question

OQ-01 (does the grammar-based Mandatory/Guideline split hold?) is **still unresolved**. The
2026-08-09 decisions ruled out the blanket-non-gating answer and confirmed gating for IMP-06
specifically, but did not settle the general classification. It no longer blocks anything on the
critical path: every gate now in use has been individually confirmed or individually decided.
It matters for the *remaining* blocked rules, where the M/G call is still load-bearing.

## 9. Data model requirements

Specified as field contracts. **This is a specification, not code** — no types, classes, or
interfaces are being declared here for implementation.

### DM-1 Pivot

| Field | Type | Tier | Notes |
|---|---|---|---|
| `index` | int | EI | Bar position of the extreme in the source OHLCV frame |
| `confirm_index` | int | **EN** | Bar at which the reversal confirmed the pivot. **Always > `index`.** Consumers at bar *t* may use only pivots with `confirm_index <= t` (FR-1b.2). |
| `timestamp` | datetime | EI | For rendering and cross-referencing |
| `price` | float | EI | The bar's own extreme — `high` for a HIGH pivot, `low` for a LOW pivot (FR-1c.1) |
| `kind` | enum {high, low} | EI | Required for direction-aware rules |
| `scale` | int | **EN** | Which threshold in the ladder produced this pivot (FR-1c.3). **Not an Elliott degree** — see FR-1d.3 / OQ-17. |

**DM-1.1 [EN — OQ-21 RESOLVED]** — Pivots come from the engine's own detector, specified in §4a. No existing pivot/swing module is imported or consumed (FR-1f.2).

### DM-2 Wave

| Field | Type | Tier | Notes |
|---|---|---|---|
| `id` | stable string | EN | Deterministic; no randomness (FR-6.2) |
| `start_pivot`, `end_pivot` | Pivot ref | EI | Bounds of the leg |
| `label` | string \| null | SD | "1".."5", "A".."E", "W"/"X"/"Y"/"Z"; null until labelled |
| `structure_type` | string \| null | SD | Only from the reference's named set (§DM-4) |
| `degree` | int \| null | UD — OQ-17 | Assignment rule undefined |
| `degree_name` | string \| null | SD | From DEG-02's 9 names |
| `parent_id` | string \| null | EI | Hierarchy is implied by "subdivision of" wording throughout |
| `child_ids` | list[string] | EI | Same inference |
| `state` | enum | EN | FR-5.2 / FR-5.3 |
| `measurements` | map | SD | Recorded ratios (FR-4.1); never gates |
| `blocked_by` | list[OQ id] | EN | Which Open Questions prevented a decision — required by FR-5.3 so UNDECIDABLE is explainable rather than opaque |

**DM-2.1 [SD]** — There SHALL be **no** `confidence` / `score` / `probability` field (FR-7.4).
**DM-2.2 [SD]** — There SHALL be **no** `valid` / `violated_rules` field. A candidate failing an
implementable gate is never created (FR-5.4), so there is nothing for such a field to describe.

### DM-3 Analysis result (top level)

| Field | Type | Tier | Notes |
|---|---|---|---|
| `engine_version` | string | EN | |
| `config` | map | UD | Contents depend on unresolved parameters (§12, D-03) |
| `waves` | list[Wave] | EI | |
| `blocked_rules` | list[rule id] | EN | Which inventory rules were **not** evaluated on this run, and why. Makes the gap machine-readable instead of silent. |

### DM-4 Permitted structure_type values

**SD.** Exactly the reference's named structures, and nothing else:
`impulse` · `impulse_with_extension` · `leading_diagonal` · `ending_diagonal` · `zigzag` ·
`flat_regular` · `flat_expanded` · `flat_running` · `triangle` · `double_three` · `triple_three`.

**DM-4.1 [NI]** — `motive_sequence` is **excluded**: FR-3.5.1 (OQ-14).
**DM-4.2 [UD — OQ-12]** — `triangle` is listed but its inclusion in v1 is an open decision.

---

## 10. API requirements

### API-1 Endpoint

| ID | Tier | Requirement |
|---|---|---|
| API-1.1 | **EN** | One new read-only sub-resource: `GET /api/backtests/{backtest_id}/elliott-wave`. Follows the existing sub-resource convention (`/zigzag`, `/chart-patterns`, `/candlestick-patterns`). |
| API-1.2 | **EN** | It SHALL read `price_data` from the existing in-memory store and SHALL NOT re-run the backtest or re-fetch data. |
| API-1.3 | **EN** | 404 for an unknown/expired `backtest_id`, matching sibling endpoints. |
| API-1.4 | **EN — D-13 CLOSED** | The endpoint SHALL expose the pivot detector's `theta_base`, `ratio` and `scales` as optional query parameters, defaulting to the FR-1e.3 values. FR-1e.4's parity test applies. Any further parameters depend on OQ-05 and are out of v1. `max_combination_depth` is deliberately **not** exposed — it is capped at 1 by the ladder's expressive limit (FR-3.9a.1), so a caller-supplied value could only be wrong. |
| API-1.5 | **EN** | The response SHALL include `blocked_rules` (DM-3) so the client can honestly display what was not evaluated. |
| API-1.6 | **EN** | No existing endpoint's path, parameters, or response shape SHALL change. |
| API-1.7 | **EN** | `GET /api/backtests/{id}/report` SHALL NOT gain Elliott Wave parameters in v1 (§1.3). |

### API-2 Layering

| ID | Tier | Requirement |
|---|---|---|
| API-2.1 | **EN** | Existing three-layer separation SHALL be preserved: router (HTTP/params) → serializer (domain → JSON) → `src/` (domain math). No Elliott logic in the router; no FastAPI imports in `src/`. |
| API-2.2 | **EN** | The Elliott analysis module SHALL live under `src/analysis/` as a new, self-contained unit and SHALL NOT modify any existing analysis module. |

---

## 11. Frontend requirements

### FE-1 Dedicated tab

| ID | Tier | Requirement |
|---|---|---|
| FE-1.1 | **EN** | Elliott Wave SHALL be a **dedicated top-level tab** in `ResultsPage.tsx`, added after `✨ Strategy Optimizer` as the 9th tab. |
| FE-1.2 | **EN** | The only permitted edits to `ResultsPage.tsx` are: one import, one data query, one `<TabsTrigger>`, one `<TabsContent>`. |
| FE-1.3 | **EN** | Elliott Wave SHALL NOT be a checkbox, toggle, or overlay on any existing tab. |

### FE-2 Dedicated chart

| ID | Tier | Requirement |
|---|---|---|
| FE-2.1 | **EN** | A **new, standalone chart component** SHALL be created for the Elliott Wave tab. |
| FE-2.2 | **EN** | **`CandlestickChart.tsx` SHALL NOT be modified, extended, parameterized, or imported by the Elliott Wave chart.** The Price & Trades chart remains a plain Price & Trades chart. This is a hard boundary (§12). |
| FE-2.3 | **EN** | The Elliott chart SHALL be single-panel: candlesticks + Elliott structures only. No RSI, Stochastic, trade markers, or Swing/ZigZag overlay — those belong to Price & Trades. |
| FE-2.4 | **EN** | Rendering SHALL use the existing Plotly stack (`react-plotly.js`); no new charting dependency. |
| FE-2.5 | **EI** | Each structure SHALL render as a connected path through its own labelled legs in order, with each wave's label displayed at its terminal pivot. **Inference:** the reference's structures are defined as ordered sequences (1→2→3→4→5, A→B→C, W→X→Y); scattered independent markers would not convey the ordering that *is* the structure. |
| FE-2.6 | **EN** | Elliott structures SHALL use a colour identity distinct from the Swing/3-Leg palette used elsewhere, so the two systems are never visually confused. |

### FE-3 Honest display of blocked state

| ID | Tier | Requirement |
|---|---|---|
| FE-3.1 | **EN** | Candidates in **UNDECIDABLE** state SHALL be visually distinguishable from **GATED** ones, or excluded — but MUST NOT be presented as confirmed. |
| FE-3.2 | **EN** | The UI SHALL surface `blocked_rules`, so a user is never shown a partial analysis that looks complete. |
| FE-3.3 | **EN** | The UI SHALL NOT display a confidence value (FR-7.4) — there is nothing truthful to put in it. |

### FE-4 Types and client

| ID | Tier | Requirement |
|---|---|---|
| FE-4.1 | **EN** | New TypeScript interfaces SHALL be **added** to `lib/types.ts`; no existing interface modified. |
| FE-4.2 | **EN** | One new method SHALL be **added** to `lib/api.ts`; no existing method modified. |
| FE-4.3 | **EN** | `tsc --noEmit` SHALL pass with zero errors. |

---

## 12. Implementation boundaries

### 12.1 MUST NOT be modified

| Path | Reason |
|---|---|
| `src/analysis/swing_identification.py` | Standing instruction. Consumed by `src/backtesting/trade_quality.py`. **As of the OQ-21 resolution the Elliott package must neither modify NOR consume it** — no import, wrapper, subclass, or use of its return values (FR-1f.2). |
| `src/analysis/zigzag.py` | Standing instruction. Consumed by `api/serializers.py`, `api/report/charts.py`, and 29 regression tests. User-confirmed swing-numbering algorithm. **As of the OQ-21 resolution the Elliott package must neither modify NOR consume it** (FR-1f.2). |
| `web/src/components/charts/CandlestickChart.tsx` | FE-2.2. The Price & Trades chart stays a plain Price & Trades chart. |
| `api/report/charts.py`, `api/report/report.py` | Report integration is out of scope for v1 (§1.3). |
| `src/analysis/{indicators,chart_patterns,candlestick_patterns,regime}.py` | Unrelated shared infrastructure. |
| `src/backtesting/**`, `src/strategies/**`, `src/data/**`, `src/broker/**` | Elliott Wave is analysis + display only; it changes no trading behavior. |
| Existing API endpoints and their response shapes | API-1.6. |
| `tests/test_engine.py`, `tests/test_swing_zigzag_regression.py` | Existing regression baselines. |
| `docs/RELEASE_AUDIT.md`, `docs/VERIFICATION_REPORT.md`, `docs/RELEASE_NOTES.md`, `docs/SECURITY_AUDIT.md` | Historical records. |

### 12.2 MAY be created or additively changed

| Path | Change |
|---|---|
| New unit under `src/analysis/` | New Elliott module |
| `api/serializers.py` | **Add** one function |
| `api/routers/backtests.py` | **Add** one endpoint |
| `web/src/components/charts/` | **Add** one component |
| `web/src/lib/types.ts`, `web/src/lib/api.ts` | **Add** only |
| `web/src/features/backtest/ResultsPage.tsx` | FE-1.2's four additions only |
| `tests/` | New test files |
| `CLAUDE.md`, `CHANGELOG.md` | Documentation, once something ships |

---

## 13. Testing requirements

| ID | Tier | Requirement |
|---|---|---|
| TR-1 | **EN** | Every **implementable** mandatory gate SHALL have both a passing fixture and a fixture violating **only** that gate. Applies to: IMP-01, IMP-02, IMP-03, LD-01, LD-03, ED-01, ED-03, ZZ-01, ZZ-02, ZZ-03, ZZ-04, FL-01, FL-02, FLE-01, FLU-01, TRI-01, TRI-03, DT-01, DT-02, DT-04, TT-01, TT-02, TT-04. |
| TR-2 | **EN** | **Blocked-rule guard tests.** For every rule marked BLOCKED, a test SHALL assert it has **not** been silently implemented — e.g. no Fibonacci tolerance constant exists while OQ-05 is open; no "near"/"slightly"/"substantially" flat-subtype threshold exists while OQ-09/OQ-10 are open; no Fibonacci constant outside the one scoped DT-05/TT-05 ceiling exception; no "extension" magnitude test while OQ-24 is open. This is the primary defence against gaps being quietly filled with invented values. *(The OQ-02, OQ-03 and OQ-04 guards are retired — those rules are now specified and are covered by TR-2a/TR-2b.)* |
| TR-2b | **EN** | **IMP-04 / IMP-05 tests.** Fixtures SHALL cover: wave 3 longer than both siblings (pass); wave 3 shorter than both (fail); wave 3 shorter than exactly one (pass); wave 4 territory clear of wave 1 (pass); wave 4 territory overlapping wave 1 (fail); and both exact-equality boundary cases of FR-3.1b.8. A further test SHALL assert **no tolerance constant** is applied to either gate (FR-3.1b.7). |
| TR-2a | **EN** | **IMP-06 tests.** Fixtures SHALL cover all four outcomes of the resolved definition: divergence present (up), divergence present (down), price precondition met but RSI **not** diverging (gate fails, FR-3.1a.8), and RSI(13) `NaN` at a comparison bar (→ **UNDECIDABLE**, FR-3.1a.6). A further test SHALL assert **no tolerance constant** is applied to the RSI comparison (FR-3.1a.5). |
| TR-3 | **EN** | A test SHALL assert LD-02/ED-02 (wave 1/4 overlap) **never** gates — a fixture with overlap must still classify as a diagonal. This is explicitly source-defined (FR-3.3.1) and easy to regress. |
| TR-4 | **EN** | A test SHALL assert no output record carries a confidence/score/probability field (FR-7.4, DM-2.1). |
| TR-5 | **EN** | Determinism: identical input SHALL produce byte-identical output across ≥20 repeated runs. |
| TR-6 | **EN** | The 29 existing swing/zigzag regression tests and the 5 engine tests SHALL continue to pass **unmodified**. |
| TR-7 | **EN** | **Independence guard (hard).** A test SHALL assert that no module in the Elliott package imports or references `src.analysis.swing_identification`, `src.analysis.zigzag`, or any other existing pivot/swing detector — verified by inspecting each module's **actual bound names and its resolved import graph**, not by a source-text grep (which a rename or aliased import would defeat). The only permitted shared-analysis dependency is `indicators.calc_rsi` (FR-1f.3). |
| TR-7a | **EN** | **No-look-ahead test.** Truncating the input at bar *t* and re-running the detector SHALL reproduce exactly the pivots whose `confirm_index <= t`, with identical indices and prices (FR-1b.4). This is the single most important correctness test for the detector. |
| TR-7b | **EN** | **Cross-scale nesting measurement.** A test SHALL measure and report the actual containment rate between adjacent scales rather than assert containment (FR-1d.4), so a non-nesting assumption can never silently creep into hierarchy construction. |
| TR-8 | **EN** | Fixtures SHALL be deterministic (fixed seeds or hand-built), never live/网络 data. |
| TR-9 | **EN** | Every test SHALL cite the rule ID(s) it covers, so coverage against the 94-rule inventory is auditable. |
| TR-10 | **UD** | Frontend chart-rendering tests: this repo has **no** TS test infrastructure. Whether to add one is a Phase 4 decision (§14, D-06). |
| TR-11 | **EN** | New tests SHALL be wired into CI. **Note:** CI currently runs only `pytest tests/test_engine.py` — the 29 swing/zigzag regression tests are **not** in CI today. See §14, D-05. |

---

## 14. Open Questions — 5 resolved, 21 unresolved (OQ-25, OQ-26 added 2026-08-10)

**Revised 2026-08-09.** **OQ-02, OQ-03, OQ-04 and OQ-21 are RESOLVED by project decision**
(§6.1b, §6.1a, §4a). **The other 20 remain unresolved and none has been silently narrowed.**
OQ-01 is *partially constrained* by those decisions but is **not** resolved (§8.3). For each: the rules it affects, why the reference is
insufficient, and what it blocks.

| OQ | Affected rules | Why the reference is insufficient | What it blocks |
|---|---|---|---|
| **OQ-01** | All 94 | **STILL UNRESOLVED — now partially constrained.** Every structure block is headed "Guidelines"; the words *rule*, *must*, *mandatory* never appear as a classification. The M/G split in the inventory is inferred from grammar, not stated. The 2026-08-09 decisions ruled out the blanket-non-gating answer, but did **not** confirm the grammar-based split. See §8.3. | The definition of "gate" itself. Determines whether *anything* can reject a candidate. |
| ~~**OQ-02**~~ | IMP-04 | **✅ RESOLVED 2026-08-09 by project decision** — wave length is **absolute price distance** from pivot prices; %, log and bar-count measures rejected. Full definition: §6.1b. **The reference still says nothing on this**; tier EN, not SD. | *(was: impulse gate 4 — now specified)* |
| ~~**OQ-03**~~ | IMP-05 | **✅ RESOLVED 2026-08-09 by project decision** — territory is the **pivot-price interval**; violated iff wave 4's interval intersects wave 1's. Full-intrabar-range reading rejected. Full definition: §6.1b. **The reference still says nothing on this**; tier EN, not SD. | *(was: impulse gate 5 — now specified)* |
| ~~**OQ-04**~~ | IMP-06, WP-10 | **✅ RESOLVED 2026-08-09 by project decision** — RSI(13) directional comparison, IMP-06 stays mandatory. Full definition: §6.1a. **The reference still says nothing on this**; the resolution is a decision (tier EN), not source-defined behavior. | *(was: the entire §8 chain — now unblocked at this node)* |
| **OQ-05** | All 16 Fibonacci rules | **PRESERVED UNRESOLVED per instruction.** Every ratio is a discrete exact value, never a band. No tolerance stated anywhere. Exact float equality never matches real data. | All ratio matching (FR-4.2). Ratios may be *computed*, never *matched*. |
| **OQ-06** | IMP-F02 | "of wave 1-2" — net displacement start-of-1→end-of-2, or wave 1's length projected from end of wave 2? | Wave 3 ratio base |
| **OQ-07** | IMP-F04, FIB-06 | "inverse retracement" is used but never defined on the page. | Wave 5 target, basis 1 of 3 |
| **OQ-08** | IMP-F03, WP-07 | §3.1 says "14.6%, 23.6%, or 38.2% … but no more than 50%"; §4.3 says "typically less than 38.2%". Two sections, different numbers. Cap vs guideline unstated. | Wave 4 ratio; its interaction with IMP-05 |
| **OQ-09** | FLR-01 | "near" unquantified; paired ratio is a single point (90%) with no tolerance. | Regular Flat wave-B gate |
| **OQ-10** | FLR-02, FLE-02 | "slightly beyond" vs "substantially beyond" is the **only** Regular/Expanded discriminator; neither is quantified. | Regular vs Expanded Flat separation (FR-3.7.1) |
| **OQ-11** | FLR-F02, FLE-F02, FLU-F02 | "of wave AB" — net A→B displacement, len(A)+len(B), or len(A)? Undefined. | All three flat wave-C ratios |
| **OQ-12** | TRI-01…07 | No Fibonacci ratios, no rules for waves D/E, no variant discriminators; TRI-04 permits nearly any corrective. | Whether Triangle is in v1 at all (FR-3.8.1) |
| **OQ-13** | TRI-06 | "support" undefined; "every time frame" undefined in a single-timeframe backtest. Only place RSI is named as a requirement. | Triangle momentum gate |
| **OQ-14** | MS-01…03 | The motive-sequence **numbers are never stated on the page**. | Motive Sequence entirely → **NI**, excluded from v1 (FR-3.5.1, DM-4.1) |
| **OQ-15** | LD-02, ED-02 | Overlap is explicitly *not* a condition and "wedge shape" is unquantified — leaving position + subdivision as the only gates. | Whether a diagonal is distinguishable from a plain 5-leg move |
| **OQ-16** | LD-03, ED-03 | Identical permitted subdivision sets for both diagonals. | Leading vs Ending distinguishable only by host (FR-3.3.3) |
| **OQ-17** | DEG-03, DEG-04 | Only 2 of 9 degrees mapped to timeframes; no rule for assigning degree from data. | Degree assignment (FR-3.11.2) |
| ~~**OQ-18**~~ | DT-03, TT-03 | **RESOLVED 2026-08-10 by project decision** — capped at `max_combination_depth = 1`, derived from the ladder's expressive limit. The reference still states no depth; tier EN, not SD. | *(was: DT/TT gates — now specified)* |
| **OQ-19** | ZZ-F03 | The reference flags the C=161.8% ambiguity itself and offers "whether the third swing has extension" as tiebreak — but "extension" is undefined (OQ-24). **Circular.** | Zigzag-vs-impulse disambiguation |
| **OQ-20** | GEN-04, GEN-06 | **PRESERVED UNRESOLVED per instruction.** §5: corrective waves "move in three, but never in five". §1.6/§3.5: motive waves "can unfold in 3 waves". A 3-swing move is therefore both, with **no stated discriminator.** | The motive/corrective distinction at 3 swings — the reference's central modernization and central ambiguity |
| **OQ-26** | DT-02, TT-02 | **NEW 2026-08-10, UNRESOLVED.** The reference's swing arithmetic contradicts itself: DT-02 says WXY is a **7**-swing structure, while DT-04 ("X can be any corrective structure") plus GEN-06 ("correctives move in three") imply **9**. TT is the same: 11 requires X to be a single swing. | Whether swing count may gate. It does not — recorded as a measurement only, so neither statement is discarded. |
| **OQ-25** | LD-03, ED-03 | **NEW 2026-08-10, UNRESOLVED.** The reference constrains a diagonal's subdivision *shape* (5-3-5-3-5 / 3-3-3-3-3) but never defines how detector-scale legs combine into an Elliott sub-wave. Implemented readings: 'sub-wave is a five-wave' = 'the finer scale registers an impulse inside it'; 'sub-wave is a three-wave' = 'spans ≥2 finer legs'. Both are readings, not stated rules. | Which groupings count as valid diagonals. All consistent groupings are emitted as alternates; none is preferred. |
| ~~**OQ-21**~~ | All | **RESOLVED 2026-08-09 by project decision** — an independent, Elliott-specific detector (§4a) that neither modifies nor consumes the existing swing/zigzag modules. **The reference still says nothing on this**; the detector is 100% project engineering, tier EN. | *(was: the engine's entire input — now specified)* |
| **OQ-22** | WP-02/04/08/11/12/13, TRI-05 | All volume statements are qualitative, with no threshold or window. Volume is also **synthetic** on the default data source. | All volume rules (FR-4.3) |
| **OQ-23** | FLE-F01, FLU-F01 | Expanded and Running Flat state the **same** wave-B ratio (123.6%). | Wave B cannot separate them (FR-3.7.2) |
| **OQ-24** | EXT-01, EXT-02, ZZ-F03 | "extension" / "elongated" / "exaggerated subdivisions" — no numeric definition anywhere. | Extension detection entirely (FR-3.2.1); feeds OQ-19 |

---

## 14a. Residual sub-detail of the OQ-04 resolution

The resolution specified the indicator, the direction of comparison, the no-tolerance rule, and
the unavailable-data behavior. **One detail was left implicit**, recorded here rather than
silently chosen:

> The decision's wording says *"price **closes** beyond Wave 3's extreme"* while both other clauses
> speak of the *"extreme"*. For a high pivot the bar's **high** and its **close** are different
> prices, so the two phrasings can disagree on the same bar.

**FR-3.1a.7 adopts the pivot-price reading** — "extreme" means the terminal pivot's price (bar
high for a high pivot, bar low for a low pivot), with RSI(13) read at that same bar — because it
is self-consistent across all three clauses of the definition and matches how every other rule in
the inventory measures a wave boundary.

**This is flagged, not hidden.** If the close-price reading was intended, FR-3.1a.7 is the single
place to change (Phase 4 decision **D-02b**). It does not affect any other requirement.

### 14a.2 Exact-equality boundaries in IMP-04 and IMP-05 (D-02c)

The OQ-02 and OQ-03 decisions specify the measure and the comparison but not what happens at
exact equality. Two cases exist, and **FR-3.1b.8 adopts the literal reading of each**:

| Case | Literal reading adopted | Alternative |
|---|---|---|
| `len(wave 3) == min(len(1), len(5))` | Wave 3 **is** a shortest wave → **rejected** (strict `>`) | Treat "shortest" as *uniquely* shortest → ties pass (`>=`) |
| `territory(wave 4)` touches `territory(wave 1)` at exactly one price | Closed intervals intersect → **overlap → rejected** | Treat a bare touch as non-overlapping (half-open intervals) |

**These are not tolerances** — no buffer, epsilon, or threshold is introduced either way; the
question is purely which side of an exact boundary is inclusive.

**Why it is worth confirming:** futures prices are tick-quantised (ES trades in 0.25 increments),
so two waves having *identical* absolute length, or a wave-4 pivot landing *exactly* on wave 1's
endpoint, are reachable outcomes on real data — not floating-point curiosities. Both defaults are
the strict/conservative choice, meaning they reject rather than admit a borderline candidate.

**Confirm or overturn via D-02c.** FR-3.1b.8 is the single place to change.

---

## 15. Traceability — all 96 rules

Every rule ID from the inventory appears exactly once.

| Rules | Requirement | Tier | Blocking OQ |
|---|---|---|---|
| GEN-01 | — | SD | Informational only |
| GEN-02, GEN-03 | FR-2.2, DM-4 | SD | — |
| GEN-04, GEN-06 | — | UD | **OQ-20** |
| GEN-05, GEN-07 | FR-2.2, DM-4 | SD | — |
| DEG-01, DEG-02 | FR-3.11.1 | SD | — |
| DEG-03, DEG-04 | FR-3.11.2 | UD | OQ-17 |
| DEG-05 | — | SD | Informational only |
| FIB-01, FIB-02, FIB-03, FIB-04, FIB-05 | FR-4.1 | SD | — |
| FIB-06 | FR-3.1.2 | UD | OQ-07 |
| IMP-01, IMP-02 | FR-3.1 | SD | — |
| IMP-03 | FR-3.1, FR-4.5 | SD | — |
| IMP-04 | FR-3.1, FR-3.1b | EN | **OQ-02 RESOLVED** — absolute price distance |
| IMP-05 | FR-3.1, FR-3.1b | EN | **OQ-03 RESOLVED** — pivot-price interval overlap |
| IMP-06 | FR-3.1a | EN | **OQ-04 RESOLVED** — mandatory gate, RSI(13) directional comparison |
| IMP-F01, IMP-F02, IMP-F03, IMP-F04 | FR-3.1.2, FR-4.2 | UD | **OQ-05** (+OQ-06, OQ-07, OQ-08) |
| EXT-01, EXT-02 | FR-3.2 | UD | OQ-24 |
| EXT-03, EXT-04 | FR-3.2 | NI | — |
| LD-01, LD-03 | FR-3.3 | SD | — |
| LD-02 | FR-3.3.1 (non-gating), FR-3.3.2 | SD / UD | OQ-15 |
| ED-01, ED-03 | FR-3.4 | SD | — |
| ED-02 | FR-3.3.1 (non-gating), FR-3.3.2 | SD / UD | OQ-15 |
| MS-01, MS-02, MS-03 | FR-3.5.1 | **NI** | OQ-14 — **excluded from v1** |
| WP-01, WP-09 | FR-4.4 | SD | Prose only |
| WP-02, WP-04, WP-08, WP-11, WP-12, WP-13 | FR-4.3 | UD | OQ-22 |
| WP-03 | FR-4.5 | SD | Restates the impulse wave-2 constraint; implemented once |
| WP-05, WP-06, WP-14 | FR-4.6 | SD | — |
| WP-07 | FR-3.1.2 | UD | OQ-08 |
| WP-10 | FR-3.1a | EN | **OQ-04 RESOLVED** — prose definition operationalized as RSI(13) |
| ZZ-01, ZZ-02, ZZ-03, ZZ-04 | FR-3.6 | SD | — |
| ZZ-F01, ZZ-F02 | FR-4.2 | UD | **OQ-05** |
| ZZ-F03 | FR-3.6 | UD | OQ-19 |
| FL-01, FL-02 | FR-3.7 | SD | — |
| FLR-01 | FR-3.7 | UD | OQ-09 |
| FLR-02 | FR-3.7 | UD | OQ-10 |
| FLE-01 | FR-3.7 | SD | — |
| FLE-02 | FR-3.7 | UD | OQ-10 |
| FLU-01 | FR-3.7, FR-3.7.3 | SD | — |
| FLR-F01, FLR-F02, FLE-F01, FLE-F02, FLU-F01, FLU-F02 | FR-4.2 | UD | **OQ-05**, OQ-11, OQ-23 |
| TRI-01, TRI-02, TRI-03 | FR-3.8 | SD | — |
| TRI-04, TRI-07 | FR-3.8 | UD | OQ-12 |
| TRI-05 | FR-3.8, FR-4.3 | UD | OQ-22 |
| TRI-06 | FR-3.8 | UD | OQ-13 |
| DT-01, DT-04 | FR-3.9, FR-3.9a | SD | — |
| DT-05 | FR-3.9a | SD | **Newly extracted 2026-08-10** — ceiling, not blocked by OQ-05 |
| DT-03 | FR-3.9a | EN | **OQ-18 RESOLVED** — depth cap |
| DT-02 | FR-3.9a | UD | **OQ-26** |
| DT-F01, DT-F02 | FR-4.2 | UD | **OQ-05** |
| TT-01, TT-04 | FR-3.10, FR-3.9a | SD | — |
| TT-05 | FR-3.9a | SD | **Newly extracted 2026-08-10** — constrains wave Y, not Z |
| TT-03 | FR-3.9a | EN | **OQ-18 RESOLVED** — depth cap |
| TT-02 | FR-3.9a | UD | **OQ-26** |
| TT-F01, TT-F02 | FR-4.2 | UD | **OQ-05** |

### 15.1 Disposition totals

Counted directly from the matrix above, not restated from Phase 2:

| Disposition | Rules | Meaning |
|---|---|---|
| **SD / EN** — implementable now | 43 | 39 fully specified by the reference, **+4 specified by project decision** rather than by the reference: IMP-06 and WP-10 (OQ-04), IMP-04 (OQ-02), IMP-05 (OQ-03) |
| **SD / UD** — partially implementable | 2 | LD-02 and ED-02: the non-gating half is source-defined and buildable; the "wedge shape" half is blocked (OQ-15) |
| **UD** — blocked | 40 | Depends on an unresolved Open Question (44 → 42 after OQ-04, → 40 after OQ-02/OQ-03) |
| **NI** — not implementable | 5 | The reference is silent; cannot be built from this source |
| **Informational** — prose, no detector | 4 | GEN-01, DEG-05, WP-01, WP-09 |
| **Total** | **94** | Every rule ID accounted for exactly once |

**Both documents now agree.** `ELLIOTT_WAVE_RULES.md`'s coverage summary was recounted at the same
time and reports the identical 41 / 42 / 5 / 2 / 4 split. Three reconciliations were applied:

1. **§5.2 Flat contains 13 rules, not 12** (FL 2 + FLR 4 + FLE 4 + FLU 3). This single miscount
   in the Phase 2 summary table was the entire source of the earlier "93 vs 94" discrepancy. The
   row-level ID count was always 94; only that summary was wrong.
2. **EXT-03, EXT-04** were "Informational" in the inventory; here they are **NI**. They are not
   merely narrative — they state market-class priors, and building them would need both an
   instrument-class taxonomy (which this platform lacks) and probability values (which the
   reference never gives). "Cannot be built" is the accurate label.
3. Rules blocked by more than one Open Question are counted once, under UD.

**Effect of the three resolutions on these totals:** IMP-06 and WP-10 (OQ-04), then IMP-04
(OQ-02) and IMP-05 (OQ-03), moved from UD to implementable — 44 → 40 blocked, 39 → 43
implementable. No other rule's disposition changed; in particular the 16 Fibonacci rules remain
blocked on OQ-05, and no blocked rule was reclassified to make the totals look better.

---

## 16. Assumptions

Only three, all structural rather than Elliott-semantic, and all falsifiable:

| # | Assumption | Basis | If wrong |
|---|---|---|---|
| A-1 | The Elliott module is a **read-only analyser** — it never influences trades, signals, or backtest results. | §1.3; nothing in the reference concerns execution. | Scope changes materially; §12 boundaries would need revisiting. |
| A-2 | Analysis runs against a **completed** backtest's stored `price_data`, not live/streaming bars. | Matches every existing analysis sub-resource (`/zigzag`, `/chart-patterns`). | Would require a streaming interface; out of scope. |
| A-3 | v1 targets a **single timeframe** — whatever the backtest ran on. | The platform is single-timeframe per backtest. | TRI-06's "every time frame" would become addressable — but it is blocked by OQ-13 regardless. |

**No assumption has been made about any Elliott Wave rule.** Where the reference is silent, this
SRS says UNDEFINED rather than assuming.

---

## 17. Decisions Phase 4 (architecture) must make

| # | Decision | Depends on |
|---|---|---|
| **D-01** | Answer OQ-01 — what constitutes a gate, given the reference declares only "Guidelines". **Partially constrained** (blanket-non-gating ruled out, §8.3) but still **OPEN**. No longer on the critical path | — |
| ~~**D-02**~~ | ~~Answer OQ-04~~ — **✅ CLOSED 2026-08-09.** IMP-06 stays mandatory; divergence defined as an RSI(13) directional comparison (§6.1a) | — |
| ~~**D-02a**~~ | ~~Answer OQ-02 and OQ-03~~ — **✅ CLOSED 2026-08-09.** Absolute price distance; pivot-price interval overlap (§6.1b). **This broke the §8 chain.** | — |
| ~~**D-02c**~~ | ~~Confirm FR-3.1b.8~~ — **CLOSED 2026-08-09.** Reject-on-tie confirmed for both IMP-04 and IMP-05; no change made | — |
| ~~**D-02b**~~ | ~~Confirm FR-3.1a.7~~ — **CLOSED 2026-08-09.** Pivot-price reading confirmed; no change made | — |
| **D-03** | Answer OQ-05 — the tolerance model for all 16 Fibonacci rules; this also determines API query parameters (API-1.4) and enumeration bounds (FR-2.6) | — |
| ~~**D-04**~~ | ~~Answer OQ-21 — pivot source~~ — **CLOSED 2026-08-09.** Independent Elliott-specific detector; existing swing/zigzag modules neither modified nor consumed (§4a) | — |
| ~~**D-13**~~ | ~~Choose pivot threshold values~~ — **CLOSED 2026-08-09, REVISED 2026-08-10.** Now 0.10% / r=4.0 / S=4. Rev 1 (0.20% / 2.5) superseded after implementation showed it could never satisfy IMP-02 (ARCHITECTURE §5.6) | — |
| ~~**D-14**~~ | ~~IMP-02 recursion floor~~ — **✅ CLOSED 2026-08-09.** At scale 1 there is no finer scale, so IMP-02 resolves to **UNDECIDABLE**, never a silent pass/fail (ARCHITECTURE §5.3). Confirmed | — |
| **D-05** | Whether to extend CI beyond `test_engine.py` — the 29 swing/zigzag regression tests are currently **not** run in CI (TR-11) | — |
| **D-06** | Whether to introduce TypeScript test infrastructure for the new chart (TR-10) | — |
| **D-07** | Whether Elliott Wave ever appears in the exported HTML report — and if so, how to avoid the existing `CandlestickChart.tsx` ↔ `api/report/charts.py` duplication hazard (§1.3) | — |
| **D-08** | Answer OQ-12 — whether Triangle is in v1 scope, given its gates are near-vacuous (FR-3.8.1) | — |
| ~~**D-09**~~ | ~~Answer OQ-18~~ — **CLOSED 2026-08-10.** `max_combination_depth = 1`, derived from the ladder (ARCHITECTURE §6.7a) | — |
| **D-10** | Answer OQ-20 — how a 3-swing move is classified as motive vs corrective | D-01 |
| **D-11** | Build order, given §8. Now depends on **D-02a**, not D-02 | D-01, D-02a |
| **D-12** | Whether an UNDECIDABLE candidate is surfaced in the UI or withheld (FE-3.1). **More concrete now:** the OQ-04 resolution creates a real UNDECIDABLE path (RSI(13) warmup, FR-1.8), so this is no longer hypothetical | D-02a |

---

## 18. Documentation Summary

### Files created (1)

| File | Contents |
|---|---|
| `docs/ELLIOTT_WAVE_SRS.md` | This document — 20 sections (SS4a added), 132 tier-tagged requirement statements, full 94-rule traceability matrix, 20 Open Questions carried forward + 4 resolved, 15 Phase 4 decisions (D-02, D-02a, D-04 closed; D-02b/D-02c/D-13 open). |

### Files modified

**One:** `docs/ELLIOTT_WAVE_RULES.md` — OQ-04 marked RESOLVED with a new "OQ-04 resolution"
section; IMP-06 and WP-10 rows updated; coverage summary recounted (two corrections recorded
there); header revision note added. **No source file, configuration file, or test was changed.**

### Files deleted

**None.**

### Sections added

§1 Purpose and scope · §2 Definitions · §3 Requirement classification scheme (SD/EI/UD/NI + EN) ·
§4 Input requirements · §5 Candidate enumeration · §6 Structure classification (11 structures +
degree) · §7 Measurement, lifecycle, determinism, serialization · §8 Critical dependency chain ·
§9 Data model · §10 API requirements · §11 Frontend requirements (dedicated tab + dedicated
chart + honest blocked-state display) · §12 Implementation boundaries · §13 Testing requirements ·
§14 Open Questions carried forward · §15 Traceability · §16 Assumptions · §17 Phase 4 decisions ·
§18 this summary.

### Rules covered

**All 94 of 94.** Every rule ID appears exactly once in §15 — verified programmatically (no
omissions, no duplicates). Disposition, counted from the matrix (§15.1): **43** implementable
(39 source-defined + 4 specified by the OQ-02/03/04 decisions) · **2** partially implementable ·
**40** UD (blocked) · **5** NI · **4** informational. `ELLIOTT_WAVE_RULES.md` reports the
identical split.

### Open Questions preserved

**21 of 26 unresolved; OQ-02, OQ-03, OQ-04, OQ-18 and OQ-21 resolved by explicit project decision. OQ-25 and OQ-26 were added 2026-08-10.**

- **OQ-02, OQ-03** — RESOLVED (§6.1b). **OQ-04** — RESOLVED (§6.1a). **OQ-21** — RESOLVED (§4a).
  All four tagged **EN**, not SD: the reference contributes nothing to any of them, and each is
  recorded as a decision everywhere it appears.
- **OQ-01** — **still unresolved.** The decisions ruled out the blanket-non-gating answer, which
  *constrains* OQ-01 without answering it (§8.3). Deliberately not marked resolved.
- **OQ-05, OQ-20** — untouched, still marked *"PRESERVED UNRESOLVED per instruction"* in §14.
- The remaining 17 are unchanged.

No classical Elliott Wave knowledge was substituted for any gap, and **no Open Question beyond
the four named was resolved.**

### Implementation blockers

**Nothing now blocks Phase 4 from starting.** The v1 core path — pivot detection through
Impulse, Diagonals, Zigzag, generic Flat and Running Flat — has no remaining rule gap (§8.2).

**Outstanding on the core path (all Phase 4 items, none a rule gap):**

1. **D-13** — pivot threshold values (`theta_base`, ratio, scale count). Configuration, not a
   rule; the mechanism is fully specified without it (FR-1e.3).
2. **D-02b / D-02c** — two boundary confirmations (pivot-price vs close; exact-equality
   handling). One line each.

**Blocked and therefore OUT of the v1 core (each blocks only its own structure):**

3. **OQ-09 / OQ-10** — Regular and Expanded Flat remain indistinguishable. Running Flat is
   unaffected and stays in the core.
4. **OQ-12 / OQ-13** — Triangle's gates remain near-vacuous; scope decision required.
5. ~~**OQ-18**~~ — **RESOLVED.** Double/Triple Three implemented; the *nested* branch is
   missing; the {zigzag, flat} branch is available. A depth cap would close this.
6. **OQ-24** — Extension undefined; this also keeps OQ-19's zigzag/impulse tiebreak circular.
7. **OQ-05** — all 16 Fibonacci rules. **Not a classification blocker** — non-gating
   measurements; ratios computable, just not declarable as "matched".
8. **OQ-14** — Motive Sequence not implementable; excluded from v1.
9. **OQ-01** — still open, off the critical path (§8.3).

### Assumptions

Three, all structural, all listed in §16 (A-1 read-only analyser · A-2 completed backtest, not
streaming · A-3 single timeframe). **Zero assumptions about Elliott Wave semantics.**

### What Phase 4 architecture will need to decide

**Fifteen** decisions in §17; **D-02, D-02a and D-04 are now CLOSED.** No decision now blocks
Phase 4 from beginning. The first item Phase 4 should settle is **D-13** (pivot threshold values),
since every downstream behaviour is observed through it, followed by **D-11** (build order), which
is now answerable — the natural order falls out of §8.2's pipeline. **D-02b** and **D-02c** are
one-line confirmations. **D-03** (Fibonacci tolerance) affects reporting quality, not
classification, and can land later. **D-01**, **D-08** (Triangle scope) and **D-09** (recursion
depth) govern structures outside the v1 core and need not gate the start of Phase 4.
