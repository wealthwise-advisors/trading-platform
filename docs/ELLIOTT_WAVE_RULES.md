# Elliott Wave — Reference Rule Inventory

**Phase 2 deliverable.** Extracted 2026-08-09 from the single approved reference:
<https://elliottwave-forecast.com/elliott-wave-theory/> (Elliott Wave Forecast, "EWF").

This document is an **inventory of what the reference actually says** — not a design, not
a specification, and not an implementation plan. Nothing here has been implemented.

**Revision 2026-08-10:** **OQ-18 RESOLVED** — Double/Triple Three recursion capped at depth 1
([resolution](#oq-18-resolution--doubletriple-three-recursion-depth)). **DT-05 and TT-05 added** —
an extraction correction; both ceilings were missing from the first pass. **OQ-26 added**
(unresolved) — the reference's 7-vs-9 swing-count contradiction. Rule count 94 → **96**.

**Revision 2026-08-09:** pivot thresholds calibrated and **D-13 closed**
(θ_base 0.20%, r 2.5, S 4 — see [ARCHITECTURE](ELLIOTT_WAVE_ARCHITECTURE.md) §5);
**D-02b and D-02c confirmed closed** (pivot-price reading kept; reject-on-tie kept for both
IMP-04 and IMP-05 — no rule text changed).

**Four Open Questions RESOLVED by project decision:**
[OQ-02](#oq-02-resolution--wave-3-shortest-measure) (wave 3 "shortest" = absolute price distance),
[OQ-03](#oq-03-resolution--wave-4-price-territory) (wave 4 territory = pivot-price interval
overlap), [OQ-04](#oq-04-resolution--wave-5-momentum-divergence) (divergence = RSI(13) directional
comparison), and [OQ-21](#oq-21-resolution--elliott-specific-pivot-detection) (an independent,
Elliott-specific pivot detector that neither modifies **nor consumes** the existing swing/zigzag
modules). **All four are decisions, not source-defined behavior** — the reference contributes
nothing to any of them — and are labelled as such wherever they appear. *(OQ-18 has since been
resolved too, and OQ-26 added — see the 2026-08-10 revision above. Current standing: **5 of 26
resolved, 21 unresolved**.)* With OQ-02/03/04 settled, **all six Impulse gates are specified**;
with OQ-21 settled, **the engine now has a defined input**.

---

## How to read this document

### Scope and provenance

Every rule below traces to one numbered section of the reference page. The page's own
outline is:

| § | Title | § | Title |
|---|---|---|---|
| 1 | Elliott Wave Theory: Modern Theory for 21st Century Market | 3.4 | Ending Diagonal |
| 1.1 | What is Elliott Wave Theory? | 3.5 | Motive Sequence |
| 1.2 | Basic Principle of the 1930's Elliott Wave Theory | 4 | Waves Personality |
| 1.3 | The Five Waves Pattern (Motive and Corrective) | 4.1 | Wave 1 and wave 2 |
| 1.4 | Wave Degree | 4.2 | Wave 3 |
| 1.5 | The Rise of Algorithmic / Computer-Based Trading | 4.3 | Wave 4 |
| 1.6 | The New Elliott Wave Principle | 4.4 | Wave 5 |
| 2 | Fibonacci | 4.5 | Wave A, B, and C |
| 2.1–2.5 | Intro, Summation Series, Ratio Table, Retracement/Extension, Relation to EW | 5 | Corrective Waves |
| 3 | Motive Waves | 5.1 | Zigzag |
| 3.1 | Impulse | 5.2 | Flat (5.2.1 Regular, 5.2.2 Expanded, 5.2.3 Running) |
| 3.2 | Impulse with Extension | 5.3 | Triangles |
| 3.3 | Leading Diagonal | 5.4 | Double Three · 5.5 Triple Three |

### ⚠ Critical finding: the reference declares *no* mandatory rules

**The reference labels every single structure block "Guidelines".** It never uses the words
"rule", "mandatory", "required", or "must" as a classification. There is no rules-vs-guidelines
distinction in the source.

The **M/G** column below is therefore **my classification, not the reference's**, derived
purely from the grammar of each statement:

- **M (Mandatory)** — stated as an absolute negative or a definitional identity:
  *"can't"*, *"can not"*, *"does not"*, *"never"*, *"is X waves"*. Falsifiable from price alone.
- **G (Guideline)** — stated as typical/frequent/approximate: *"usually"*, *"typically"*,
  *"generally"*, *"frequently"*, *"should"*, *"can be"*, or any Fibonacci ratio.

This inference needs your sign-off before Phase 3 — see **OQ-01**.

### Column key

| Column | Meaning |
|---|---|
| **Input** | Data the rule needs. `pivots` = ordered wave-boundary pivots (bar index + price); `OHLC` = bar extremes; `vol` = volume; `mom` = a momentum oscillator series; `sub` = child-wave classification results; `deg` = assigned wave degree |
| **Measurement** | The computation the rule reduces to. `P(x)` = price at pivot x; `len(w)` = abs price length of wave w |
| **Fib** | Fibonacci relationship stated by the reference for that wave, verbatim |
| **Mom** | Momentum/volume requirement, if the reference states one |
| **Status** | Implementation status. All rules are currently **Not implemented** (fresh start); rules that cannot be implemented as written are marked **Blocked** with the blocking Open Question |

### Status legend

- **Not implemented** — extractable and implementable; no blocker
- **Blocked (OQ-nn)** — cannot be implemented as written; the reference is ambiguous or silent
- **Informational** — narrative/contextual; not a detector rule

---

## 1. General theory (§1)

| ID | Structure | Wave | Rule | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| GEN-01 | — | — | "the movement of the stock market could be predicted by observing and identifying a repetitive pattern of waves" | G | — | — | — | — | 1.1 | Informational |
| GEN-02 | Motive | — | "the traditional definition of motive wave is a 5 wave move in the same direction as the trend of one larger degree" | M | pivots, deg | count of legs == 5; direction == parent direction | — | — | 3 | Not implemented |
| GEN-03 | Motive | — | "There are three different variations of a 5 wave move which is considered a motive wave: Impulse wave, Impulse with extension, and diagonal" | M | sub | classification ∈ {impulse, impulse-with-extension, diagonal} | — | — | 3 | Not implemented |
| GEN-04 | Motive | — | EWF revision: "motive waves do not have to be in 5 waves… motive waves can unfold in 3 waves. For this reason, we prefer to call it motive sequence" | G | pivots | leg count ∈ {3, 5} | — | — | 1.6, 3.5 | Blocked (OQ-20) |
| GEN-05 | Corrective | — | "waves that move against the trend of one greater degree" | M | pivots, deg | direction != parent direction | — | — | 5 | Not implemented |
| GEN-06 | Corrective | — | "Corrective waves are probably better defined as waves that move in three, but never in five" | M | pivots | leg count == 3 (never 5) | — | — | 5 | Blocked (OQ-20) |
| GEN-07 | Corrective | — | Five corrective types exist: Zigzag (5-3-5), Flat (3-3-5), Triangle (3-3-3-3-3), Double Three, Triple Three | M | sub | classification ∈ the five | — | — | 5 | Not implemented |

## 2. Wave Degree (§1.4)

| ID | Structure | Wave | Rule | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| DEG-01 | — | — | "Elliott acknowledged 9 degrees of waves" | M | deg | degree count == 9 | — | — | 1.4 | Not implemented |
| DEG-02 | — | — | Degree names, largest→smallest: Grand Super Cycle, Super Cycle, Cycle, Primary, Intermediate, Minor, Minute, Minuette, Subminuette | M | deg | name lookup | — | — | 1.4 | Not implemented |
| DEG-03 | — | — | "Grand Super Cycle degree… is usually found in weekly and monthly time frame" | G | deg, timeframe | timeframe ∈ {W, M} → GSC | — | — | 1.4 | Blocked (OQ-17) |
| DEG-04 | — | — | "Subminuette degree which is found in the hourly time frame" | G | deg, timeframe | timeframe == 1h → Subminuette | — | — | 1.4 | Blocked (OQ-17) |
| DEG-05 | — | — | Degree exists to "identify position of a wave within overall progress of the market" | G | — | — | — | — | 1.4 | Informational |

**Gap:** the reference maps only 2 of 9 degrees to timeframes, and gives **no rule at all** for
assigning a degree from price data. See **OQ-17**.

## 3. Fibonacci (§2)

| ID | Structure | Wave | Rule | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| FIB-01 | — | — | Summation series: "0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89 to infinity" | M | — | Fₙ = Fₙ₋₁ + Fₙ₋₂ | — | — | 2.2 | Not implemented |
| FIB-02 | — | — | 0.618 = "dividing any Fibonacci number… by another Fibonacci number that immediately follows it" | M | — | Fₙ / Fₙ₊₁ | 0.618 | — | 2.2 | Not implemented |
| FIB-03 | — | — | 0.382 = "dividing any Fibonacci number… by another… two places to the right" | M | — | Fₙ / Fₙ₊₂ | 0.382 | — | 2.2 | Not implemented |
| FIB-04 | — | — | 1.618 (Golden Ratio) = "dividing any Fibonacci number… by another… 1 place to the left" | M | — | Fₙ / Fₙ₋₁ | 1.618 | — | 2.2 | Not implemented |
| FIB-05 | — | — | Additional ratios referenced on the page: 0.236, 0.764, 1.236, 2.618 | M | — | — | 0.236 / 0.764 / 1.236 / 2.618 | — | 2.3 | Not implemented |
| FIB-06 | — | — | "Wave 3 is typically 161.8% of wave 1"; "Wave 5 is typically inverse 1.236 – 1.618% of wave 4, equal to wave 1 or 61.8% of wave 1+3" | G | pivots | see IMP-F02 / IMP-F04 | — | — | 2.5 | Blocked (OQ-07) |

**Note:** every Fibonacci relationship in the reference is a **discrete set of exact values**
(e.g. "50%, 61.8%, 76.4%, or 85.4%"), never a band. No tolerance is stated anywhere. See **OQ-05**.

---

## 4. Impulse (§3.1)

**Reference heading: "Guidelines"**

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| IMP-01 | Impulse | all | "Impulse wave subdivide into 5 waves." | M | pivots | leg count == 5 | — | — | 3.1 | Not implemented |
| IMP-02 | Impulse | 1, 3, 5 | "Wave 1, 3, and 5 subdivision are impulse." | M | sub | sub(1), sub(3), sub(5) each classify as impulse | — | — | 3.1 | Not implemented |
| IMP-03 | Impulse | 2 | "Wave 2 can't retrace more than the beginning of wave 1" | **M** | pivots | up: P(end 2) > P(start 1); down: P(end 2) < P(start 1) | — | — | 3.1 | Not implemented |
| IMP-04 | Impulse | 3 | "Wave 3 can not be the shortest wave of the three impulse waves, namely wave 1, 3, and 5" | **M** | pivots | **absolute price distance**: len(w) = \|P(end w) − P(start w)\|; requires len(3) > min(len(1), len(5)) | — | — | 3.1 | **Specified — OQ-02 RESOLVED 2026-08-09** |
| IMP-05 | Impulse | 4 | "Wave 4 does not overlap with the price territory of wave 1" | **M** | pivots | **pivot-price interval overlap**: territory(w1) = [min(P(start 1), P(end 1)), max(…)]; violated iff wave 4's own pivot-price interval intersects it | — | — | 3.1 | **Specified — OQ-03 RESOLVED 2026-08-09** |
| IMP-06 | Impulse | 5 | "Wave 5 needs to end with momentum divergence" | **M** | pivots, close series | P(end w5) beyond P(end w3) **AND** RSI(13)@w5-extreme not beyond RSI(13)@w3-extreme (direction-aware) | — | **RSI(13) divergence** | 3.1 | **Specified — OQ-04 RESOLVED 2026-08-09** |

### Impulse — Fibonacci Ratio Relationship (§3.1)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| IMP-F01 | Impulse | 2 | "Wave 2 is 50%, 61.8%, 76.4%, or 85.4% of wave 1" | G | pivots | len(2) / len(1) | 50 / 61.8 / 76.4 / 85.4 % | — | 3.1 | Blocked (OQ-05) |
| IMP-F02 | Impulse | 3 | "Wave 3 is 161.8%, 200%, 261.8%, or 323.6% of wave 1-2" | G | pivots | len(3) / len(wave 1-2) | 161.8 / 200 / 261.8 / 323.6 % | — | 3.1 | Blocked (OQ-05, OQ-06) |
| IMP-F03 | Impulse | 4 | "Wave 4 is 14.6%, 23.6%, or 38.2% of wave 3 but no more than 50%" | G + cap | pivots | len(4) / len(3) | 14.6 / 23.6 / 38.2 %, hard cap 50% | — | 3.1 | Blocked (OQ-05, OQ-08) |
| IMP-F04 | Impulse | 5 | "Wave 5 is inverse 123.6 – 161.8% retracement of wave 4. Second, wave 5 is equal to wave 1. Third, wave 5 is 61.8% of wave 1-3" | G (3 alternative bases) | pivots | three independent targets | 123.6–161.8% of w4 (inverse) · 100% of w1 · 61.8% of w1-3 | — | 3.1 | Blocked (OQ-07) |

**IMP-F04 is the only Fibonacci relationship in the entire reference given as a *range*
(123.6–161.8%) rather than a discrete set.**

## 5. Impulse with Extension (§3.2)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| EXT-01 | Impulse+Ext | 1/3/5 | "Impulses usually have an extension in one of the motive waves (either wave 1, 3, or 5)" | G | pivots | exactly one of w1/w3/w5 is "extended" | — | — | 3.2 | Blocked (OQ-24) |
| EXT-02 | Impulse+Ext | — | "Extensions are elongated impulses with exaggerated subdivisions" | G | pivots, sub | length + subdivision-count vs siblings | — | — | 3.2 | Blocked (OQ-24) |
| EXT-03 | Impulse+Ext | 3 | "Extensions frequently occur in the third wave in the stock market and forex market" | G | pivots, instrument class | prior probability by market | — | — | 3.2 | Informational |
| EXT-04 | Impulse+Ext | 5 | "Commodities market commonly develop extensions in the fifth wave" | G | pivots, instrument class | prior probability by market | — | — | 3.2 | Informational |

**No Fibonacci ratios are stated for extensions.** No numeric definition of "extended" is given.

## 6. Leading Diagonal (§3.3)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| LD-01 | Leading Diagonal | — | "appears as subdivision of wave 1 in an impulse or subdivision of wave A in a zigzag" | **M** | pivots, sub | host label ∈ {impulse w1, zigzag wA} | — | — | 3.3 | Not implemented |
| LD-02 | Leading Diagonal | 1, 4 | "usually characterized by overlapping wave 1 and 4 and also by the wedge shape **but overlap between wave 1 and 4 is not a condition, it may or may not happen**" | G (explicitly non-gating) | pivots | overlap(w1, w4) — recorded, never gates | — | — | 3.3 | Blocked (OQ-15) |
| LD-03 | Leading Diagonal | all | "The subdivision of a leading diagonal can be 5-3-5-3-5 or 3-3-3-3-3." | **M** | sub | subdivision pattern ∈ {5-3-5-3-5, 3-3-3-3-3} | — | — | 3.3 | Not implemented |

## 7. Ending Diagonal (§3.4)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| ED-01 | Ending Diagonal | — | "appears as subdivision of wave 5 in an impulse or subdivision of wave C in a zigzag" | **M** | pivots, sub | host label ∈ {impulse w5, zigzag wC} | — | — | 3.4 | Not implemented |
| ED-02 | Ending Diagonal | 1, 4 | "usually characterized by overlapping wave 1 and 4 and also by the wedge shape. **However, overlap between wave 1 and 4 is not a condition and it may or may not happen**" | G (explicitly non-gating) | pivots | overlap(w1, w4) — recorded, never gates | — | — | 3.4 | Blocked (OQ-15) |
| ED-03 | Ending Diagonal | all | "The subdivision of an ending diagonal is either 3-3-3-3-3 or 5-3-5-3-5" | **M** | sub | subdivision pattern ∈ {3-3-3-3-3, 5-3-5-3-5} | — | — | 3.4 | Not implemented |

**LD-03 and ED-03 permit the identical two subdivision sets.** Leading and Ending Diagonal are
therefore distinguished *only* by host position (LD-01 vs ED-01). See **OQ-16**.

## 8. Motive Sequence (§3.5)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| MS-01 | Motive Sequence | — | "We define a motive sequence simply as an incomplete sequence of waves (swings)" | M | pivots | swing count | — | — | 3.5 | Blocked (OQ-14) |
| MS-02 | Motive Sequence | — | "The structure of the waves can be corrective, but the sequence of the swings will be able to tell us whether the move is over" | G | pivots, sub | swing count vs sequence membership | — | — | 3.5 | Blocked (OQ-14) |
| MS-03 | Motive Sequence | — | "Motive sequence is much like the Fibonacci number sequence. If we discover the number of swings on the chart is one of the numbers in the motive sequence, then we can expect the current trend to extend further." | G | pivots | swing_count ∈ motive_sequence | — | — | 3.5 | **Blocked (OQ-14) — sequence numbers never stated** |

## 9. Wave Personality (§4)

All of §4 is descriptive. None of it is stated as a gating condition. Included for completeness
because several entries carry the reference's only volume and momentum statements.

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| WP-01 | Impulse | 1 | "Wave one is rarely obvious at its inception… the fundamental news is almost universally negative." | G | — | — | — | — | 4.1 | Informational |
| WP-02 | Impulse | 1 | "Volume might increase a bit as prices rise, but not by enough to alert many technical analysts" | G | vol | vol(w1) trend | — | volume | 4.1 | Blocked (OQ-22) |
| WP-03 | Impulse | 2 | "Wave two corrects wave one, but can never extend beyond the starting point of wave one." | **M** | pivots | duplicate of IMP-03 | — | — | 4.1 | Not implemented |
| WP-04 | Impulse | 2 | "volume should be lower during wave two than during wave one" | G | vol | mean vol(w2) < mean vol(w1) | — | volume | 4.1 | Blocked (OQ-22) |
| WP-05 | Impulse | 3 | "Wave three is usually the largest and most powerful wave in a trend" | G | pivots | len(3) vs len(1), len(5) | — | — | 4.2 | Not implemented |
| WP-06 | Impulse | 3 | "Gaps are a good indication of a Wave 3 in progress" | G | OHLC | gap detection within w3 | — | — | 4.2 | Not implemented |
| WP-07 | Impulse | 4 | "wave four typically retraces less than 38.2% of wave three" | G | pivots | len(4)/len(3) < 0.382 | 38.2% | — | 4.3 | Blocked (OQ-08) |
| WP-08 | Impulse | 4 | "Volume is well below than that of wave three" | G | vol | mean vol(w4) ≪ mean vol(w3) | — | volume | 4.3 | Blocked (OQ-22) |
| WP-09 | Impulse | 5 | "Wave five is the final leg in the direction of the dominant trend." | G | — | — | — | — | 4.4 | Informational |
| WP-10 | Impulse | 5 | "Many momentum indicators start to show divergences (prices reach a new high but the indicators do not reach a new peak)." | G | pivots, close series | **the reference's only prose definition of divergence** — operationalized as RSI(13) by the OQ-04 resolution | — | **RSI(13) divergence** | 4.4 | **Specified — OQ-04 RESOLVED 2026-08-09** |
| WP-11 | Impulse | 5 | "Volume is often lower in wave five than in wave three" | G | vol | mean vol(w5) < mean vol(w3) | — | volume | 4.4 | Blocked (OQ-22) |
| WP-12 | Zigzag/Flat | A | "In wave A of a bear market, the fundamental news is usually still positive… Some technical indicators that accompany wave A include increased volume." | G | vol | vol(wA) rising | — | volume | 4.5 | Blocked (OQ-22) |
| WP-13 | Zigzag/Flat | B | "The volume during wave B should be lower than in wave A." | G | vol | mean vol(wB) < mean vol(wA) | — | volume | 4.5 | Blocked (OQ-22) |
| WP-14 | Zigzag/Flat | C | "Prices move impulsively lower in five waves. Volume picks up" | G | sub, vol | sub(wC) == impulse; vol rising | — | volume | 4.5 | Not implemented |

**WP-10 is the only place the reference defines what "momentum divergence" means** — and it
defines it only in words, with no named indicator, period, or threshold. IMP-06 depends on it.
That gap was **OQ-04**, now **resolved by decision** (not by the reference) — see the
[OQ-04 resolution](#oq-04-resolution--wave-5-momentum-divergence) section below.

---

## 10. Zigzag (§5.1)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| ZZ-01 | Zigzag | all | "Zigzag is a corrective 3 waves structure labelled as ABC" | **M** | pivots | leg count == 3 | — | — | 5.1 | Not implemented |
| ZZ-02 | Zigzag | A, C | "Subdivision of wave A and C is 5 waves, either impulse or diagonal" | **M** | sub | sub(A), sub(C) ∈ {impulse, diagonal}, each 5 legs | — | — | 5.1 | Not implemented |
| ZZ-03 | Zigzag | B | "Wave B can be any corrective structure" | **M** (permissive) | sub | sub(B) ∈ any corrective | — | — | 5.1 | Not implemented |
| ZZ-04 | Zigzag | all | "Zigzag is a 5-3-5 structure" | **M** | sub | subdivision pattern == 5-3-5 | — | — | 5.1 | Not implemented |
| ZZ-F01 | Zigzag | B | "Wave B = 50%, 61.8%, 76.4% or 85.4% of wave A" | G | pivots | len(B)/len(A) | 50 / 61.8 / 76.4 / 85.4 % | — | 5.1 | Blocked (OQ-05) |
| ZZ-F02 | Zigzag | C | "Wave C = 61.8%, 100%, or 123.6% of wave A" | G | pivots | len(C)/len(A) | 61.8 / 100 / 123.6 % | — | 5.1 | Blocked (OQ-05) |
| ZZ-F03 | Zigzag | C | "If wave C = 161.8% of wave A, wave C can be a wave 3 of a 5 waves impulse. Thus, one way to label between ABC and impulse is whether the third swing has extension or not" | G (disambiguator) | pivots | len(C)/len(A) ≈ 161.8% → prefer impulse reading | 161.8% | — | 5.1 | Blocked (OQ-19) |

## 11. Flat — general (§5.2)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| FL-01 | Flat | all | A flat is a 3-wave (ABC) move with a **3-3-5** structure | **M** | sub | subdivision pattern == 3-3-5 | — | — | 5.2 | Not implemented |
| FL-02 | Flat | A | Flat differs from zigzag in wave A's subdivision (A is 3 waves, not 5) | **M** | sub | sub(A) leg count == 3 | — | — | 5.2 | Not implemented |

### 11.1 Regular Flat (§5.2.1)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| FLR-01 | Regular Flat | B | "Wave B terminates near the start of wave A" | G | pivots | \|P(end B) − P(start A)\| small | — | — | 5.2.1 | Blocked (OQ-09) |
| FLR-02 | Regular Flat | C | "Wave C generally terminates slightly beyond the end of wave A" | G | pivots | P(end C) beyond P(end A), by a small amount | — | — | 5.2.1 | Blocked (OQ-10) |
| FLR-F01 | Regular Flat | B | "Wave B = 90% of wave A" | G | pivots | len(B)/len(A) | **90%** (single value) | — | 5.2.1 | Blocked (OQ-05) |
| FLR-F02 | Regular Flat | C | "Wave C = 61.8%, 100%, or 123.6% of wave AB" | G | pivots | len(C)/len(AB) | 61.8 / 100 / 123.6 % | — | 5.2.1 | Blocked (OQ-05, OQ-11) |

### 11.2 Expanded Flat (§5.2.2)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| FLE-01 | Expanded Flat | B | "Wave B of the 3-3-5 pattern terminates beyond the starting level of wave A" | **M** | pivots | P(end B) beyond P(start A) | — | — | 5.2.2 | Not implemented |
| FLE-02 | Expanded Flat | C | "Wave C ends substantially beyond the ending level of wave A" | G | pivots | P(end C) beyond P(end A), substantially | — | — | 5.2.2 | Blocked (OQ-10) |
| FLE-F01 | Expanded Flat | B | "Wave B = 123.6% of wave A" | G | pivots | len(B)/len(A) | **123.6%** (single value) | — | 5.2.2 | Blocked (OQ-05, OQ-23) |
| FLE-F02 | Expanded Flat | C | "Wave C = 123.6% – 161.8% of wave AB" | G | pivots | len(C)/len(AB) | 123.6–161.8% (range) | — | 5.2.2 | Blocked (OQ-11) |

### 11.3 Running Flat (§5.2.3)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| FLU-01 | Running Flat | C | "Wave C fails travel the full distance, falling short of the level where wave A ended" | **M** | pivots | P(end C) does NOT reach P(end A) | — | — | 5.2.3 | Not implemented |
| FLU-F01 | Running Flat | B | "Wave B = 123.6% of wave A" | G | pivots | len(B)/len(A) | **123.6%** (single value) | — | 5.2.3 | Blocked (OQ-05, OQ-23) |
| FLU-F02 | Running Flat | C | "Wave C = 61.8% – 100% of wave AB" | G | pivots | len(C)/len(AB) | 61.8–100% (range) | — | 5.2.3 | Blocked (OQ-11) |

**Flat subtype discrimination summary** — the only *non-Fibonacci* discriminators the reference
gives are the wave-B and wave-C termination tests:

| Subtype | Wave B vs start of A | Wave C vs end of A | Wave B Fib |
|---|---|---|---|
| Regular | terminates **near** it | **slightly beyond** it | 90% |
| Expanded | terminates **beyond** it | **substantially beyond** it | 123.6% |
| Running | (not stated) | **falls short of** it | 123.6% |

Expanded and Running share an identical wave-B ratio (**OQ-23**), and "near" / "slightly" /
"substantially" are never quantified (**OQ-09**, **OQ-10**).

## 12. Triangle (§5.3)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| TRI-01 | Triangle | all | "Corrective structure labelled as ABCDE" | **M** | pivots | leg count == 5 | — | — | 5.3 | Not implemented |
| TRI-02 | Triangle | — | "Usually happens in wave B or wave 4" | G | pivots, sub | host label ∈ {B, 4} | — | — | 5.3 | Not implemented |
| TRI-03 | Triangle | all | "Subdivided into three (3-3-3-3-3)" | **M** | sub | every leg subdivides into 3 | — | — | 5.3 | Not implemented |
| TRI-04 | Triangle | A–E | "Subdivision of ABCDE can be either abc, wxy, or flat" | **M** (permissive) | sub | each leg ∈ {abc, wxy, flat} | — | — | 5.3 | Blocked (OQ-12) |
| TRI-05 | Triangle | — | "A triangle is a sideways movement that is associated with decreasing volume and volatility" | G | OHLC, vol | vol and range both contracting | — | volume | 5.3 | Blocked (OQ-22) |
| TRI-06 | Triangle | — | "RSI also needs to support the triangle in every time frame" | G | mom (RSI) | undefined | — | **RSI** | 5.3 | Blocked (OQ-13) |
| TRI-07 | Triangle | — | Variants named: ascending, descending, contracting, expanding | G | pivots | trendline slopes of A-C-E and B-D | — | — | 5.3 | Blocked (OQ-12) |

**No Fibonacci ratios are stated for any triangle wave.** No rule for wave D or wave E
individually. TRI-04's permitted set covers nearly every corrective structure, so it does almost
no discriminating work. See **OQ-12** — Triangle is the weakest-specified structure in the
reference by a wide margin.

## 13. Double Three (§5.4)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| DT-01 | Double Three | all | "Double three is a sideways combination of two corrective patterns" labelled **WXY** | **M** | pivots | leg count == 3 (W, X, Y) | — | — | 5.4 | Not implemented |
| DT-02 | Double Three | all | 7-swing structure | **M** | pivots | total sub-swing count == 7 | — | — | 5.4 | Not implemented |
| DT-03 | Double Three | W, Y | "Wave W and wave Y subdivision can be zigzag, flat, double three of smaller degree, or triple three of smaller degree" | **M** | sub, deg | sub(W), sub(Y) ∈ {zigzag, flat, DT(−1 deg), TT(−1 deg)} | — | — | 5.4 | **Specified 2026-08-10** — OQ-18 resolved (depth cap) |
| DT-04 | Double Three | X | "Wave X can be any corrective structure" | **M** (permissive) | sub | sub(X) ∈ any corrective | — | — | 5.4 | Not implemented |
| DT-F01 | Double Three | X | "Wave X = 50%, 61.8%, 76.4%, or 85.4% of wave W" | G | pivots | len(X)/len(W) | 50 / 61.8 / 76.4 / 85.4 % | — | 5.4 | Blocked (OQ-05) |
| DT-F02 | Double Three | Y | "Wave Y = 61.8%, 100%, or 123.6% of wave W" | G | pivots | len(Y)/len(W) | 61.8 / 100 / 123.6 % | — | 5.4 | Blocked (OQ-05) |
| DT-05 | Double Three | Y | **"Wave Y can not pass 161.8% of wave W"** | **M** | pivots | len(Y) <= 1.618 × len(W) | 161.8% (ceiling) | — | 5.4 | **Specified 2026-08-10** — added by the extraction correction below |

## 14. Triple Three (§5.5)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| TT-01 | Triple Three | all | "Triple three is a sideways combination of three corrective patterns" labelled **WXYXZ** | **M** | pivots | leg count == 5 (W, X, Y, X, Z) | — | — | 5.5 | Not implemented |
| TT-02 | Triple Three | all | 11-swing structure | **M** | pivots | total sub-swing count == 11 | — | — | 5.5 | Not implemented |
| TT-03 | Triple Three | W, Y, Z | "Wave W, wave Y, and wave Z subdivision can be zigzag, flat, double three of smaller degree, or triple three of smaller degree" | **M** | sub, deg | sub(W/Y/Z) ∈ {zigzag, flat, DT(−1 deg), TT(−1 deg)} | — | — | 5.5 | **Specified 2026-08-10** — OQ-18 resolved (depth cap) |
| TT-04 | Triple Three | X (both) | "Wave X can be any corrective structure" | **M** (permissive) | sub | sub(X) ∈ any corrective | — | — | 5.5 | Not implemented |
| TT-F01 | Triple Three | X | "Wave X = 50%, 61.8%, 76.4%, or 85.4% of wave W" | G | pivots | len(X)/len(W) | 50 / 61.8 / 76.4 / 85.4 % | — | 5.5 | Blocked (OQ-05) |
| TT-F02 | Triple Three | Z | "Wave Z = 61.8%, 100%, or 123.6% of wave W" | G | pivots | len(Z)/len(W) | 61.8 / 100 / 123.6 % | — | 5.5 | Blocked (OQ-05) |
| TT-05 | Triple Three | **Y** | **"Wave Y can not pass 161.8% of wave W or it can become an impulsive wave 3"** | **M** | pivots | len(Y) <= 1.618 × len(W) | 161.8% (ceiling) | — | 5.5 | **Specified 2026-08-10** — constrains wave **Y**, not Z |

**Note:** the reference states no *discrete ratio set* for wave **Y** in a Triple Three (only X
and Z), and none for the **second** X. Asymmetry is in the source, not a transcription error.
Wave Y is nonetheless constrained — by the TT-05 ceiling.

> ### ⚠ Extraction correction, 2026-08-10
>
> **DT-05 and TT-05 were missing from the original Phase 2 inventory.** The reference states
> *"Wave Y can not pass 161.8% of wave W"* (§5.4) and *"Wave Y can not pass 161.8% of wave W or it
> can become an impulsive wave 3"* (§5.5); the first pass recorded only the discrete
> 61.8/100/123.6% sets alongside them and missed both ceilings. Found by re-verifying the source
> before implementing Double/Triple Three.
>
> Both are **mandatory** ("can not"), and — importantly — **neither is blocked by OQ-05**. Every
> other Fibonacci rule is a discrete value needing a tolerance to match; these are one-sided
> **inequalities**, which need none. They are implemented exactly as written.
>
> Note TT-05 constrains wave **Y**, not wave Z. That is what the page says.

---

## Open Questions

The reference is ambiguous, silent, or self-conflicting on each of these. **Per the Phase 2
instruction, no rule has been invented to fill any of these gaps.** Each needs a decision
before it can enter the Phase 3 SRS.

| OQ | Affects | Question |
|---|---|---|
| **OQ-01** | Everything | The reference labels every block "Guidelines" and never says "rule" or "mandatory". Is the M/G split in this document (absolute-negation wording ⇒ Mandatory) the classification we adopt? |
| ~~**OQ-02**~~ | IMP-04 | **✅ RESOLVED 2026-08-09 — absolute price distance.** *(Original question: "shortest" by what — absolute price distance, percentage move, log distance, or bar count? The reference never says; these disagree on real data.)* See [resolution](#oq-02-resolution--wave-3-shortest-measure). |
| ~~**OQ-03**~~ | IMP-05 | **✅ RESOLVED 2026-08-09 — pivot-price interval overlap.** *(Original question: is the test against wave 1's terminal price or its full intrabar range? And wave 4's terminal price or its own extreme? Four readings.)* See [resolution](#oq-03-resolution--wave-4-price-territory). |
| ~~**OQ-04**~~ | IMP-06, WP-10 | **✅ RESOLVED 2026-08-09 — see "OQ-04 resolution" below.** *(Original question: "Momentum divergence" — which indicator, what period, measured between which two points, and what magnitude counts? WP-10 gives only a prose definition. IMP-06 is stated as a hard requirement for every impulse, which made the entire impulse detector depend on an undefined quantity.)* |
| **OQ-05** | All 16 Fibonacci rules | Every ratio is a **discrete exact value** ("50%, 61.8%, 76.4%, or 85.4%"), never a band. Exact float equality never matches real price data. What tolerance? A single global ±%, per-ratio bands, or convert each discrete set to one min–max envelope? |
| **OQ-06** | IMP-F02 | "161.8% … of wave **1-2**" — is the base the net displacement from start of wave 1 to end of wave 2, or the length of wave 1 projected from the end of wave 2? Standard practice differs from the literal reading. |
| **OQ-07** | IMP-F04, FIB-06 | "**inverse** 123.6 – 161.8% retracement of wave 4" — "inverse retracement" is used but never defined on the page. |
| **OQ-08** | IMP-F03, WP-07 | Wave 4: §3.1 says "14.6%, 23.6%, or 38.2% of wave 3 **but no more than 50%**"; §4.3 says "typically retraces **less than 38.2%**". Is 50% a hard cap or a guideline, and how does it interact with IMP-05 (overlap), which is the actual structural constraint? Two sections give different numbers. |
| **OQ-09** | FLR-01 | Regular Flat wave B "terminates **near** the start of wave A" — "near" is unquantified, and the paired Fibonacci value (90%) is a **single point** with no tolerance, so under strict reading it can essentially never match. |
| **OQ-10** | FLR-02, FLE-02 | "**slightly** beyond" (Regular) vs "**substantially** beyond" (Expanded) is the only stated discriminator between the two subtypes, and neither word is quantified. |
| **OQ-11** | FLR-F02, FLE-F02, FLU-F02 | All three flat subtypes measure wave C "of wave **AB**". What is "wave AB" — the net A-to-B displacement, the sum of len(A)+len(B), or wave A's length? Undefined. |
| **OQ-12** | TRI-01…07 | Triangle has **no Fibonacci ratios, no per-wave rules for D or E, no rule distinguishing the four named variants**, and TRI-04 permits nearly any corrective subdivision. As written, a Triangle detector would match almost any 5-leg sideways move. Is Triangle in scope at all for v1? |
| **OQ-13** | TRI-06 | "RSI also needs to support the triangle in **every time frame**" — "support" is undefined, and "every time frame" is undefined in a single-timeframe backtest. This is the only place RSI is named as a requirement. |
| **OQ-14** | MS-01…03 | Motive Sequence is defined entirely by reference to "the numbers in the motive sequence" — **and those numbers are never stated on the page.** The concept cannot be implemented from this source. Do we drop it, or source the numbers elsewhere (out of scope for this reference)? |
| **OQ-15** | LD-02, ED-02 | Both diagonals: overlap is "**not a condition**" and the wedge shape is unquantified. With position (LD-01/ED-01) and subdivision (LD-03/ED-03) as the only gates, what actually makes a diagonal a diagonal rather than a plain 5-leg move? |
| **OQ-16** | LD-03, ED-03 | Leading and Ending Diagonal permit the **identical** subdivision sets, so shape cannot distinguish them — only host position can. Confirm that's intended. |
| **OQ-17** | DEG-03, DEG-04 | Only 2 of the 9 degrees are mapped to a timeframe, and no rule exists for assigning a degree from price data. How is degree assigned? |
| ~~**OQ-18**~~ | DT-03, TT-03 | **✅ RESOLVED 2026-08-10 — recursion capped at depth 1.** *(Original question: W/Y/Z may themselves be a "double three of smaller degree", recursive with no stated depth limit.)* The cap is derived from the pivot ladder's expressive limit, not chosen: correctives occur only at scale 2, so a combination needs scale 3 and a nested one scale 4 — two levels would need scale 5, beyond the 4-scale ladder. See [OQ-18 resolution](#oq-18-resolution--doubletriple-three-recursion-depth). |
| **OQ-26** | DT-02, TT-02 | **NEW 2026-08-10, UNRESOLVED.** The reference's own swing arithmetic is inconsistent. DT-02 says WXY is a **7**-swing structure, but DT-04 says X is "any corrective structure" and GEN-06 says correctives move in three — 3+3+3 is **9**, not 7. The stated count only works if X contributes a single swing. TT is identical: 11 = 3+1+3+1+3. Gating on the count would contradict DT-04; ignoring DT-02 would drop a mandatory-tier statement. Swing count is therefore **recorded as a measurement and never gated**, and every combination carries `blocked_by: ["OQ-26"]`. |
| **OQ-19** | ZZ-F03 | The reference itself flags that a Zigzag's wave C at 161.8% of A is ambiguous with a wave 3 of an impulse, and offers "whether the third swing has extension or not" as the tiebreak — but "extension" is itself undefined (OQ-24). Circular. |
| **OQ-20** | GEN-04, GEN-06 | §5 says corrective waves "move in three, but **never** in five"; §1.6/§3.5 says motive waves "can unfold in **3 waves**". A 3-swing move is therefore both possibly-corrective and possibly-motive, with **no stated discriminator**. This is the reference's central modernization and its central ambiguity. |
| ~~**OQ-21**~~ | All | **✅ RESOLVED 2026-08-09 — build an independent, Elliott-specific pivot detector; do not consume the existing swing/zigzag modules.** *(Original question: the reference assumes waves/pivots are already identified and gives no rule for detecting wave boundaries from raw price.)* The reference **still** says nothing on this; the detector is entirely a project decision. See [OQ-21 resolution](#oq-21-resolution--elliott-specific-pivot-detection). |
| **OQ-22** | WP-02/04/08/11/12/13, TRI-05 | Every volume statement is qualitative ("lower than", "well below", "picks up", "decreasing") with no threshold or measurement window. Also: volume is present in our OHLCV but is **synthetic** for the default data source, so volume-gated rules would be meaningless on synthetic backtests. |
| **OQ-23** | FLE-F01, FLU-F01 | Expanded Flat and Running Flat both state wave B = **123.6%** of wave A. Wave B cannot discriminate between them; only wave C can. Confirm. |
| **OQ-24** | EXT-01, EXT-02, ZZ-F03 | "Extension" / "elongated" / "exaggerated subdivisions" — no numeric definition anywhere. What makes a wave "extended"? |

---

## OQ-18 resolution — Double/Triple Three recursion depth

**Status: RESOLVED 2026-08-10 by project decision.**

> ⚠ **Not from the reference.** The page says W/Y/Z may be "a double three or triple three of
> smaller degree" and **never states a termination depth** (verified against the source). The cap
> below is a **project decision**.

### Decision

`max_combination_depth = 1`. A Double/Triple Three may be built from zigzag/flat components
(depth 0), or from a depth-0 Double/Triple Three (depth 1). No deeper.

### Why 1 — derived from the ladder, not chosen

| Structure | Minimum scale | Because |
|---|---|---|
| Corrective (zigzag / flat) | **2** | needs 5-wave A/C legs at scale 1 |
| DT/TT from correctives | **3** | needs correctives at scale 2 |
| DT/TT containing a DT/TT | **4** | needs a DT at scale 3 |
| DT/TT nested two deep | **5** | ❌ exceeds the 4-scale ladder (D-13) |

Measured across four backtest configurations (191 impulses, 73 correctives): **correctives occur
at scale 2 and nowhere else.** So depth 1 is exactly what the ladder can express — depth 0 would
refuse a stated rule, depth ≥2 would be dead configuration. Confirmed empirically after
implementation: depth-0 combinations land at scale 3 and depth-1 at scale 4, precisely as the
table predicts.

### Consequences

| Item | Effect |
|---|---|
| DT-01, DT-03, DT-04, TT-01, TT-03, TT-04 | Blocked → **specified** |
| DT-05, TT-05 | Newly extracted and **specified** (mandatory ceilings) |
| DT-02, TT-02 | **Still blocked — OQ-26**, recorded as a measurement only |
| DT-F01/F02, TT-F01/F02 | Still blocked on **OQ-05** (discrete ratios, no tolerance) |
| Real-data yield | 11 Double Threes + 1 Triple Three across four configurations — rare, as predicted |

---

## OQ-21 resolution — Elliott-specific pivot detection

**Status: RESOLVED 2026-08-09 by project decision.**

> ⚠ **Nothing in this resolution comes from the reference.** The EWF page assumes waves are
> already identified and states no detection rule of any kind. Pivot detection is **100% project
> engineering** (tier EN). It is recorded here because it is the engine's input contract, not
> because the reference implies it.

### Decision

Build a **brand-new, Elliott-specific pivot detector** inside the new
`src/analysis/elliott_wave/` package. The engine SHALL NOT reuse, import, wrap, subclass, or
consume the **output** of:

- `src/analysis/swing_identification.py`
- `src/analysis/zigzag.py`
- any other existing pivot/swing detection code in this repository

Those files remain **untouched and unmodified** — and, per this decision, **also unconsumed**.
"Don't touch" is now strengthened to "don't touch *and* don't depend on."

### Mechanism — threshold-based directional change

A single chronological pass maintaining a direction and a running extreme:

```
state: direction ∈ {up, down}, extreme = (price, bar_index)

for each bar, in order:
    if direction == up:
        if bar.high > extreme.price:
            extreme ← (bar.high, bar.index)          # extend the swing
        elif bar.low <= extreme.price * (1 - θ):     # reversal confirmed
            emit HIGH pivot at extreme.bar_index, confirm_index = this bar
            direction ← down
            extreme ← (bar.low, bar.index)
    else:  # mirror image for a down swing
        ...
```

**Why directional change and not an N-bar fractal:** an N-bar fractal is precisely what
`swing_identification.py` already implements. Re-deriving that design — even without importing it
— would make the "independent detector" independent in name only. Directional change is a
structurally different formulation: it confirms on a **price event** (a reversal of θ) rather
than a **fixed bar lag**, which is also what gives it a natural, non-arbitrary confirmation
moment.

### Design decisions

| # | Decision | Rationale |
|---|---|---|
| **P-1** | **Pivot time ≠ confirmation time.** A pivot is recorded at the bar where the extreme occurred; `confirm_index` is the later bar where the θ reversal completed. | Mandatory no-look-ahead. A consumer evaluating bar *t* may use only pivots with `confirm_index ≤ t`. |
| **P-2** | **Pivot price = the bar's own extreme** — `high` for a HIGH pivot, `low` for a LOW pivot. | Matches the pivot-price convention already fixed by the OQ-02, OQ-03 and OQ-04 resolutions (FR-3.1a.7, FR-3.1b.4). One convention across the whole engine. |
| **P-3** | **Alternation is guaranteed by construction** — direction flips on every emission, so HIGH and LOW strictly alternate. | Satisfies the alternation requirement without a separate post-filter. |
| **P-4** | **The final, unconfirmed extreme is never emitted.** | It has no `confirm_index`; emitting it would be exactly the look-ahead P-1 exists to prevent. |
| **P-5** | **Multi-scale ladder.** The same pass runs independently at *S* scales with geometric thresholds θₖ = θ_base · rᵏ⁻¹. Each pivot carries its `scale` index. | Elliott is inherently hierarchical (IMP-02 needs waves 1/3/5 to subdivide; DT-03/TT-03 reference smaller degrees). A single-scale pivot list cannot support that. |
| **P-6** | **Relative (percentage) threshold, not volatility-adaptive.** | A fixed relative θ is simple, auditable, and deterministic. Volatility adaptation was considered and **deferred**: it introduces a second undefined parameter set and makes determinism harder to reason about. It can be added later without changing the pivot contract. |
| **P-7** | **`scale` is NOT an Elliott degree.** The detector emits an integer scale index only. | Mapping a scale to one of the reference's 9 named degrees is **OQ-17, still open.** The detector must not pre-empt it. |
| **P-8** | **Single deterministic pass per scale**, no randomness, no wall-clock, no I/O. | Required for byte-identical repeat runs. |

### Input

`BacktestResults.price_data` — the canonical OHLCV DataFrame already held in the store. The
detector **re-fetches nothing** and mutates nothing.

### Threshold values — settled 2026-08-09 (D-13 closed)

- **θ_base = 0.20%, ratio r = 2.5, S = 4 scales** → ladder 0.20 / 0.50 / 1.25 / 3.125%.
  Calibrated against real CL and ES data plus the deterministic synthetic generator; the
  measurements and reasoning are in
  [ELLIOTT_WAVE_ARCHITECTURE.md](ELLIOTT_WAVE_ARCHITECTURE.md) §5. These remain
  **configuration, not rules** — tunable per request.

### What this resolution still does NOT settle
- **OQ-17** (degree assignment) stays open — P-7 exists precisely to avoid pre-empting it.
- **Cross-scale nesting is not assumed.** Directional change at a coarse θ does **not**
  guarantee its extremes are a subset of a finer θ's extremes. Any hierarchy construction must
  handle non-nesting explicitly rather than assume containment. Flagged for Phase 4.

---

## OQ-02 resolution — Wave 3 "shortest" measure

**Status: RESOLVED 2026-08-09 by project decision.**

> ⚠ **Not from the reference.** The EWF page says only *"Wave 3 can not be the shortest wave of
> the three impulse waves, namely wave 1, 3, and 5"* and never states how length is measured.
> The measure below is a **project decision**.

### Decision

**Wave length is ABSOLUTE PRICE DISTANCE**, computed from pivot prices:

```
len(w) = | P(end pivot of w) − P(start pivot of w) |
```

**Explicitly rejected:** percentage distance, logarithmic distance, and bar count (time).

**IMP-04 gate:** `len(wave 3) > min( len(wave 1), len(wave 5) )`

**No tolerance, threshold, or buffer** is introduced. The comparison is exact.

### Consistency with existing decisions

This uses the same **pivot-price** convention already adopted in **FR-3.1a.7** for IMP-06.
Checked for contradiction — **none found**; the two decisions reinforce each other, so
FR-3.1a.7 is left unchanged.

---

## OQ-03 resolution — Wave 4 price territory

**Status: RESOLVED 2026-08-09 by project decision.**

> ⚠ **Not from the reference.** The EWF page says only *"Wave 4 does not overlap with the price
> territory of wave 1"* and never defines "price territory". The reading below is a **project
> decision**.

### Decision

Wave 4 is **invalid only when its price enters/overlaps wave 1's price territory**, where both
territories are the **pivot-price intervals** of the respective waves:

```
territory(w) = [ min(P(start w), P(end w)),  max(P(start w), P(end w)) ]

IMP-05 is VIOLATED  iff  territory(wave 4) ∩ territory(wave 1) ≠ ∅
```

Equivalently, for the common case where wave 4 retraces toward wave 1:

| Direction | Violated when |
|---|---|
| Up-trending impulse | wave 4's low pivot price **≤** wave 1's high pivot price |
| Down-trending impulse | wave 4's high pivot price **≥** wave 1's low pivot price |

**Explicitly rejected:** using the full intrabar high/low range across all bars spanned by
wave 1 (rather than its two endpoint pivots).

**No tolerance, percentage threshold, or arbitrary buffer** is introduced.

### Note on pivot prices vs intrabar extremes

For a high pivot the pivot price *is* the bar's high, and for a low pivot it *is* the bar's low
(DM-1). Because pivots alternate high/low (FR-1.3), a wave's two endpoint pivots are its own
extremes by construction, so the endpoint-pivot reading and the "extremes of this wave" reading
coincide. What the decision rules out is scanning **all** bars inside wave 1's span for a more
extreme value than its own endpoints.

### Consistency with existing decisions

Same pivot-price convention as **FR-3.1a.7** and the OQ-02 resolution. **No contradiction.**

---

## OQ-04 resolution — Wave 5 momentum divergence

**Status: RESOLVED 2026-08-09 by project decision.** Three Open Questions are now resolved
(OQ-02, OQ-03, OQ-04); the other 21 remain open.

> ⚠ **This definition does not come from the reference.** The EWF page names no indicator, no
> period, and no comparison procedure. The definition below is a **project decision** made because
> IMP-06 is mandatory and therefore had to be made computable. It is recorded here as a decision,
> not presented as source-defined behavior.

### Decision

**IMP-06 remains MANDATORY.** "Guidelines" are **not** declared non-gating as a blanket rule —
that alternative was explicitly rejected, because it would have silently weakened IMP-03, IMP-04
and IMP-05, which sit under the same heading.

**Indicator:** RSI(13), computed by `src/analysis/indicators.py::calc_rsi(close, 13)` — the
existing shared implementation already used for the platform's RSI(13) chart panel. Consumed
**read-only**; that module is not modified.

**Definition** — a purely directional comparison, with **no tolerance band and no threshold**:

| Impulse direction | Price condition | RSI condition | ⇒ divergence |
|---|---|---|---|
| **Up** | wave 5's extreme is **above** wave 3's extreme | RSI(13) at wave 5's extreme is **LOWER** than RSI(13) at wave 3's extreme | yes |
| **Down** | wave 5's extreme is **below** wave 3's extreme | RSI(13) at wave 5's extreme is **HIGHER** than RSI(13) at wave 3's extreme | yes |

**Unavailable data:** if RSI(13) is `NaN` at either comparison bar — which happens for the first
13 bars of any series, since `calc_rsi` uses `min_periods=13` — IMP-06 evaluates to
**UNDECIDABLE**, never to pass or fail.

### What this resolution deliberately does *not* do

- **No tolerance/threshold.** "Lower"/"higher" is a strict directional comparison. No epsilon, no
  minimum divergence magnitude, no RSI overbought/oversold levels are involved. (The platform's
  RSI(13) chart bands are 70/30, but they play **no part** in this rule.)
- **No other Open Question is resolved by this one.** In particular **OQ-01, OQ-05 and OQ-20
  remain open.**
- **On its own it did not unblock the impulse detector** — IMP-04 and IMP-05 were still
  undefined at that point. They were subsequently resolved by the OQ-02 and OQ-03 decisions
  above, which is what actually cleared the impulse gate set.

### Consequences

| Item | Effect |
|---|---|
| IMP-06, WP-10 | Blocked → **specified** |
| **Impulse overall** | Was still blocked after OQ-04 alone; **now fully specified** once OQ-02 and OQ-03 were also resolved |
| Engine input contract | **Extended.** IMP-06 needs the `close` price series, so pivots alone are no longer a sufficient input. This is a real change to the engine's input requirements. |
| New dependency | The Elliott module now depends on `src/analysis/indicators.py` (read-only). |

### Partial constraint on OQ-01 (not a resolution)

The same decision states that "Guidelines" must **not** be treated as non-gating as a blanket
rule. That **rules out one of OQ-01's two candidate answers** but does not answer the question
itself — whether the grammar-based Mandatory/Guideline split proposed in this inventory is the
adopted classification is **still open**. OQ-01 therefore remains listed as unresolved.

---

## Coverage summary

Recounted 2026-08-09, after the OQ-04 resolution. Columns are mutually exclusive and sum to the
section total.

| Reference section | Rules | Specified | Blocked | Not implementable | Partial | Informational |
|---|---|---|---|---|---|---|
| §1 General theory | 7 | 4 | 2 | — | — | 1 |
| §1.4 Wave Degree | 5 | 2 | 2 | — | — | 1 |
| §2 Fibonacci | 6 | 5 | 1 | — | — | — |
| §3.1 Impulse | 10 | **6** | **4** | — | — | — |
| §3.2 Impulse with Extension | 4 | — | 2 | 2 | — | — |
| §3.3 Leading Diagonal | 3 | 2 | — | — | 1 | — |
| §3.4 Ending Diagonal | 3 | 2 | — | — | 1 | — |
| §3.5 Motive Sequence | 3 | — | — | 3 | — | — |
| §4 Wave Personality | 14 | **5** | **7** | — | — | 2 |
| §5.1 Zigzag | 7 | 4 | 3 | — | — | — |
| §5.2 Flat (all subtypes) | 13 | 4 | 9 | — | — | — |
| §5.3 Triangle | 7 | 3 | 4 | — | — | — |
| §5.4 Double Three | 6 | 3 | 3 | — | — | — |
| §5.5 Triple Three | 6 | 3 | 3 | — | — | — |
| **Total** | **94** | **43** | **40** | **5** | **2** | **4** |

**Two corrections from the original version of this table**, both found while recounting:

1. **§5.2 Flat contains 13 rules, not 12** (FL 2 + FLR 4 + FLE 4 + FLU 3). This single
   miscount was the entire source of the earlier "93 vs 94" total discrepancy. The row-level
   ID count was always 94; only this summary was wrong.
2. **EXT-03/EXT-04 are reclassified from "Informational" to "Not implementable."** They are not
   merely narrative — they state market-class priors, and building them would require both an
   instrument-class taxonomy (which this platform lacks) and probability values (which the
   reference never gives).

**Impulse is now fully specified** — all six of its gates (IMP-01…IMP-06) are settled, three by
the reference and three by the OQ-02/03/04 decisions. The remaining blocked rules cluster into:
the 16 Fibonacci rules (all blocked on tolerance, **OQ-05**, none of which gate anything), the
Regular/Expanded flat discriminators (**OQ-09** / **OQ-10**), Triangle (**OQ-12** / **OQ-13**),
and extensions (**OQ-24**). Nested combinations are no longer blocked: **OQ-18 is resolved** by a depth-1 cap, though DT-02/TT-02's swing counts remain open as **OQ-26**.

**The OQ-21 resolution deliberately does not move these numbers.** OQ-21 was never a *per-rule*
blocker — no individual rule in this inventory cites it. It was an engine-level precondition: the
rules were computable in principle but had no input to compute against. Resolving it makes the
engine runnable without reclassifying a single rule, and the totals above are unchanged as a
result. Reporting an increase here would have been misleading.

---

## Provenance and integrity notes

- **Single source.** Everything above comes from the one page you specified. No other Elliott
  Wave source (Prechter/Frost, Neely, MotiveWave, etc.) was consulted, and no rule from general
  Elliott Wave knowledge has been added.
- **Nothing carried over.** The deleted implementations were not opened, read, or referenced
  while producing this document. Rule IDs here are newly assigned; any resemblance to earlier
  IDs is coincidental and not a reuse.
- **Verbatim where quoted.** Text in quotation marks is reproduced from the reference. Anything
  outside quotation marks is my classification or restatement and is labelled as such.
- **This reference is EWF's modernized interpretation**, which deliberately departs from
  classical Elliott Wave in at least two ways worth knowing: it adds "wave 5 needs to end with
  momentum divergence" as a hard impulse condition (IMP-06), and it allows motive moves in 3
  waves (GEN-04). Both are EWF positions, not universal Elliott Wave doctrine.
