# Elliott Wave

Everything about the Elliott Wave engine, in one place. This was four
separate files; they are merged here unchanged, in the order the work
actually happened — the rules are the specification, the requirements
follow from them, the architecture serves the requirements, and the
implementation record says what was built.

> Merged 2026-08-31. No content was removed; each part below is the former
> file in full, with its headings pushed down one level so this document
> has a single title.

## Contents

1. [Elliott Wave — Reference Rule Inventory](#rules) — was `ELLIOTT_WAVE_RULES.md`
2. [Elliott Wave — Software Requirements Specification](#requirements) — was `ELLIOTT_WAVE_SRS.md`
3. [Elliott Wave — Architecture](#architecture) — was `ELLIOTT_WAVE_ARCHITECTURE.md`
4. [Elliott Wave — Implementation Record](#implementation) — was `ELLIOTT_WAVE_IMPLEMENTATION.md`

---

<a id="rules"></a>

## Part 1 — Elliott Wave — Reference Rule Inventory

**Phase 2 deliverable.** Extracted 2026-08-09 from the single approved reference:
<https://elliottwave-forecast.com/elliott-wave-theory/> (Elliott Wave Forecast, "EWF").

This document is an **inventory of what the reference actually says** — not a design, not
a specification, and not an implementation plan. Nothing here has been implemented.

**Revision 2026-08-10:** **OQ-18 RESOLVED** — Double/Triple Three recursion capped at depth 1
([resolution](#oq-18-resolution--doubletriple-three-recursion-depth)). **DT-05 and TT-05 added** —
an extraction correction; both ceilings were missing from the first pass. **OQ-26 added**
(unresolved) — the reference's 7-vs-9 swing-count contradiction. Rule count 94 → **96**.

**Revision 2026-08-09:** pivot thresholds calibrated and **D-13 closed**
(θ_base 0.20%, r 2.5, S 4 — see [ARCHITECTURE](#architecture) §5);
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
resolved too, and OQ-26 added — see the 2026-08-10 revision above. Current standing: **6 of 27
resolved, 20 unresolved, 1 confirmed not implementable (OQ-14)**.)* With OQ-02/03/04 settled, **all six Impulse gates are specified**;
with OQ-21 settled, **the engine now has a defined input**.

---

### How to read this document

#### Scope and provenance

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

#### ⚠ Critical finding: the reference declares *no* mandatory rules

**The reference labels every single structure block "Guidelines".** It never uses the words
"rule", "mandatory", "required", or "must" as a classification. There is no rules-vs-guidelines
distinction in the source.

The **M/G** column below is therefore **a project classification, not the reference's**. It is
**informed by the grammar of each statement, not mechanically derived from it** — a distinction
corrected on 2026-08-10 after OQ-01 was investigated, because the original wording ("derived
purely from the grammar") claimed more rigour than was actually applied.

The grammar that informs the call:

- **M (Mandatory)** — typically an absolute negative or a definitional identity:
  *"can't"*, *"can not"*, *"does not"*, *"never"*, *"is X waves"*. Falsifiable from price alone.
- **G (Guideline)** — typically an approximation or a frequency claim: *"usually"*, *"typically"*,
  *"generally"*, *"frequently"*, *"should"*, *"can be"*, or any Fibonacci ratio.

**Where grammar and judgement diverge, judgement decided, and the divergences are documented
rather than smoothed over** — see [the OQ-01 investigation](#oq-01-investigated-2026-08-10--resolved-as-documentation-no-behaviour-change).
Applying the grammar mechanically would give the wrong answer in at least one place: the
reference states the *same* diagonal subdivision constraint as *"can be"* for LD-03 and *"is
either"* for ED-03, which would split an identical rule across two tiers.

**OQ-01 is closed** as of 2026-08-10 — resolved as a documentation matter, with no behavioural
change.

#### OQ-01 investigated 2026-08-10 — resolved as documentation, no behaviour change

OQ-01 asked whether the Mandatory/Guideline split in this inventory is the classification the
project adopts, given the reference labels **every** block "Guidelines" and never says *rule*,
*must*, *mandatory* or *required* as a classification anywhere.

**Outcome: every gate stays exactly as it is.** What changed is the honesty of the description —
the tiers are project judgement calls informed by grammar, not outputs of a grammar rule. No code
was touched, no rule was reclassified, and no structure the engine reports has changed.

##### The grammar evidence

Re-verified against the live reference. All eight structure blocks — Impulse, Leading Diagonal,
Ending Diagonal, Zigzag, Flat, Triangle, Double Three, Triple Three — carry the identical heading
**"Guidelines"**. The Impulse list, in order:

| Rule | Verbatim modal | Matches the stated M criterion? |
|---|---|---|
| IMP-01 | "subdivide into 5 waves" | yes — definitional identity |
| IMP-02 | "subdivision **are** impulse" | yes — definitional identity |
| IMP-03 | "**can't** retrace more than" | yes — absolute negation |
| IMP-04 | "**can not** be the shortest" | yes — absolute negation |
| IMP-05 | "**does not** overlap" | yes — absolute negation |
| IMP-06 | "**needs to** end with momentum divergence" | **no — neither** |

##### Three inconsistencies found

**1. IMP-06 and TRI-06 share a modal and are tiered oppositely.**

> IMP-06 — **M** — *"Wave 5 **needs to** end with momentum divergence"*
>
> TRI-06 — **G** — *"RSI also **needs to** support the triangle in every time frame"*

Same verb, same page, opposite tiers. **This is a considered inconsistency, not an oversight**, and
it is recorded here so that nobody "fixes" it into a behaviour change:

- **IMP-06 is Mandatory by the OQ-04 project decision** (RSI(13) divergence, 55/45), taken
  deliberately and independently of grammar. Its tier does not rest on the words "needs to".
- **TRI-06 stays Guideline** because *"supports"* states no direction, no threshold and no
  comparison, and *"in every time frame"* has no meaning in a single-timeframe engine (OQ-13). It
  ships measurement-only, exactly as the Triangle step built it.

The two differ because the **evaluability of their content** differs, not because their grammar
does. Reclassifying either to match the other is a behaviour change of the magnitude in the table
below — IMP-06 is the single highest-impact gate in the engine.

**2. LD-03 and ED-03 state the same constraint with different grammar.**

> LD-03 — *"The subdivision of a leading diagonal **can be** 5-3-5-3-5 or 3-3-3-3-3"*
>
> ED-03 — *"The subdivision of an ending diagonal **is either** 3-3-3-3-3 or 5-3-5-3-5"*

*"Can be"* is on the Guideline list; *"is either"* is a definitional identity. Applied
mechanically, grammar would put an **identical constraint into two different tiers**. Both are M,
which is substantively correct — and is the clearest single proof that grammar cannot be the
criterion on its own. (A closed disjunction, "can be X or Y", genuinely constrains; "can be **any**
corrective structure" in ZZ-03/DT-04/TT-04 does not, and those are marked permissive and never
gate.)

**3. An absolute cap inside a guideline.** IMP-F03 — *"Wave 4 is 14.6%, 23.6%, or 38.2% of wave 3
**but no more than 50%**"* — is G-classified, yet "no more than 50%" is an absolute inequality
needing no tolerance, the same shape as DT-05. Already tracked as **OQ-08**; noted here because it
is the one place a gateable constraint sits inside a non-gating rule.

##### Blast radius — why nothing was reclassified

Every currently-gating mandatory rule was measured on real data (CL 5m, NQ 5m, CL 15m, ES 15m) by
making it non-gating and re-running. Baseline: **1,891 structures — 765 gated, 1,126 undecidable,
1,140 impulses.**

| Rule relaxed | change in structures | gated | undecidable | impulses |
|---|---|---|---|---|
| **IMP-06** wave 5 divergence | **+2,560 (+135%)** | +768 | +1,792 | +1,876 |
| **IMP-02** wave 1/3/5 subdivide | +1,605 (+85%) | +2,731 | **−1,126** | +292 |
| **IMP-05** wave 4 territory | +692 (+37%) | +258 | +434 | +450 |
| **IMP-03** wave 2 retrace | +581 (+31%) | +184 | +397 | +407 |
| **IMP-04** wave 3 not shortest | +125 (+7%) | +74 | +51 | +58 |
| **DT-05 / TT-05** wave Y ceiling | +51 (+3%) | +51 | 0 | 0 |
| **FLU-01** running flat wave C | 0 | 0 | 0 | 0 |

Three things the totals hide:

- **FLU-01's zero is a relabel, not a no-op.** Relaxed, *every* flat becomes a running flat
  (188 → 0 generic, 23 → 211 running). Zero percent by count, one hundred percent by label.
- **IMP-02 is the sole source of UNDECIDABLE.** Relaxing it drives the count to zero — the D-14
  scale-1 floor is entirely IMP-02's doing.
- **Impulse gates cascade**, because ZZ-02/FL-01 and LD-01/ED-01 consume the spans impulses
  register. Relaxing IMP-02 takes diagonals from 72 to **1,236**; relaxing IMP-06 takes ending
  diagonals from 13 to **170**.

Rules that **cannot** be relaxed this way are excluded rather than faked: IMP-01, ZZ-01, FL-01,
DT-01 and TT-01 are leg-count definitions that determine which windows are enumerated at all. An
"impulse without IMP-01" is not a relaxed impulse; it is a different structure.

##### Disposition

**OQ-01 RESOLVED 2026-08-10 — documentation only.** The tier assignments are substantively sound
but were never mechanically derivable from the stated criterion, and the criterion now says so.
Every gate is unchanged. A future reader who spots the IMP-06/TRI-06 asymmetry should read this
section before acting on it: it has been reviewed deliberately, and changing it is a behaviour
change of the magnitude shown above.

#### Column key

| Column | Meaning |
|---|---|
| **Input** | Data the rule needs. `pivots` = ordered wave-boundary pivots (bar index + price); `OHLC` = bar extremes; `vol` = volume; `mom` = a momentum oscillator series; `sub` = child-wave classification results; `deg` = assigned wave degree |
| **Measurement** | The computation the rule reduces to. `P(x)` = price at pivot x; `len(w)` = abs price length of wave w |
| **Fib** | Fibonacci relationship stated by the reference for that wave, verbatim |
| **Mom** | Momentum/volume requirement, if the reference states one |
| **Status** | Implementation status. All rules are currently **Not implemented** (fresh start); rules that cannot be implemented as written are marked **Blocked** with the blocking Open Question |

#### Status legend

- **Not implemented** — extractable and implementable; no blocker
- **Blocked (OQ-nn)** — cannot be implemented as written; the reference is ambiguous or silent
- **Informational** — narrative/contextual; not a detector rule

---

### 1. General theory (§1)

| ID | Structure | Wave | Rule | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| GEN-01 | — | — | "the movement of the stock market could be predicted by observing and identifying a repetitive pattern of waves" | G | — | — | — | — | 1.1 | Informational |
| GEN-02 | Motive | — | "the traditional definition of motive wave is a 5 wave move in the same direction as the trend of one larger degree" | M | pivots, deg | count of legs == 5; direction == parent direction | — | — | 3 | Not implemented |
| GEN-03 | Motive | — | "There are three different variations of a 5 wave move which is considered a motive wave: Impulse wave, Impulse with extension, and diagonal" | M | sub | classification ∈ {impulse, impulse-with-extension, diagonal} | — | — | 3 | Not implemented |
| GEN-04 | Motive | — | EWF revision: "motive waves do not have to be in 5 waves… motive waves can unfold in 3 waves. For this reason, we prefer to call it motive sequence" | G | pivots | leg count ∈ {3, 5} | — | — | 1.6, 3.5 | Blocked (OQ-20) |
| GEN-05 | Corrective | — | "waves that move against the trend of one greater degree" | M | pivots, deg | direction != parent direction | — | — | 5 | Not implemented |
| GEN-06 | Corrective | — | "Corrective waves are probably better defined as waves that move in three, but never in five" | M | pivots | leg count == 3 (never 5) | — | — | 5 | Blocked (OQ-20) |
| GEN-07 | Corrective | — | Five corrective types exist: Zigzag (5-3-5), Flat (3-3-5), Triangle (3-3-3-3-3), Double Three, Triple Three | M | sub | classification ∈ the five | — | — | 5 | Not implemented |

### 2. Wave Degree (§1.4)

| ID | Structure | Wave | Rule | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| DEG-01 | — | — | "Elliott acknowledged 9 degrees of waves" | M | deg | degree count == 9 | — | — | 1.4 | Not implemented |
| DEG-02 | — | — | Degree names, largest→smallest: Grand Super Cycle, Super Cycle, Cycle, Primary, Intermediate, Minor, Minute, Minuette, Subminuette | M | deg | name lookup | — | — | 1.4 | Not implemented |
| DEG-03 | — | — | "Grand Super Cycle degree… is usually found in weekly and monthly time frame" | G | deg, timeframe | timeframe ∈ {W, M} → GSC | — | — | 1.4 | Blocked (OQ-17) |
| DEG-04 | — | — | "Subminuette degree which is found in the hourly time frame" | G | deg, timeframe | timeframe == 1h → Subminuette | — | — | 1.4 | Blocked (OQ-17) |
| DEG-05 | — | — | Degree exists to "identify position of a wave within overall progress of the market" | G | — | — | — | — | 1.4 | Informational |

**Gap:** the reference maps only 2 of 9 degrees to timeframes, and gives **no rule at all** for
assigning a degree from price data. See **OQ-17**.

### 3. Fibonacci (§2)

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

### 4. Impulse (§3.1)

**Reference heading: "Guidelines"**

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| IMP-01 | Impulse | all | "Impulse wave subdivide into 5 waves." | M | pivots | leg count == 5 | — | — | 3.1 | Not implemented |
| IMP-02 | Impulse | 1, 3, 5 | "Wave 1, 3, and 5 subdivision are impulse." | M | sub | sub(1), sub(3), sub(5) each classify as impulse | — | — | 3.1 | Not implemented |
| IMP-03 | Impulse | 2 | "Wave 2 can't retrace more than the beginning of wave 1" | **M** | pivots | up: P(end 2) > P(start 1); down: P(end 2) < P(start 1) | — | — | 3.1 | Not implemented |
| IMP-04 | Impulse | 3 | "Wave 3 can not be the shortest wave of the three impulse waves, namely wave 1, 3, and 5" | **M** | pivots | **absolute price distance**: len(w) = \|P(end w) − P(start w)\|; requires len(3) > min(len(1), len(5)) | — | — | 3.1 | **Specified — OQ-02 RESOLVED 2026-08-09** |
| IMP-05 | Impulse | 4 | "Wave 4 does not overlap with the price territory of wave 1" | **M** | pivots | **pivot-price interval overlap**: territory(w1) = [min(P(start 1), P(end 1)), max(…)]; violated iff wave 4's own pivot-price interval intersects it | — | — | 3.1 | **Specified — OQ-03 RESOLVED 2026-08-09** |
| IMP-06 | Impulse | 5 | "Wave 5 needs to end with momentum divergence" | **M** | pivots, close series | P(end w5) beyond P(end w3) **AND** RSI(13)@w5-extreme not beyond RSI(13)@w3-extreme (direction-aware) | — | **RSI(13) divergence** | 3.1 | **Specified — OQ-04 RESOLVED 2026-08-09** |

#### Impulse — Fibonacci Ratio Relationship (§3.1)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| IMP-F01 | Impulse | 2 | "Wave 2 is 50%, 61.8%, 76.4%, or 85.4% of wave 1" | G | pivots | len(2) / len(1) | 50 / 61.8 / 76.4 / 85.4 % | — | 3.1 | Blocked (OQ-05) |
| IMP-F02 | Impulse | 3 | "Wave 3 is 161.8%, 200%, 261.8%, or 323.6% of wave 1-2" | G | pivots | len(3) / len(wave 1-2) | 161.8 / 200 / 261.8 / 323.6 % | — | 3.1 | Blocked (OQ-05, OQ-06) |
| IMP-F03 | Impulse | 4 | "Wave 4 is 14.6%, 23.6%, or 38.2% of wave 3 but no more than 50%" | G + cap | pivots | len(4) / len(3) | 14.6 / 23.6 / 38.2 %, hard cap 50% | — | 3.1 | Blocked (OQ-05, OQ-08) |
| IMP-F04 | Impulse | 5 | "Wave 5 is inverse 123.6 – 161.8% retracement of wave 4. Second, wave 5 is equal to wave 1. Third, wave 5 is 61.8% of wave 1-3" | G (3 alternative bases) | pivots | three independent targets | 123.6–161.8% of w4 (inverse) · 100% of w1 · 61.8% of w1-3 | — | 3.1 | Blocked (OQ-07) |

**IMP-F04 is the only Fibonacci relationship in the entire reference given as a *range*
(123.6–161.8%) rather than a discrete set.**

### 5. Impulse with Extension (§3.2)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| EXT-01 | Impulse+Ext | 1/3/5 | "Impulses usually have an extension in one of the motive waves (either wave 1, 3, or 5)" | G | pivots | longest of w1/w3/w5, and its ratio to the second-longest | — | — | 3.2 | **Measured only** — OQ-24 open, no cutoff exists |
| EXT-02 | Impulse+Ext | — | "Extensions are elongated impulses with exaggerated subdivisions" | G | pivots, sub | length + subdivision-count vs siblings | — | — | 3.2 | **Measured only** — OQ-24; conjunctive, and unmeasurable on 98.8% |
| EXT-03 | Impulse+Ext | 3 | "Extensions frequently occur in the third wave in the stock market and forex market" | G | pivots, instrument class | prior probability by market | — | — | 3.2 | Informational |
| EXT-04 | Impulse+Ext | 5 | "Commodities market commonly develop extensions in the fifth wave" | G | pivots, instrument class | prior probability by market | — | — | 3.2 | Informational |

**No Fibonacci ratios are stated for extensions.** No numeric definition of "extended" is given.

#### OQ-24 investigated 2026-08-10 — measured, still unresolved

OQ-24 was attacked the same way D-13 and the OQ-18 depth cap were: derive the number from real
data instead of guessing. **The data refused to supply one, so OQ-24 stays open** and the engine
records the quantities without ever rendering a verdict (`measurements.record_extension`).

**1. No cliff, in any formulation.** Five candidate measures of "extended" over 1,142 impulses
(CL 5m, NQ 5m, CL 15m, ES 15m; 60k-bar slices):

| Formulation | Modes | Verdict |
|---|---|---|
| longest / second-longest | 0 | no split |
| wave 3 / wave 1 | 1 | no split |
| longest / mean(other two) | 2 | tail noise (counts `25, 15, 24, 21, 19, 10`), not a regime |
| longest / total | 1 | no split |
| longest / shortest | 1 | no split |

The distribution is a smooth monotone decay — p25 = 1.22, p50 = 1.55, p75 = 2.13, p90 = 2.80,
p95 = 3.51 — with no shoulder anywhere. D-13 had a genuine discontinuity to calibrate against;
this has none. The only thing separating candidate cutoffs is what share they flag (1.618 → 46%,
2.0 → 29%), which means choosing one is choosing a hit rate and back-solving. That is precisely
what this project's calibration method exists to avoid.

**2. EXT-02's second criterion is mostly unmeasurable, and self-contradicting where it isn't.**
EXT-02 is conjunctive — "elongated impulses **with** exaggerated subdivisions". Subdivision count
needs a finer scale, which scale-1 impulses do not have (D-14): unmeasurable on **1,198 of 1,212**
motive structures (98.8%). On the 14 where both halves *are* measurable, they name **different
waves 36% of the time** (5 of 14) — e.g. lengths `[1910, 3504, 3405] → longest w3` against
subdivisions `[21, 27, 43] → most w5`. So even given a length threshold, EXT-02 as written could
not be evaluated on almost the whole population and would contradict itself on a third of the
rest.

**3. OQ-24 is independent of OQ-05 — resolving OQ-05 first would not help.** OQ-05 is about
tolerance for matching *discrete stated ratios*. DT-05 escaped it because the reference states an
explicit **inequality** ("Wave Y can not pass 161.8% of wave W"), and an inequality needs no
tolerance. **Extension has no equivalent stated ratio at all** — §3.2 gives none, as the line
above records. Importing 161.8% here would be inventing a rule rather than lifting one, and it
would break two things: it makes **OQ-19** circular (the reference offers "whether the third swing
has extension" as the tiebreak for a zigzag wave C at 161.8% of A), and it collides with
**IMP-F02**, which lists 161.8% as the *first, typical* value for an ordinary wave 3 — so the
textbook-normal wave 3 would be classified as extended.

**What is recorded instead** (all tagged `blocked_by: ["OQ-24"]`, never gating):
`EXT-01_motive_wave_lengths`, `EXT-01_longest_motive_wave` (None on a tie, per D-02c),
`EXT-01_longest_over_second`, `EXT-02_subdivision_counts` (None where no finer scale exists —
not 0, which would falsely read as "measured, and none"), `EXT-02_most_subdivided_wave`,
`EXT-02_criteria_agree`. `StructureType` still has **no** `IMPULSE_WITH_EXTENSION` member, so
GEN-03's three-way motive classification correctly remains unavailable.

### 6. Leading Diagonal (§3.3)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| LD-01 | Leading Diagonal | — | "appears as subdivision of wave 1 in an impulse or subdivision of wave A in a zigzag" | **M** | pivots, sub | host label ∈ {impulse w1, zigzag wA} | — | — | 3.3 | Not implemented |
| LD-02 | Leading Diagonal | 1, 4 | "usually characterized by overlapping wave 1 and 4 and also by the wedge shape **but overlap between wave 1 and 4 is not a condition, it may or may not happen**" | G (explicitly non-gating) | pivots | overlap(w1, w4) — recorded, never gates | — | — | 3.3 | Blocked (OQ-15) |
| LD-03 | Leading Diagonal | all | "The subdivision of a leading diagonal can be 5-3-5-3-5 or 3-3-3-3-3." | **M** | sub | subdivision pattern ∈ {5-3-5-3-5, 3-3-3-3-3} | — | — | 3.3 | Not implemented |

### 7. Ending Diagonal (§3.4)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| ED-01 | Ending Diagonal | — | "appears as subdivision of wave 5 in an impulse or subdivision of wave C in a zigzag" | **M** | pivots, sub | host label ∈ {impulse w5, zigzag wC} | — | — | 3.4 | Not implemented |
| ED-02 | Ending Diagonal | 1, 4 | "usually characterized by overlapping wave 1 and 4 and also by the wedge shape. **However, overlap between wave 1 and 4 is not a condition and it may or may not happen**" | G (explicitly non-gating) | pivots | overlap(w1, w4) — recorded, never gates | — | — | 3.4 | Blocked (OQ-15) |
| ED-03 | Ending Diagonal | all | "The subdivision of an ending diagonal is either 3-3-3-3-3 or 5-3-5-3-5" | **M** | sub | subdivision pattern ∈ {3-3-3-3-3, 5-3-5-3-5} | — | — | 3.4 | Not implemented |

**LD-03 and ED-03 permit the identical two subdivision sets.** Leading and Ending Diagonal are
therefore distinguished *only* by host position (LD-01 vs ED-01). See **OQ-16**.

### 8. Motive Sequence (§3.5)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| MS-01 | Motive Sequence | — | "We define a motive sequence simply as an incomplete sequence of waves (swings)" | M | pivots | swing count | — | — | 3.5 | **Not implementable (OQ-14)** — "incomplete" has no stated criterion |
| MS-02 | Motive Sequence | — | "The structure of the waves can be corrective, but the sequence of the swings will be able to tell us whether the move is over" | G | pivots, sub | swing count vs sequence membership | — | — | 3.5 | **Not implementable (OQ-14)** — membership set absent |
| MS-03 | Motive Sequence | — | "Motive sequence is much like the Fibonacci number sequence. If we discover the number of swings on the chart is one of the numbers in the motive sequence, then we can expect the current trend to extend further." | G | pivots | swing_count ∈ motive_sequence | — | — | 3.5 | **Blocked (OQ-14) — sequence numbers never stated** |

#### OQ-14 investigated 2026-08-10 — confirmed NOT IMPLEMENTABLE, closed as a dead end

Re-verified against the live reference rather than trusting the Phase-2
extraction, because the three preceding investigations each found something it
had missed. **This one did not.** The gap is exactly as recorded, and it is
terminal rather than merely open.

Everything section 3.5 says about the concept:

> *"We define a motive sequence simply as an incomplete sequence of waves
> (swings)."*
> *"The structure of the waves can be corrective, but the sequence of the
> swings will be able to tell us whether the move is over or whether we should
> expect an extension in the existing direction."*
> *"Motive sequence is much like the Fibonacci number sequence. If we discover
> the number of swings on the chart is one of the numbers in the motive
> sequence, then we can expect the current trend to extend further."*

Confirmed absent: **no numeric sequence is ever listed**, **no worked example
of counting swings to a number**, **no labelling scheme** distinct from the
standard 1-2-3-4-5, and **no criterion for complete vs incomplete**.

##### Why this is NI, not merely unresolved

The definition closes a loop with nothing inside it:

- **MS-01** defines a motive sequence as an ***incomplete*** sequence.
- Incomplete relative to what? **MS-03** answers: relative to *"the numbers in
  the motive sequence"*.
- Those numbers are **never stated**.

So the concept is defined by reference to a set the source never supplies, and
the only thing distinguishing it from an ordinary swing count is that missing
set. There is no parameter to choose here and no decision a project could
make: unlike OQ-05, where a tolerance *could* be picked (badly), here the
absent content **is the rule itself**. Supplying numbers would not be resolving
an Open Question — it would be authoring a different rule.

##### The Fibonacci simile is not a licence to substitute

MS-03 says the sequence is *"much **like** the Fibonacci number sequence"*.
That is a **simile, not an identity** — "much like X" does not state "is X".
Reading it as an identity and substituting 3, 5, 8, 13, 21 would be inventing
the operative content of the rule while quoting the source as authority for it,
which is the precise failure mode this project exists to avoid. Note also that
the sentence compares the sequence to Fibonacci *as an analogy for how it
behaves* ("if the swing count is one of the numbers, expect extension"), not as
a definition of its membership.

##### Disposition

**Tier NI. Closed.** MS-01/02/03 are registered in `blocked_rules` and excluded
from v1 (FR-3.5.1, DM-4.1). No code was written and none should be. OQ-14 is
distinguished from the 21 genuinely *unresolved* questions in the tally below:
those await a decision or better source wording; this one awaits content the
reference does not contain and cannot be closed from it at all.

### 9. Wave Personality (§4)

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

### 10. Zigzag (§5.1)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| ZZ-01 | Zigzag | all | "Zigzag is a corrective 3 waves structure labelled as ABC" | **M** | pivots | leg count == 3 | — | — | 5.1 | Not implemented |
| ZZ-02 | Zigzag | A, C | "Subdivision of wave A and C is 5 waves, either impulse or diagonal" | **M** | sub | sub(A), sub(C) ∈ {impulse, diagonal}, each 5 legs | — | — | 5.1 | Not implemented |
| ZZ-03 | Zigzag | B | "Wave B can be any corrective structure" | **M** (permissive) | sub | sub(B) ∈ any corrective | — | — | 5.1 | Not implemented |
| ZZ-04 | Zigzag | all | "Zigzag is a 5-3-5 structure" | **M** | sub | subdivision pattern == 5-3-5 | — | — | 5.1 | Not implemented |
| ZZ-F01 | Zigzag | B | "Wave B = 50%, 61.8%, 76.4% or 85.4% of wave A" | G | pivots | len(B)/len(A) | 50 / 61.8 / 76.4 / 85.4 % | — | 5.1 | Blocked (OQ-05) |
| ZZ-F02 | Zigzag | C | "Wave C = 61.8%, 100%, or 123.6% of wave A" | G | pivots | len(C)/len(A) | 61.8 / 100 / 123.6 % | — | 5.1 | Blocked (OQ-05) |
| ZZ-F03 | Zigzag | C | "If wave C = 161.8% of wave A, wave C can be a wave 3 of a 5 waves impulse. Thus, one way to label between ABC and impulse is whether the third swing has extension or not" | G (disambiguator) | pivots | len(C)/len(A) ≈ 161.8% → prefer impulse reading | 161.8% | — | 5.1 | Blocked (OQ-19) |

### 11. Flat — general (§5.2)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| FL-01 | Flat | all | A flat is a 3-wave (ABC) move with a **3-3-5** structure | **M** | sub | subdivision pattern == 3-3-5 | — | — | 5.2 | Not implemented |
| FL-02 | Flat | A | Flat differs from zigzag in wave A's subdivision (A is 3 waves, not 5) | **M** | sub | sub(A) leg count == 3 | — | — | 5.2 | Not implemented |

#### 11.1 Regular Flat (§5.2.1)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| FLR-01 | Regular Flat | B | "Wave B terminates near the start of wave A" | G | pivots | \|P(end B) − P(start A)\| small | — | — | 5.2.1 | Blocked (OQ-09) |
| FLR-02 | Regular Flat | C | "Wave C generally terminates slightly beyond the end of wave A" | G | pivots | P(end C) beyond P(end A), by a small amount | — | — | 5.2.1 | Blocked (OQ-10) |
| FLR-F01 | Regular Flat | B | "Wave B = 90% of wave A" | G | pivots | len(B)/len(A) | **90%** (single value) | — | 5.2.1 | Blocked (OQ-05) |
| FLR-F02 | Regular Flat | C | "Wave C = 61.8%, 100%, or 123.6% of wave AB" | G | pivots | len(C)/len(AB) | 61.8 / 100 / 123.6 % | — | 5.2.1 | Blocked (OQ-05, OQ-11) |

#### 11.2 Expanded Flat (§5.2.2)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| FLE-01 | Expanded Flat | B | "Wave B of the 3-3-5 pattern terminates beyond the starting level of wave A" | **M** | pivots | P(end B) beyond P(start A) | — | — | 5.2.2 | Not implemented |
| FLE-02 | Expanded Flat | C | "Wave C ends substantially beyond the ending level of wave A" | G | pivots | P(end C) beyond P(end A), substantially | — | — | 5.2.2 | Blocked (OQ-10) |
| FLE-F01 | Expanded Flat | B | "Wave B = 123.6% of wave A" | G | pivots | len(B)/len(A) | **123.6%** (single value) | — | 5.2.2 | Blocked (OQ-05, OQ-23) |
| FLE-F02 | Expanded Flat | C | "Wave C = 123.6% – 161.8% of wave AB" | G | pivots | len(C)/len(AB) | 123.6–161.8% (range) | — | 5.2.2 | Blocked (OQ-11) |

#### 11.3 Running Flat (§5.2.3)

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

#### OQ-09 / OQ-10 investigated 2026-08-10 — measured, still unresolved

Attacked with the D-13 method — derive the number from real data, don't guess — over **356 flats**
from CL 5m, NQ 5m, CL 15m and ES 15m. **No cliff exists in either dimension**, so both stay open
and the engine records the quantities without separating the subtypes
(`measurements.record_flat_subtype`).

**OQ-10 — "slightly" vs "substantially" beyond wave A's end.** Where wave C lands is a broad
continuum: p5 = 0.17, p25 = 0.69, p50 = 1.29, p75 = 2.54, p95 = 5.98 (in units of |wave A|). Every
large consecutive gap sits at p97 or beyond — tail sparsity, not a regime boundary. There is no
trough anywhere that could mark the end of "slightly" and the start of "substantially".

**OQ-09 — "near" the start of wave A.** Wave B's retracement of wave A runs *continuously through
1.00* with no trough at all: p25 = 0.37, p50 = 0.65, p75 = 1.21, and only **9%** of flats land
within ±10% of 1.00. "Near" has no natural width to discover.

#### A correction, and one exact rule that was overlooked

The implementation note in `correction.py` claimed Regular and Expanded were *"separated ONLY by
slightly-vs-substantially"*. **That was wrong**, and the summary table above already showed why:
the wave-B column is a second, independent discriminator, and **FLE-01's half of it is exact.**

**FLE-01 — "wave B of the 3-3-5 pattern terminates beyond the starting level of wave A"** — is a
binary geometric test. It needs no threshold, no tolerance and no Open Question, exactly like
FLU-01, which already ships as a gate. It is marked *Not implemented* above rather than *Blocked*,
so this is an unactioned extraction gap, not a reference gap. **33.5% of real flats (118 of 352)
satisfy it.**

What FLE-01 buys and what it does not:

- It separates **Expanded from NOT-Expanded**, exactly and without inventing anything.
- It does **not** hand us Regular Flat. Regular's own two statements are *both* vague ("near",
  "slightly beyond"), so Regular has **no exact criterion at all** and cannot be gated under any
  resolution of OQ-10 alone.
- Promoting it to a gate would collide with Running Flat: **29 of the 34** structures satisfying
  FLE-01 also satisfy FLU-01, and the reference states no precedence between them. That is
  recorded as **OQ-27**.

FLE-01 is therefore **measured but not gating**, pending a project decision.

#### OQ-05 investigated 2026-08-10 — measured, still unresolved

The one Open Question with engine-wide reach: it blocks every discrete
Fibonacci ratio from ever being declared "matched". Investigated on three
independent fronts, all negative. **OQ-05 stays open and match/no-match is
never computed.** Recorded here so it is not re-investigated.

##### 1. The reference re-verified — and it writes ranges when it means them

The source was re-fetched and searched for tolerance language. Three of the
four categories are empty:

| Looked for | Found |
|---|---|
| "approximately" / "about" / "near" / "roughly" applied to a ratio | **nothing** |
| any statement on how precise a ratio must be | **nothing** |
| tolerance / band / zone / area / margin around a level | **nothing** |
| a ratio stated as an explicit **range** | **three** |

The fourth row is the interpretive finding. Three relationships *are* written
as ranges — IMP-F04's *"inverse **123.6 – 161.8%** retracement of wave 4"*,
FLE-F02's *"**123.6% – 161.8%** of wave AB"*, FLU-F02's *"**61.8% – 100%** of
wave AB"* — while everywhere else the values are enumerated discretely
("50%, 61.8%, 76.4%, or 85.4%").

**The author demonstrably knows how to express a band and wrote one where a
band was meant.** That is positive evidence the discrete lists are discrete by
intent, not band-centres with an unstated width. It is the same principle that
let DT-05's inequality through: implement what the source states, in the form
it states it.

##### 2. Attribution corrected — OQ-05 blocks 14 rules, not 16

A stated range needs no tolerance: `123.6 ≤ r ≤ 161.8` is directly evaluable.
So OQ-05 never applied to **FLE-F02** or **FLU-F02**; this table already had
them as `Blocked (OQ-11)`, but `validation.py`'s registry listed them under
OQ-05. Corrected — they stay blocked, by OQ-11's undefined "wave AB" base.

**IMP-F04** was inconsistent in the other direction: this table listed only
OQ-07, the registry only OQ-05. It has three bases — one undefined
("inverse retracement", OQ-07) and two discrete ("equal to wave 1",
"61.8% of wave 1-3", OQ-05). It now carries **both**.

##### 3. No empirical clustering — including a false positive that was caught

If real ratios clustered on the stated values, the clustering width would BE
an empirically derived tolerance, exactly as D-13 was derived. They do not.

A first pass compared each family's mean distance-to-nearest-target against
randomly placed targets, and returned **IMP-F03 at p = 0.018** — an apparent
signal. **It was an artifact.** That null is confounded: wave 4's targets
(0.146 / 0.236 / 0.382) all sit in the naturally dense low end of the window —
the engine's own IMP-05 territory gate and the "no more than 50%" cap force
wave 4 to be small — so they beat targets scattered across a mostly-empty
range *without any clustering on the target values themselves*.

Two density-controlled nulls remove the confound. **Shift** slides the real
target set by a random offset, preserving its internal spacing and its region,
so only clustering *on the values* can win. **Empirical** draws fake targets
from the observed data itself, preserving the density profile exactly.

| Rule | p (shift) | p (empirical) | Verdict |
|---|---|---|---|
| IMP-F01 | 0.134 | 0.753 | not special |
| IMP-F03 | 0.051 | 0.093 | **apparent signal collapses** |
| IMP-F04 | 0.143 | 0.277 | not special |
| ZZ-F01 | 0.377 | 0.994 | not special |
| ZZ-F02 | 0.066 | 0.486 | not special |

**0 of 5 families significant** at α = 0.01 (Bonferroni across five tests), and
none survive *both* controls even at an uncorrected 0.05.

##### 4. No single global tolerance could work anyway

Width required to call half the observed ratios "matched":

| Rule | ±width for 50% |
|---|---|
| IMP-F03 | ±0.035 |
| IMP-F01 | ±0.065 |
| ZZ-F02 | ±0.157 |
| ZZ-F01 | ±0.196 |
| IMP-F04 | ±0.397 |

An **11× spread**. This eliminates, on evidence, the first of the three options
OQ-05 poses ("a single global ±%, per-ratio bands, or one min–max envelope?").
A conventional ±3% sits below even the 25% match threshold for every family
except IMP-F03 — it would match almost nothing.

##### Conclusion

Ratios stay **computed and reported; match/no-match stays uncomputed**. Three
independent lines converge: the reference states no tolerance and shows it
writes ranges deliberately; the data shows no clustering once density is
controlled for; and no single tolerance could serve all families. Adopting a
common convention such as ±3% is the one option the evidence actively
contradicts rather than merely failing to support.

### 12. Triangle (§5.3)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| TRI-01 | Triangle | all | "Corrective structure labelled as ABCDE" | **M** | pivots | leg count == 5 | — | — | 5.3 | **Exact; used to form candidates, never to gate** — see §12 investigation |
| TRI-02 | Triangle | — | "Usually happens in wave B or wave 4" | G | pivots, sub | host label ∈ {B, 4} | — | — | 5.3 | Not implemented |
| TRI-03 | Triangle | all | "Subdivided into three (3-3-3-3-3)" | **M** | sub | every leg subdivides into 3 | — | — | 5.3 | **Exact; forms candidates (8.4% pass), never gates.** Loose reading inherits OQ-25 |
| TRI-04 | Triangle | A–E | "Subdivision of ABCDE can be either abc, wxy, or flat" | **M** (permissive) | sub | each leg ∈ {abc, wxy, flat} | — | — | 5.3 | Blocked (OQ-12) |
| TRI-05 | Triangle | — | "A triangle is a sideways movement that is associated with decreasing volume and volatility" | G | OHLC, vol | net displacement / path length | — | volume | 5.3 | Blocked (OQ-12 for "sideways", OQ-22 for volume) — ratio **measured**; no cliff exists (bootstrap: 0 of 3 modes stable) |
| TRI-06 | Triangle | — | "RSI also needs to support the triangle in every time frame" | G | mom (RSI) | RSI at each of the 6 pivots | — | **RSI** | 5.3 | Blocked (OQ-13) — readings **measured** (326/328 complete); "supports" never decided |
| TRI-07 | Triangle | — | Variants named: ascending, descending, contracting, expanding — **and nothing more; the geometry is only in a graphic, never in prose** | G | pivots | trendline slopes of A-C-E and B-D | — | — | 5.3 | Blocked (OQ-12) — both slopes **measured**; no name assigned |

**No Fibonacci ratios are stated for any triangle wave.** No rule for wave D or wave E
individually. TRI-04's permitted set covers nearly every corrective structure, so it does almost
no discriminating work. See **OQ-12** — Triangle is the weakest-specified structure in the
reference by a wide margin.

#### OQ-12 / OQ-13 investigated 2026-08-10 — measured, still unresolved

Investigated with the same method as OQ-24 and OQ-09/OQ-10. Outcome: an exact
rule *was* found, and it still does not gate. Candidates are measured
(`triangle.py`, surfaced as `AnalysisResult.triangle_candidates`) and
`StructureType` gains **no** `TRIANGLE` member.

##### 1. The reference re-verified

Re-fetched rather than trusting the Phase-2 extraction. Confirmed empty:
**no rule for wave D or wave E**, **no Fibonacci ratio of any kind**, **nothing
about what follows a triangle**.

**Correction to this document's earlier framing.** The four variants were
described here as lacking *quantification*. That understates it: ascending,
descending, contracting and expanding are **named and nothing else** — the
distinguishing geometry appears only in a *graphic*, never in prose. There is
no text to extract, quantified or otherwise.

##### 2. An exact rule was found — and the old "near-vacuous" claim was wrong

**TRI-01** ("labelled as ABCDE" → 5 sides) and **TRI-03** ("3-3-3-3-3") are
both **M** and *Not implemented* — the same signature FLE-01 had.

`validation.py` recorded these as "a near-vacuous subdivision gate". **Measured,
that is false:**

| | count |
|---|---|
| five-leg windows examined | 3,912 |
| passing TRI-01 + TRI-03 | **328 (8.4%)** |

For scale, the engine confirms 318 flats and 173 zigzags on the same data. The
gate is genuinely selective. It nonetheless stays ungated for three reasons:

1. **It inherits OQ-25.** Read strictly — "subdivided into three" meaning
   exactly three finer legs per side — the gate finds **1 candidate in 3,912**.
   The 328 come from the *loose* predicate `diagonal.py` already applies to
   LD-03/ED-03's identical `3-3-3-3-3`, so Triangle rests on the same
   unresolved reading rather than standing on its own.
2. **Nothing can constrain where a triangle occurs.** TRI-02 says *"**usually**
   happens in wave B or wave 4"* — guideline grammar, so gating on it would be
   an OQ-01 decision. It is moot regardless: only **6 of 328** candidates sit
   in an impulse wave 4 or a zigzag/flat wave B.
3. **The definitional property would be the one thing unenforced.** The
   reference opens *"a triangle is a sideways movement"*, and **21% of
   candidates (69 of 328)** have net displacement above 50% of their path
   length — plainly trending. Emitting a structure named `TRIANGLE` for those
   would be worse than emitting nothing.

Point 3 is what separates this from FLE-01. FLE-01 is a *complete* criterion
for what it claims; TRI-01 + TRI-03 is an **incomplete** criterion for
"triangle", because the definitional content of the word is exactly what it
omits.

##### 3. No threshold for "sideways" — and a false signal caught

Net displacement / path length across the 328 candidates is a broad plateau:
p5 = 0.017, p25 = 0.160, p50 = 0.312, p75 = 0.479, p95 = 0.706.

The histogram initially showed **three modes**, which would have been the
cliff. A 1,000-sample bootstrap rejected it:

| | |
|---|---|
| modes stable in >90% of resamples | **0 of 3** |
| best bin (0.65) | 70.5% |
| adjacent bins also called modes | 20–30% |
| mode *count* across resamples | varies 1–5; three only 58.9% of the time |

Ripples on a plateau, not regimes. The same discipline that caught the IMP-F03
false positive during the OQ-05 investigation.

##### 4. The Diagonal overlap — expected, and not found

`3-3-3-3-3` is an explicitly permitted **diagonal** shape (LD-03/ED-03), so a
collision was expected. **Measured overlap: zero** — 0 of 328 candidates
coincide with or even overlap a confirmed diagonal, because diagonals are
enumerated only inside impulse wave-1/wave-5 host legs, a different basis.

No practical clash, but the principle stands: with no gateable host rule, a
triangle would be defined as *"a 3-3-3-3-3 that is not inside an impulse
host"* — a definition by exclusion the reference never gives.

##### 5. OQ-13 (RSI) — measurable, not decidable

RSI is readable at all six pivots for **326 of 328** candidates, and
`momentum.rsi_series` already exists for IMP-06, so recording it is trivial.
What is undefined is *"supports"*: no direction, no threshold, no comparison
is stated, and *"in every time frame"* has no meaning in a single-timeframe
engine. Readings are recorded; the verdict is not.

##### What is recorded

Per candidate, all tagged `blocked_by: ["OQ-12", "OQ-13"]`:
`TRI-03_subdivision_counts`, `TRI-05_net_over_path`, `TRI-07_slope_A_C_E`,
`TRI-07_slope_B_D`, `TRI-06_rsi_at_pivots`, plus `confirm_index` so no
consumer can treat a candidate as known before its closing pivot confirmed.

### 13. Double Three (§5.4)

| ID | Structure | Wave | Rule (verbatim) | M/G | Input | Measurement | Fib | Mom | § | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| DT-01 | Double Three | all | "Double three is a sideways combination of two corrective patterns" labelled **WXY** | **M** | pivots | leg count == 3 (W, X, Y) | — | — | 5.4 | Not implemented |
| DT-02 | Double Three | all | 7-swing structure | **M** | pivots | total sub-swing count == 7 | — | — | 5.4 | Not implemented |
| DT-03 | Double Three | W, Y | "Wave W and wave Y subdivision can be zigzag, flat, double three of smaller degree, or triple three of smaller degree" | **M** | sub, deg | sub(W), sub(Y) ∈ {zigzag, flat, DT(−1 deg), TT(−1 deg)} | — | — | 5.4 | **Specified 2026-08-10** — OQ-18 resolved (depth cap) |
| DT-04 | Double Three | X | "Wave X can be any corrective structure" | **M** (permissive) | sub | sub(X) ∈ any corrective | — | — | 5.4 | Not implemented |
| DT-F01 | Double Three | X | "Wave X = 50%, 61.8%, 76.4%, or 85.4% of wave W" | G | pivots | len(X)/len(W) | 50 / 61.8 / 76.4 / 85.4 % | — | 5.4 | Blocked (OQ-05) |
| DT-F02 | Double Three | Y | "Wave Y = 61.8%, 100%, or 123.6% of wave W" | G | pivots | len(Y)/len(W) | 61.8 / 100 / 123.6 % | — | 5.4 | Blocked (OQ-05) |
| DT-05 | Double Three | Y | **"Wave Y can not pass 161.8% of wave W"** | **M** | pivots | len(Y) <= 1.618 × len(W) | 161.8% (ceiling) | — | 5.4 | **Specified 2026-08-10** — added by the extraction correction below |

### 14. Triple Three (§5.5)

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

### Open Questions

The reference is ambiguous, silent, or self-conflicting on each of these. **Per the Phase 2
instruction, no rule has been invented to fill any of these gaps.** Each needs a decision
before it can enter the Phase 3 SRS.

| OQ | Affects | Question |
|---|---|---|
| ~~**OQ-01**~~ | Everything | **RESOLVED 2026-08-10 — documentation only, no behaviour change.** The M/G split IS the adopted classification, restated honestly as project judgement *informed by* grammar rather than derived from it. Three divergences documented (IMP-06/TRI-06 same modal, opposite tiers — deliberate; LD-03/ED-03 same constraint, different grammar; IMP-F03's embedded cap, tracked as OQ-08). Every gate unchanged; blast radius measured and recorded. See [the investigation](#oq-01-investigated-2026-08-10--resolved-as-documentation-no-behaviour-change). |
| ~~**OQ-02**~~ | IMP-04 | **✅ RESOLVED 2026-08-09 — absolute price distance.** *(Original question: "shortest" by what — absolute price distance, percentage move, log distance, or bar count? The reference never says; these disagree on real data.)* See [resolution](#oq-02-resolution--wave-3-shortest-measure). |
| ~~**OQ-03**~~ | IMP-05 | **✅ RESOLVED 2026-08-09 — pivot-price interval overlap.** *(Original question: is the test against wave 1's terminal price or its full intrabar range? And wave 4's terminal price or its own extreme? Four readings.)* See [resolution](#oq-03-resolution--wave-4-price-territory). |
| ~~**OQ-04**~~ | IMP-06, WP-10 | **✅ RESOLVED 2026-08-09 — see "OQ-04 resolution" below.** *(Original question: "Momentum divergence" — which indicator, what period, measured between which two points, and what magnitude counts? WP-10 gives only a prose definition. IMP-06 is stated as a hard requirement for every impulse, which made the entire impulse detector depend on an undefined quantity.)* |
| **OQ-05** | 14 Fibonacci rules *(not 16 — corrected 2026-08-10; FLE-F02 and FLU-F02 state RANGES and need no tolerance)* | **INVESTIGATED 2026-08-10, STILL UNRESOLVED.** Every ratio is a **discrete exact value** ("50%, 61.8%, 76.4%, or 85.4%"), never a band. Exact float equality never matches real price data. What tolerance? A single global ±%, per-ratio bands, or convert each discrete set to one min–max envelope? **All three investigated and none justified** — see [the OQ-05 investigation](#oq-05-investigated-2026-08-10--measured-still-unresolved). The global-±% option is eliminated on evidence (11× spread in required width). |
| **OQ-06** | IMP-F02 | "161.8% … of wave **1-2**" — is the base the net displacement from start of wave 1 to end of wave 2, or the length of wave 1 projected from the end of wave 2? Standard practice differs from the literal reading. |
| **OQ-07** | IMP-F04, FIB-06 | "**inverse** 123.6 – 161.8% retracement of wave 4" — "inverse retracement" is used but never defined on the page. |
| **OQ-08** | IMP-F03, WP-07 | Wave 4: §3.1 says "14.6%, 23.6%, or 38.2% of wave 3 **but no more than 50%**"; §4.3 says "typically retraces **less than 38.2%**". Is 50% a hard cap or a guideline, and how does it interact with IMP-05 (overlap), which is the actual structural constraint? Two sections give different numbers. |
| **OQ-09** | FLR-01 | **INVESTIGATED 2026-08-10, STILL UNRESOLVED.** Regular Flat wave B "terminates **near** the start of wave A" — "near" is unquantified, and the paired Fibonacci value (90%) is a **single point** with no tolerance. Data derivation failed: across 356 real flats wave B's retracement runs continuously through 1.00 with no trough (p25 0.37, p50 0.65, p75 1.21; only 9% within ±10% of 1.00). Regular Flat has **no exact criterion of its own**, so it cannot be gated at all. Quantities recorded; verdict withheld. |
| **OQ-10** | FLR-02, FLE-02 | **INVESTIGATED 2026-08-10, STILL UNRESOLVED.** "**slightly** beyond" (Regular) vs "**substantially** beyond" (Expanded), neither quantified. Data derivation failed: wave C's landing point is a broad continuum (p5 0.17 to p95 5.98 × |A|) with every large gap at p97+. **Correction:** this was previously described as *the only* stated discriminator between the subtypes. It is not — the wave-B test is a second one, and **FLE-01's half of it is exact** (see §11.3). |
| **OQ-11** | FLR-F02, FLE-F02, FLU-F02 | All three flat subtypes measure wave C "of wave **AB**". What is "wave AB" — the net A-to-B displacement, the sum of len(A)+len(B), or wave A's length? Undefined. |
| **OQ-12** *(investigated 2026-08-10; candidates measured, see §12)* | TRI-01…07 | Triangle has **no Fibonacci ratios, no per-wave rules for D or E, no rule distinguishing the four named variants**, and TRI-04 permits nearly any corrective subdivision. As written, a Triangle detector would match almost any 5-leg sideways move. Is Triangle in scope at all for v1? |
| **OQ-13** *(investigated 2026-08-10; RSI recorded, "supports" undecided)* | TRI-06 | "RSI also needs to support the triangle in **every time frame**" — "support" is undefined, and "every time frame" is undefined in a single-timeframe backtest. This is the only place RSI is named as a requirement. |
| ~~**OQ-14**~~ | MS-01…03 | **INVESTIGATED 2026-08-10 — CONFIRMED NOT IMPLEMENTABLE (tier NI), CLOSED.** Re-verified against the live reference: no numeric sequence, no worked example, no labelling scheme, no complete-vs-incomplete criterion. The definition is circular — MS-01 says "incomplete", MS-03 defines completeness by "the numbers in the motive sequence", and the numbers are never given. MS-03's "much **like** the Fibonacci number sequence" is a simile, not an identity, so substituting Fibonacci numbers would author the rule rather than implement it. Not a pending decision: the absent content **is** the rule. Original wording: Motive Sequence is defined entirely by reference to "the numbers in the motive sequence" — **and those numbers are never stated on the page.** The concept cannot be implemented from this source. Do we drop it, or source the numbers elsewhere (out of scope for this reference)? |
| **OQ-15** | LD-02, ED-02 | Both diagonals: overlap is "**not a condition**" and the wedge shape is unquantified. With position (LD-01/ED-01) and subdivision (LD-03/ED-03) as the only gates, what actually makes a diagonal a diagonal rather than a plain 5-leg move? |
| **OQ-16** | LD-03, ED-03 | Leading and Ending Diagonal permit the **identical** subdivision sets, so shape cannot distinguish them — only host position can. Confirm that's intended. |
| **OQ-17** | DEG-03, DEG-04 | Only 2 of the 9 degrees are mapped to a timeframe, and no rule exists for assigning a degree from price data. How is degree assigned? |
| ~~**OQ-18**~~ | DT-03, TT-03 | **✅ RESOLVED 2026-08-10 — recursion capped at depth 1.** *(Original question: W/Y/Z may themselves be a "double three of smaller degree", recursive with no stated depth limit.)* The cap is derived from the pivot ladder's expressive limit, not chosen: correctives occur only at scale 2, so a combination needs scale 3 and a nested one scale 4 — two levels would need scale 5, beyond the 4-scale ladder. See [OQ-18 resolution](#oq-18-resolution--doubletriple-three-recursion-depth). |
| **OQ-27** | FLE-01, FLU-01 | **NEW 2026-08-10, UNRESOLVED.** Running Flat and Expanded Flat overlap and the reference states no precedence. FLE-01 (wave B beyond wave A's start) and FLU-01 (wave C short of wave A's end) are both exact and both mandatory-tier, and **29 of 34** real structures satisfy both. Which label wins is undefined. Dormant while FLE-01 does not gate; live the moment it does. |
| **OQ-26** | DT-02, TT-02 | **NEW 2026-08-10, UNRESOLVED.** The reference's own swing arithmetic is inconsistent. DT-02 says WXY is a **7**-swing structure, but DT-04 says X is "any corrective structure" and GEN-06 says correctives move in three — 3+3+3 is **9**, not 7. The stated count only works if X contributes a single swing. TT is identical: 11 = 3+1+3+1+3. Gating on the count would contradict DT-04; ignoring DT-02 would drop a mandatory-tier statement. Swing count is therefore **recorded as a measurement and never gated**, and every combination carries `blocked_by: ["OQ-26"]`. |
| **OQ-19** | ZZ-F03 | The reference itself flags that a Zigzag's wave C at 161.8% of A is ambiguous with a wave 3 of an impulse, and offers "whether the third swing has extension or not" as the tiebreak — but "extension" is itself undefined (OQ-24). Circular. |
| **OQ-20** | GEN-04, GEN-06 | §5 says corrective waves "move in three, but **never** in five"; §1.6/§3.5 says motive waves "can unfold in **3 waves**". A 3-swing move is therefore both possibly-corrective and possibly-motive, with **no stated discriminator**. This is the reference's central modernization and its central ambiguity. |
| ~~**OQ-21**~~ | All | **✅ RESOLVED 2026-08-09 — build an independent, Elliott-specific pivot detector; do not consume the existing swing/zigzag modules.** *(Original question: the reference assumes waves/pivots are already identified and gives no rule for detecting wave boundaries from raw price.)* The reference **still** says nothing on this; the detector is entirely a project decision. See [OQ-21 resolution](#oq-21-resolution--elliott-specific-pivot-detection). |
| **OQ-22** | WP-02/04/08/11/12/13, TRI-05 | Every volume statement is qualitative ("lower than", "well below", "picks up", "decreasing") with no threshold or measurement window. Also: volume is present in our OHLCV but is **synthetic** for the default data source, so volume-gated rules would be meaningless on synthetic backtests. |
| **OQ-23** | FLE-F01, FLU-F01 | Expanded Flat and Running Flat both state wave B = **123.6%** of wave A. Wave B cannot discriminate between them; only wave C can. Confirm. |
| **OQ-24** | EXT-01, EXT-02, ZZ-F03 | **INVESTIGATED 2026-08-10, STILL UNRESOLVED.** "Extension" / "elongated" / "exaggerated subdivisions" — no numeric definition anywhere. Data-derivation was attempted and failed: five formulations over 1,142 impulses all decay smoothly with no cliff, and EXT-02's subdivision half is unmeasurable on 98.8% of the population and names a different wave than length on 36% of the rest. **Independent of OQ-05** — unlike DT-05 there is no stated inequality to lift. Quantities are recorded; the verdict is withheld. See [§5](#oq-24-investigated-2026-08-10--measured-still-unresolved). |

---

### OQ-18 resolution — Double/Triple Three recursion depth

**Status: RESOLVED 2026-08-10 by project decision.**

> ⚠ **Not from the reference.** The page says W/Y/Z may be "a double three or triple three of
> smaller degree" and **never states a termination depth** (verified against the source). The cap
> below is a **project decision**.

#### Decision

`max_combination_depth = 1`. A Double/Triple Three may be built from zigzag/flat components
(depth 0), or from a depth-0 Double/Triple Three (depth 1). No deeper.

#### Why 1 — derived from the ladder, not chosen

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

#### Consequences

| Item | Effect |
|---|---|
| DT-01, DT-03, DT-04, TT-01, TT-03, TT-04 | Blocked → **specified** |
| DT-05, TT-05 | Newly extracted and **specified** (mandatory ceilings) |
| DT-02, TT-02 | **Still blocked — OQ-26**, recorded as a measurement only |
| DT-F01/F02, TT-F01/F02 | Still blocked on **OQ-05** (discrete ratios, no tolerance) |
| Real-data yield | 11 Double Threes + 1 Triple Three across four configurations — rare, as predicted |

---

### OQ-21 resolution — Elliott-specific pivot detection

**Status: RESOLVED 2026-08-09 by project decision.**

> ⚠ **Nothing in this resolution comes from the reference.** The EWF page assumes waves are
> already identified and states no detection rule of any kind. Pivot detection is **100% project
> engineering** (tier EN). It is recorded here because it is the engine's input contract, not
> because the reference implies it.

#### Decision

Build a **brand-new, Elliott-specific pivot detector** inside the new
`src/analysis/elliott_wave/` package. The engine SHALL NOT reuse, import, wrap, subclass, or
consume the **output** of:

- `src/analysis/swing_identification.py`
- `src/analysis/zigzag.py`
- any other existing pivot/swing detection code in this repository

Those files remain **untouched and unmodified** — and, per this decision, **also unconsumed**.
"Don't touch" is now strengthened to "don't touch *and* don't depend on."

#### Mechanism — threshold-based directional change

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

#### Design decisions

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

#### Input

`BacktestResults.price_data` — the canonical OHLCV DataFrame already held in the store. The
detector **re-fetches nothing** and mutates nothing.

#### Threshold values — settled 2026-08-09 (D-13 closed)

- **θ_base = 0.20%, ratio r = 2.5, S = 4 scales** → ladder 0.20 / 0.50 / 1.25 / 3.125%.
  Calibrated against real CL and ES data plus the deterministic synthetic generator; the
  measurements and reasoning are in
  [ELLIOTT_WAVE_ARCHITECTURE.md](#architecture) §5. These remain
  **configuration, not rules** — tunable per request.

#### What this resolution still does NOT settle
- **OQ-17** (degree assignment) stays open — P-7 exists precisely to avoid pre-empting it.
- **Cross-scale nesting is not assumed.** Directional change at a coarse θ does **not**
  guarantee its extremes are a subset of a finer θ's extremes. Any hierarchy construction must
  handle non-nesting explicitly rather than assume containment. Flagged for Phase 4.

---

### OQ-02 resolution — Wave 3 "shortest" measure

**Status: RESOLVED 2026-08-09 by project decision.**

> ⚠ **Not from the reference.** The EWF page says only *"Wave 3 can not be the shortest wave of
> the three impulse waves, namely wave 1, 3, and 5"* and never states how length is measured.
> The measure below is a **project decision**.

#### Decision

**Wave length is ABSOLUTE PRICE DISTANCE**, computed from pivot prices:

```
len(w) = | P(end pivot of w) − P(start pivot of w) |
```

**Explicitly rejected:** percentage distance, logarithmic distance, and bar count (time).

**IMP-04 gate:** `len(wave 3) > min( len(wave 1), len(wave 5) )`

**No tolerance, threshold, or buffer** is introduced. The comparison is exact.

#### Consistency with existing decisions

This uses the same **pivot-price** convention already adopted in **FR-3.1a.7** for IMP-06.
Checked for contradiction — **none found**; the two decisions reinforce each other, so
FR-3.1a.7 is left unchanged.

---

### OQ-03 resolution — Wave 4 price territory

**Status: RESOLVED 2026-08-09 by project decision.**

> ⚠ **Not from the reference.** The EWF page says only *"Wave 4 does not overlap with the price
> territory of wave 1"* and never defines "price territory". The reading below is a **project
> decision**.

#### Decision

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

#### Note on pivot prices vs intrabar extremes

For a high pivot the pivot price *is* the bar's high, and for a low pivot it *is* the bar's low
(DM-1). Because pivots alternate high/low (FR-1.3), a wave's two endpoint pivots are its own
extremes by construction, so the endpoint-pivot reading and the "extremes of this wave" reading
coincide. What the decision rules out is scanning **all** bars inside wave 1's span for a more
extreme value than its own endpoints.

#### Consistency with existing decisions

Same pivot-price convention as **FR-3.1a.7** and the OQ-02 resolution. **No contradiction.**

---

### OQ-04 resolution — Wave 5 momentum divergence

**Status: RESOLVED 2026-08-09 by project decision.** Three Open Questions are now resolved
(OQ-02, OQ-03, OQ-04); the other 21 remain open.

> ⚠ **This definition does not come from the reference.** The EWF page names no indicator, no
> period, and no comparison procedure. The definition below is a **project decision** made because
> IMP-06 is mandatory and therefore had to be made computable. It is recorded here as a decision,
> not presented as source-defined behavior.

#### Decision

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

#### What this resolution deliberately does *not* do

- **No tolerance/threshold.** "Lower"/"higher" is a strict directional comparison. No epsilon, no
  minimum divergence magnitude, no RSI overbought/oversold levels are involved. (The platform's
  RSI(13) chart bands are 70/30, but they play **no part** in this rule.)
- **No other Open Question is resolved by this one.** In particular **OQ-05 and OQ-20
  remain open.**
- **On its own it did not unblock the impulse detector** — IMP-04 and IMP-05 were still
  undefined at that point. They were subsequently resolved by the OQ-02 and OQ-03 decisions
  above, which is what actually cleared the impulse gate set.

#### Consequences

| Item | Effect |
|---|---|
| IMP-06, WP-10 | Blocked → **specified** |
| **Impulse overall** | Was still blocked after OQ-04 alone; **now fully specified** once OQ-02 and OQ-03 were also resolved |
| Engine input contract | **Extended.** IMP-06 needs the `close` price series, so pivots alone are no longer a sufficient input. This is a real change to the engine's input requirements. |
| New dependency | The Elliott module now depends on `src/analysis/indicators.py` (read-only). |

#### Partial constraint on OQ-01 *(superseded 2026-08-10 — OQ-01 is now resolved)*

The same decision states that "Guidelines" must **not** be treated as non-gating as a blanket
rule. At the time that ruled out one of OQ-01's two candidate answers without settling the
question. **OQ-01 was investigated and closed on 2026-08-10** — the split is adopted, restated as
project judgement informed by grammar rather than derived from it, with no behavioural change.
See [the investigation](#oq-01-investigated-2026-08-10--resolved-as-documentation-no-behaviour-change).

---

### Coverage summary

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
the 16 Fibonacci rules (14 blocked on tolerance, **OQ-05**; FLE-F02 and FLU-F02 state ranges and are blocked instead by **OQ-11** — none of the 16 gate anything), the
Regular/Expanded flat discriminators (**OQ-09** / **OQ-10** — investigated 2026-08-10, no cliff; but FLE-01 alone is exact and unactioned, see §11.3), Triangle (**OQ-12** / **OQ-13**),
and extensions (**OQ-24**). Nested combinations are no longer blocked: **OQ-18 is resolved** by a depth-1 cap, though DT-02/TT-02's swing counts remain open as **OQ-26**.

**The OQ-21 resolution deliberately does not move these numbers.** OQ-21 was never a *per-rule*
blocker — no individual rule in this inventory cites it. It was an engine-level precondition: the
rules were computable in principle but had no input to compute against. Resolving it makes the
engine runnable without reclassifying a single rule, and the totals above are unchanged as a
result. Reporting an increase here would have been misleading.

---

### Provenance and integrity notes

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

---

<a id="requirements"></a>

## Part 2 — Elliott Wave — Software Requirements Specification

**Phase 3 deliverable.** Version 0.1 (DRAFT — not approved for implementation).
Written 2026-08-09.

**Sole rule authority:** [docs/ELLIOTT_WAVE_RULES.md](#rules) (94 rule records,
27 Open Questions), which in turn derives solely from
<https://elliottwave-forecast.com/elliott-wave-theory/>.

> **This document specifies requirements. It contains no production code and mandates none yet.**
>
> **Revision 1.4 — 2026-08-10.** **OQ-01 RESOLVED as documentation, no behaviour change**
> (§8.3, FR-8.3.1–4). The M/G tiers are adopted as project judgement *informed by* grammar, not
> derived from it — the previous "derived purely from the grammar" wording overstated the
> rigour. Three divergences documented, blast radius measured per rule, **no gate
> reclassified**. Tally: **6 resolved, 20 unresolved, 1 not implementable**. Previously —
> **Revision 1.3 — 2026-08-10.** **OQ-14 investigated and closed as not implementable**
> (FR-3.5.2) — re-verified against the live reference, nothing missed. Reclassified out of the
> unresolved tally: **5 resolved, 21 unresolved, 1 not implementable**. No code. Previously —
> **Revision 1.2 — 2026-08-10.** **OQ-12/OQ-13 investigated and left open** (FR-3.8.1–2).
> TRI-01/TRI-03 turn out to be exact and selective (8.4%), not "near-vacuous" as previously
> recorded — corrected — but they still cannot gate, chiefly because 21% of candidates
> contradict the reference's own definition of "sideways". Candidates are measured instead.
> Previously —
> **Revision 1.1 — 2026-08-10.** **OQ-05 investigated and left open** (FR-4.2a) — no tolerance
> language in the reference, no empirical clustering once density is controlled for, and an 11x
> spread in the width any tolerance would need. **Scope corrected**: OQ-05 blocks 14 rules, not
> 16 (FR-4.2b). No behaviour change. Previously —
> **Revision 1.0 — 2026-08-10.** **OQ-09/OQ-10 investigated and left open** — no cliff in 356
> real flats; quantities now measured (FR-3.7.1a–c). **FR-3.7.1 corrected**: Regular and
> Expanded are NOT separated only by slightly-vs-substantially — FLE-01 is a second, exact
> discriminator, currently unactioned. **New OQ-27** records the Running/Expanded precedence
> collision that gating FLE-01 would create. Previously —
> **Revision 0.9 — 2026-08-10.** **OQ-24 investigated and deliberately left open** — extension
> is now MEASURED but never classified (FR-3.2.2 to FR-3.2.4). Data derivation was attempted
> with the D-13 method and failed: no cliff in any of five formulations. Confirmed independent
> of OQ-05. Previously —
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
> [ELLIOTT_WAVE_ARCHITECTURE.md](#architecture) §5. **D-02b and D-02c are
> confirmed closed** (pivot-price reading kept; reject-on-tie kept). **Four Open Questions
> are RESOLVED by project decision:**
> **OQ-21** — the engine gets its own independent, Elliott-specific pivot detector, which neither
> modifies **nor consumes** `swing_identification.py` / `zigzag.py` (§4a). Plus, from revision 0.3:
> **OQ-02** (wave 3 "shortest" = absolute price distance) and **OQ-03** (wave 4 territory =
> pivot-price interval overlap), both §6.1b; and **OQ-04** (divergence = RSI(13) directional
> comparison), §6.1a. All three are tier **EN** — decisions, **not** source-defined behavior; the
> reference says nothing on any of them. **All six Impulse gates are now specified and the §8
> dependency chain is broken.** **The other 20 Open Questions remain unresolved**, and OQ-01 is
> *partially constrained* but explicitly **not** resolved (§8.3).
> Where a requirement depends on an open question it is marked **BLOCKED** or **UNDEFINED** and
> its behavior is deliberately left unspecified. No classical Elliott Wave knowledge
> (Prechter/Frost, Neely, or common practice) has been used to fill any gap.

---

### 1. Purpose and scope

#### 1.1 Purpose

Define what an Elliott Wave analysis capability for this platform must do, given **only** what
the EWF reference actually states — and define with equal precision what it **cannot** do until
specific decisions are made.

#### 1.2 In scope for v1

- A backend analysis module that consumes an ordered pivot sequence and emits labelled wave
  structure candidates with recorded measurements.
- One read-only API sub-resource exposing that output for a stored backtest.
- One **dedicated** frontend tab containing one **dedicated** chart.
- A test suite covering every implementable rule and guarding every blocked one.

#### 1.3 Explicitly out of scope for v1

| Excluded | Reason |
|---|---|
| Any change to the Price & Trades chart | Elliott Wave is a dedicated tab with its own chart. The Price & Trades chart stays a plain Price & Trades chart. See §9. |
| Elliott Wave in the exported HTML report | Not requested for this phase, and the report path duplicates chart logic in Python (`api/report/charts.py`), doubling the surface. Deferred — see §12, D-07. |
| Trade signals, entries, exits, or any strategy influence | Analysis and display only. |
| Forecasting / projection of incomplete structures | The reference describes completed structures; it states no forecasting procedure. |
| Confidence scores or probability rankings | The reference states no weighting or scoring function anywhere. See §7.4. |
| Multi-timeframe analysis | Required by TRI-06 ("every time frame") but undefined — see OQ-13. |

#### 1.4 Status of this specification

At revision 0.4 the core path is **fully specified end to end**: an independent pivot detector
(§4a) feeds Impulse, Diagonals, Zigzag, generic Flat and Running Flat, all of whose gates are
settled (§8.1). Regular/Expanded Flat, Triangle, Double/Triple Three, Extension and Motive
Sequence remain blocked on their own Open Questions and are **out of the v1 core**. One
configuration decision (**D-13**, threshold values) and two boundary confirmations
(**D-02b**, **D-02c**) are outstanding, but no *rule* gap remains on the core path.

---

### 2. Definitions

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

### 3. Requirement classification scheme

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

### 4. Functional requirements — Input

#### FR-1 Pivot input contract

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

##### FR-1.4 resolution — independent detection (project decision)

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

### 4a. Pivot detector requirements

> **Tier EN throughout. Nothing in this section derives from the reference**, which assumes waves
> are already identified. This is 100% project engineering, specified here because it is the
> engine's input contract.

#### FR-1a — Mechanism

| ID | Tier | Requirement |
|---|---|---|
| FR-1a.1 | **EN** | The detector SHALL live in the new `src/analysis/elliott_wave/` package (e.g. `pivots.py`) and SHALL be self-contained. |
| FR-1a.2 | **EN** | It SHALL consume `BacktestResults.price_data` — the canonical OHLCV DataFrame already held in the store — and SHALL NOT re-fetch, reload, or re-derive market data. |
| FR-1a.3 | **EN** | It SHALL NOT mutate the input DataFrame. |
| FR-1a.4 | **EN** | **Detection SHALL use threshold-based directional change**, not an N-bar fractal. A single chronological pass maintains a direction and a running extreme; a pivot is emitted when price reverses from that extreme by at least the scale's threshold theta. |
| FR-1a.5 | **EN** | **Rationale for FR-1a.4, recorded so it can be challenged:** an N-bar fractal is exactly what `swing_identification.py` already implements. Re-deriving that design — even without importing it — would make the detector independent in name only. Directional change confirms on a **price event** rather than a **fixed bar lag**, which also supplies a non-arbitrary confirmation moment. |

#### FR-1b — No look-ahead

| ID | Tier | Requirement |
|---|---|---|
| FR-1b.1 | **EN** | Every pivot SHALL carry **both** `index` (the bar where the extreme occurred) and `confirm_index` (the later bar at which the reversal completed). These SHALL be distinct fields; `confirm_index > index` always. |
| FR-1b.2 | **EN** | Any consumer evaluating bar *t* SHALL use only pivots with `confirm_index <= t`. Using `index` as if the pivot were known at that bar is look-ahead bias and is prohibited. |
| FR-1b.3 | **EN** | The **final, unconfirmed extreme SHALL NOT be emitted** as a pivot. It has no confirmation bar, and emitting it would be precisely the look-ahead FR-1b.1 exists to prevent. |
| FR-1b.4 | **EN** | A test SHALL verify no-look-ahead directly: truncating the input at bar *t* and re-running SHALL reproduce exactly the pivots whose `confirm_index <= t`, with identical prices and indices. |

#### FR-1c — Output contract

| ID | Tier | Requirement |
|---|---|---|
| FR-1c.1 | **EN** | **Pivot price = the bar's own extreme** — `high` for a HIGH pivot, `low` for a LOW pivot. This is the same convention already fixed by FR-3.1a.7 (IMP-06), FR-3.1b.1 (IMP-04) and FR-3.1b.4 (IMP-05). **One convention across the entire engine.** |
| FR-1c.2 | **EN** | Pivots SHALL strictly alternate HIGH/LOW. Guaranteed by construction — direction flips on every emission — satisfying FR-1.3 without a separate post-filter. |
| FR-1c.3 | **EN** | Each pivot SHALL carry an integer `scale` index identifying which threshold produced it (FR-1d.1). |
| FR-1c.4 | **EN** | The emitted pivot record SHALL satisfy DM-1 exactly, so the already-specified Impulse, Diagonal, Zigzag and Flat gates (FR-3.1, FR-3.1b, FR-3.3, FR-3.6, FR-3.7) consume it with no adaptation layer. |

#### FR-1d — Multi-scale ladder

| ID | Tier | Requirement |
|---|---|---|
| FR-1d.1 | **EN** | The detector SHALL run the same pass independently at *S* scales, with geometric thresholds theta_k = theta_base * r^(k-1); scale 1 is finest, scale *S* coarsest. |
| FR-1d.2 | **EN** | **Rationale:** Elliott is inherently hierarchical — IMP-02 requires waves 1/3/5 to subdivide into impulses, and DT-03/TT-03 reference structures "of smaller degree". A single-scale pivot list cannot support nesting at all. |
| FR-1d.3 | **EN** | **`scale` is NOT an Elliott degree.** The detector SHALL emit only an integer scale index. Mapping a scale to one of the reference's 9 named degrees remains **OQ-17, open** — the detector must not pre-empt it. |
| FR-1d.4 | **EN** | **Cross-scale nesting SHALL NOT be assumed.** Directional change at a coarse threshold does not guarantee its extremes are a subset of a finer threshold's extremes. Hierarchy construction SHALL handle non-nesting explicitly. A test SHALL measure the actual containment rate rather than assume it. |

#### FR-1e — Threshold configuration

| ID | Tier | Requirement |
|---|---|---|
| FR-1e.1 | **EN** | The threshold SHALL be **relative (percentage)**, applied to the running extreme's price. |
| FR-1e.2 | **EN** | Volatility-adaptive thresholds (ATR- or stdev-scaled) SHALL NOT be used in v1. **Considered and deferred:** adaptation introduces a second undefined parameter set and makes determinism harder to reason about. It can be added later without changing the pivot contract (FR-1c). |
| FR-1e.3 | **EN — D-13 CLOSED (rev 2, 2026-08-10)** | Defaults: **`theta_base = 0.001` (0.10%), ratio `r = 4.0`, `S = 4` scales** → ladder 0.10 / 0.40 / 1.60 / 6.40%. **Supersedes rev 1 (0.20% / 2.5)**, which was calibrated on pivot density and proved unable to satisfy IMP-02's recursive requirement — zero impulses reached GATED above scale 1. Rev 2 is calibrated on the binding constraint: whether a coarse leg contains a finer window passing **all six** impulse gates (~6% pass rate), not merely ≥5 finer pivots (~24%). Evidence: ARCHITECTURE §5.6. **Configuration**, tunable per request via API-1.4. |
| FR-1e.4 | **EN** | Whatever values D-13 selects SHALL become the documented defaults of both the analysis function and the API endpoint, and a parity test SHALL assert the two cannot drift apart — the same class of check that already guards the `zz_deviation` defaults. |

#### FR-1f — Determinism and independence

| ID | Tier | Requirement |
|---|---|---|
| FR-1f.1 | **EN** | Detection SHALL be a single deterministic pass per scale — no randomness, no wall-clock, no I/O. Identical input SHALL produce byte-identical pivots. |
| FR-1f.2 | **EN** | The Elliott package SHALL NOT import `src.analysis.swing_identification`, `src.analysis.zigzag`, or any other existing pivot/swing detection module, and SHALL NOT consume their return values. Enforced by TR-7. |
| FR-1f.3 | **EN** | `src/analysis/indicators.py::calc_rsi` remains the **one** permitted read-only dependency on shared analysis code (FR-1.7). It is an indicator, not a pivot/swing detector, so it does not conflict with FR-1f.2. |

---

### 5. Functional requirements — Candidate enumeration

#### FR-2 Enumeration

| ID | Tier | Requirement |
|---|---|---|
| FR-2.1 | **EI** | The engine SHALL evaluate contiguous pivot windows. **Inference:** each structure has a stated leg count (IMP-01: 5; ZZ-01: 3; TRI-01: 5; DT-01: 3; TT-01: 5), and a structure occupies consecutive legs. A window of *n* legs requires *n+1* pivots. |
| FR-2.2 | **SD** | Window sizes, per the reference's stated leg counts: Impulse 5 legs (IMP-01) · Leading/Ending Diagonal 5 legs (LD-03/ED-03) · Zigzag 3 legs (ZZ-01) · Flat 3 legs (FL-01) · Triangle 5 legs (TRI-01) · Double Three 3 legs (DT-01) · Triple Three 5 legs (TT-01). |
| FR-2.3 | **EN — OQ-18 RESOLVED** | Recursion depth is capped at `max_combination_depth = 1` (FR-3.9a.1), derived from the ladder rather than chosen. The reference still states no limit; the cap is a project decision. |
| FR-2.4 | **UD** | Whether overlapping candidates are ranked, pruned, or all retained is **UNDEFINED**. The reference states no selection procedure between competing readings. (Related: ZZ-F03/OQ-19, where the reference acknowledges an ambiguity and offers a tiebreak that is itself undefined.) |
| FR-2.5 | **NI** | No search-order, completeness, or termination criterion can be derived. The reference describes patterns, never a procedure for finding them. |
| FR-2.6 | **EN** | Enumeration SHALL be bounded so that analysis of a bounded bar count terminates in bounded time. Concrete bounds: Phase 4 (§12, D-03). |

---

### 6. Functional requirements — Structure classification

Each subsection lists the reference's gates for that structure and their status. **A structure
whose gate set contains any BLOCKED gate cannot be classified.**

#### FR-3.1 Impulse (§3.1)

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

#### 6.1b IMP-04 and IMP-05 — resolved definitions (project decision, not source-defined)

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

#### 6.1a IMP-06 — resolved definition (project decision, not source-defined)

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

#### FR-3.2 Impulse with Extension (§3.2)

| Gate | Rule | Tier | Status |
|---|---|---|---|
| Exactly one of waves 1/3/5 is "extended" | EXT-01 | **UD — OQ-24** | **CLASSIFICATION BLOCKED; QUANTITY MEASURED.** "Extended" has no numeric definition, and none could be derived from data (FR-3.2.2). |
| "Elongated impulses with exaggerated subdivisions" | EXT-02 | **UD — OQ-24** | **CLASSIFICATION BLOCKED; QUANTITY MEASURED.** Conjunctive, and the subdivision half is unmeasurable on 98.8% of the population. |
| Market-class priors (equities/FX → wave 3; commodities → wave 5) | EXT-03, EXT-04 | **NI** | Not a detector rule. The platform has no instrument-class taxonomy, and the reference gives no probability values. |

**FR-3.2.1 [UD]** — Extension **classification** is BLOCKED in its entirety. No structure SHALL be
typed as an extension, and `StructureType` SHALL NOT contain `IMPULSE_WITH_EXTENSION`; GEN-03's
three-way motive classification therefore remains unavailable. This transitively affects
ZZ-F03/OQ-19, whose tiebreak depends on "whether the third swing has extension or not".

**FR-3.2.2 [EN] — OQ-24 investigated 2026-08-10, deliberately left open.** Data derivation was
attempted, using the method that resolved D-13 and the OQ-18 depth cap, and it **failed to produce
a defensible threshold**:

  * Five formulations over 1,142 impulses (longest / second-longest, w3/w1, longest / mean of the
    other two, longest / total, longest / shortest) are all smooth monotone decays. No cliff, no
    second mode. p25 = 1.22, p50 = 1.55, p75 = 2.13, p90 = 2.80, p95 = 3.51.
  * Candidate cutoffs differ only in what share they flag (1.618 → 46%, 2.0 → 29%), so choosing
    one means choosing a hit rate and back-solving — the opposite of calibration.
  * EXT-02's subdivision criterion is unmeasurable on 1,198 of 1,212 motive structures (98.8%,
    scale 1 has no finer scale — D-14) and names a different wave than length does on 36% of the
    remaining 14.

**FR-3.2.3 [SD] — OQ-24 is independent of OQ-05.** OQ-05 concerns tolerance for matching discrete
stated ratios. DT-05 escaped it because the reference states an explicit inequality; §3.2 states
**no extension ratio at all**, so there is nothing to lift. Resolving OQ-05 first would not
unblock EXT-01/EXT-02. Adopting 161.8% anyway would make OQ-19 circular and collide with IMP-F02,
which lists 161.8% as the first, typical value for an *ordinary* wave 3.

**FR-3.2.4 [EN] — what SHALL be recorded** on every 5-leg motive structure, never gating, every
one tagged `blocked_by: ["OQ-24"]`:

| Measurement | Notes |
|---|---|
| `EXT-01_motive_wave_lengths` | waves 1, 3, 5 only — EXT-01 names no corrective |
| `EXT-01_longest_motive_wave` | `None` on a tie (reject-on-tie, D-02c) |
| `EXT-01_longest_over_second` | the ratio; never compared against anything |
| `EXT-02_subdivision_counts` | `None` where no finer scale exists — **not 0**, which would read as "measured, and it has none" |
| `EXT-02_most_subdivided_wave` | `None` on a tie |
| `EXT-02_criteria_agree` | whether EXT-02's two halves name the same wave; `None` when unmeasurable |

#### FR-3.3 Leading Diagonal (§3.3) / FR-3.4 Ending Diagonal (§3.4)

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

#### FR-3.5 Motive Sequence (§3.5)

| Gate | Rule | Tier | Status |
|---|---|---|---|
| Swing count ∈ "the motive sequence" | MS-01, MS-02, MS-03 | **NI** | **NOT IMPLEMENTABLE.** The rule is defined entirely by reference to "the numbers in the motive sequence" — **and the reference never states those numbers.** |

**FR-3.5.1 [NI]** — Motive Sequence SHALL NOT be implemented in v1. No amount of care can extract
a number set that is absent from the source. Supplying one would be invention (OQ-14).

**FR-3.5.2 [NI] — OQ-14 investigated 2026-08-10, confirmed not implementable, closed.**
Re-verified against the live reference rather than the Phase-2 extraction. Confirmed absent: any
numeric sequence, any worked counting example, any labelling scheme distinct from 1-2-3-4-5, and
any complete-vs-incomplete criterion.

The definition is circular with nothing inside the loop: MS-01 defines a motive sequence as an
*incomplete* sequence; MS-03 defines completeness by *"the numbers in the motive sequence"*; those
numbers are never stated. **This is NI rather than UD** because there is no parameter to choose —
unlike OQ-05, where a tolerance could be picked, here the absent content *is* the rule, and
supplying it would author a different rule rather than resolve a question.

MS-03's *"much **like** the Fibonacci number sequence"* is a **simile, not an identity**.
Substituting 3, 5, 8, 13, 21 would invent the rule's operative content while citing the source as
authority for it. The sentence draws an analogy for how the sequence behaves, not a definition of
its membership.

**Disposition: closed.** No code, now or later, from this reference. OQ-14 is excluded from the
*unresolved* tally and counted separately as not-implementable — the other 21 await a decision or
better wording; this one awaits content the source does not contain.

#### FR-3.6 Zigzag (§5.1)

| Gate | Rule | Tier | Status |
|---|---|---|---|
| Exactly 3 legs, labelled A-B-C | ZZ-01 | SD | Implementable |
| Waves A and C each subdivide into 5 waves (impulse or diagonal) | ZZ-02 | SD | Implementable — **depends on impulse/diagonal classification** (§8) |
| Wave B is any corrective structure | ZZ-03 | SD | Implementable (permissive) |
| Overall 5-3-5 | ZZ-04 | SD | Implementable |
| Wave B / wave A ratio | ZZ-F01 | **UD — OQ-05** | Record, never gate |
| Wave C / wave A ratio | ZZ-F02 | **UD — OQ-05** | Record, never gate |
| Impulse-vs-zigzag disambiguation at C = 161.8% | ZZ-F03 | **UD — OQ-19** | **BLOCKED.** The reference's own tiebreak ("whether the third swing has extension") depends on OQ-24, which is also unresolved. Circular. |

#### FR-3.7 Flat and subtypes (§5.2)

| Gate | Rule | Tier | Status |
|---|---|---|---|
| 3 legs, 3-3-5 subdivision | FL-01 | SD | Implementable |
| Wave A subdivides into 3 (this is what separates Flat from Zigzag) | FL-02 | SD | Implementable |
| **Regular:** wave B terminates *near* the start of wave A | FLR-01 | **UD — OQ-09** | **BLOCKED; QUANTITY MEASURED.** "Near" unquantified and no cliff in the data (FR-3.7.1a). |
| **Regular:** wave C terminates *slightly beyond* the end of wave A | FLR-02 | **UD — OQ-10** | **BLOCKED; QUANTITY MEASURED.** "Slightly" unquantified, no cliff. |
| **Expanded:** wave B terminates beyond the start of wave A | FLE-01 | SD | **Implementable and unactioned** — exact, needs no threshold. Measured; does not gate, pending **OQ-27** (FR-3.7.1c). 33.5% of real flats satisfy it. |
| **Expanded:** wave C ends *substantially beyond* the end of wave A | FLE-02 | **UD — OQ-10** | **BLOCKED; QUANTITY MEASURED.** "Substantially" unquantified, no cliff. |
| **Running:** wave C falls short of where wave A ended | FLU-01 | SD | Implementable — a clean directional price comparison |
| All flat Fibonacci ratios | FLR-F01/F02, FLE-F01/F02, FLU-F01/F02 | **UD — OQ-05, OQ-11** | Record, never gate. Additionally **OQ-11**: the base "wave AB" is undefined. |

**FR-3.7.1 [UD - OQ-09/OQ-10] - CORRECTED 2026-08-10.** This clause previously read *"Regular and
Expanded Flat are separated **only** by 'slightly beyond' vs 'substantially beyond'."* **That is
wrong**, and the table above already contradicted it: the wave-B test is a second, independent
discriminator, and **FLE-01's half of it is exact** (SD, "Implementable - a clean directional price
comparison"). The accurate statement is:

  * **FLE-01 separates Expanded from NOT-Expanded**, exactly, with no threshold.
  * **Regular Flat cannot be gated at all** - *both* of its statements are vague (FLR-01 "near",
    FLR-02 "slightly beyond"), so it has no exact criterion of its own. Resolving OQ-10 alone
    would not produce Regular Flat.

**FR-3.7.1a [EN] - OQ-09/OQ-10 investigated 2026-08-10, deliberately left open.** Data derivation
over 356 real flats found **no cliff in either dimension**:

  * OQ-10 - where wave C lands relative to wave A's end is a broad continuum, p5 = 0.17 to
    p95 = 5.98 x |A|, every large gap at p97+. No trough between "slightly" and "substantially".
  * OQ-09 - wave B's retracement of wave A runs continuously *through* 1.00 with no trough
    (p25 = 0.37, p50 = 0.65, p75 = 1.21); only 9% of flats land within +/-10% of 1.00.

**FR-3.7.1b [EN] - what SHALL be recorded** on every flat and running flat, never gating, each
tagged `blocked_by: ["OQ-09", "OQ-10"]`. `StructureType` SHALL NOT gain `FLAT_REGULAR` or
`FLAT_EXPANDED`:

| Measurement | Notes |
|---|---|
| `FLR-01_waveB_retracement_of_waveA` | 1.0 means wave B ended exactly at wave A's start |
| `FLE-01_waveB_beyond_waveA_start` | boolean; exact, needs no threshold |
| `FLR-02_FLE-02_waveC_beyond_waveA_end` | signed, in units of wave A's length; below 0 is FLU-01's case |
| `waveC_over_waveA` | relative to wave A only - the "wave AB" base is OQ-11, undefined |

**FR-3.7.1c [UD - OQ-27]** - FLE-01 is **measured but SHALL NOT gate**, pending a project
decision. Promoting it would collide with Running Flat: **29 of 34** real structures satisfy both
FLE-01 and FLU-01, and the reference states no precedence between Expanded and Running. See
OQ-27.

**FR-3.7.2 [UD — OQ-23]** — Expanded and Running Flat state the **same** wave-B ratio (123.6%).
Wave B cannot discriminate between them; only wave C can (FLE-02 vs FLU-01).

**FR-3.7.3 [EI]** — Of the three subtypes, only **Running Flat** has a fully-specified,
non-Fibonacci mandatory gate (FLU-01). **Inference:** FLE-01 is also clean, but Expanded's second
gate FLE-02 is blocked, whereas Running's single stated gate is complete. This makes Running Flat
the only flat subtype whose structural test is fully derivable today.

#### FR-3.8 Triangle (§5.3)

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

#### FR-3.9 Double Three (§5.4) / FR-3.10 Triple Three (§5.5)

| Gate | Rule | Tier | Status |
|---|---|---|---|
| DT: 3 legs W-X-Y; TT: 5 legs W-X-Y-X-Z | DT-01, TT-01 | SD | Implementable |
| DT: 7 sub-swings; TT: 11 sub-swings | DT-02, TT-02 | SD | Implementable |
| W/Y (DT) and W/Y/Z (TT) in {zigzag, flat, DT of smaller degree, TT of smaller degree} | DT-03, TT-03 | **EN — OQ-18 RESOLVED** | **Implementable.** Recursion capped at depth 1 (FR-3.9a). Uses the pivot ladder's `scale`, not a named degree, so OQ-17 is not involved. |
| X ∈ any corrective structure | DT-04, TT-04 | SD | Implementable (permissive) |
| DT: X/W and Y/W ratios; TT: X/W and Z/W ratios | DT-F01/F02, TT-F01/F02 | **UD — OQ-05** | Record, never gate |

**FR-3.9.1 [SD]** — The reference states **no** ratio for wave Y in a Triple Three, and none for
the second X. The engine SHALL NOT fabricate one. This asymmetry is in the source.

#### FR-3.9a Double Three / Triple Three (§5.4, §5.5) — OQ-18 RESOLVED

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

#### FR-3.11 Degree assignment (§1.4)

| ID | Tier | Requirement |
|---|---|---|
| FR-3.11.1 | **SD** | Nine degrees exist, named largest→smallest: Grand Super Cycle, Super Cycle, Cycle, Primary, Intermediate, Minor, Minute, Minuette, Subminuette (DEG-01, DEG-02). |
| FR-3.11.2 | **UD — OQ-17** | **How a degree is assigned to a structure is UNDEFINED.** The reference maps only 2 of 9 degrees to timeframes (GSC → weekly/monthly, Subminuette → hourly) and gives no rule for assigning degree from price data. |
| FR-3.11.3 | **EI** | Degree labelling, if implemented, SHALL be presentation-only and SHALL NOT affect classification. **Inference:** no rule in the inventory takes degree as an input to a gate, except DT-03/TT-03's "of smaller degree", which is resolved by the depth cap and keyed on the ladder's integer `scale`, never a named degree. |

---

### 7. Functional requirements — Measurement, evidence, and output

#### FR-4 Measurement recording

| ID | Tier | Requirement |
|---|---|---|
| FR-4.1 | **SD** | Guideline measurements SHALL be recorded and SHALL NEVER gate. Every Fibonacci relationship in the inventory (16 rules) sits under the reference's "Fibonacci Ratio Relationship" heading, separate from its "Guidelines" list. |
| FR-4.2 | **UD — OQ-05** | **Whether a recorded ratio "matches" its stated Fibonacci value is UNDEFINED.** All 16 ratios are discrete exact values with no tolerance. Raw ratios MAY be computed; match/no-match MUST NOT be asserted. |
| FR-4.3 | **UD — OQ-22** | All volume-based observations (WP-02, WP-04, WP-08, WP-11, WP-12, WP-13, TRI-05) are **UNDEFINED**: qualitative wording, no thresholds, no measurement window — and volume is synthetic on the default data source, so any such rule would be meaningless in the common case. |
| FR-4.4 | **SD** | Wave-personality narrative statements (WP-01, WP-09) SHALL NOT be implemented as detectors. They are prose. |
| FR-4.5 | **EI** | WP-03 duplicates IMP-03. The engine SHALL implement it once. **Inference:** §4.1's "can never extend beyond the starting point of wave one" and §3.1's "can't retrace more than the beginning of wave 1" are the same constraint stated twice. |
| FR-4.6 | **SD** | WP-05 (wave 3 usually largest) and WP-06 (gaps indicate wave 3) are implementable as recorded observations, never as gates. |

**FR-4.2a [EN] — OQ-05 investigated 2026-08-10, deliberately left open.** Three independent lines
of evidence, all negative. Recorded so the question is not re-opened without new grounds.

  1. **The reference states no tolerance — and writes ranges where it means them.** Re-verified
     against the source: no "approximately"/"about"/"near" applied to any ratio, no statement on
     required precision, no band/zone/margin language anywhere. But **three** relationships ARE
     stated as explicit ranges (IMP-F04 "inverse 123.6 – 161.8%", FLE-F02 "123.6% – 161.8%",
     FLU-F02 "61.8% – 100%"). The author knows how to express a band, so the discrete lists are
     discrete **by intent**, not band-centres with an unstated width. Same principle that admitted
     the DT-05 inequality.
  2. **No empirical clustering.** A naive null suggested IMP-F03 at p = 0.018; that was an
     artifact of wave 4's targets sitting in the naturally dense low end of its range (IMP-05's
     territory gate and the "no more than 50%" cap force wave 4 small). Under a **shift** null
     (slide the target set, preserving spacing and region) and an **empirical** null (draw targets
     from the data itself), **0 of 5 families are significant** at α = 0.01 — IMP-F01 0.134/0.753,
     IMP-F03 0.051/0.093, IMP-F04 0.143/0.277, ZZ-F01 0.377/0.994, ZZ-F02 0.066/0.486.
  3. **No single global tolerance is viable.** The width needed to match 50% of observations spans
     11× — IMP-F03 ±0.035, IMP-F01 ±0.065, ZZ-F02 ±0.157, ZZ-F01 ±0.196, IMP-F04 ±0.397. This
     eliminates the "single global ±%" option in FR-4.2 on evidence rather than on preference.

**FR-4.2b [SD] — corrected scope.** OQ-05 blocks **14** rules, not 16. FLE-F02 and FLU-F02 state
ranges, which are directly evaluable and need no tolerance; they remain blocked by **OQ-11**
(undefined "wave AB" base). IMP-F04 carries **both OQ-05 and OQ-07** — one of its three bases is
undefined ("inverse retracement"), the other two are discrete values.

**FR-3.8.1 [EN] — OQ-12/OQ-13 investigated 2026-08-10, deliberately left open.** An exact rule was
found and still does not gate.

  * **TRI-01 and TRI-03 are exact, mandatory-tier and selective** — 328 of 3,912 five-leg windows
    pass (8.4%), comparable to the flat and zigzag confirm rates. The prior record calling this "a
    near-vacuous subdivision gate" was measured and is **wrong**; corrected.
  * They stay ungated on three grounds: the strict reading of "subdivided into three" finds **1**
    candidate in 3,912, so the loose `diagonal.py` predicate is used and **OQ-25 is inherited**;
    TRI-02's host rule is guideline-tier ("usually") and matches only **6 of 328** regardless; and
    **21%** of candidates are plainly trending, contradicting the reference's own opening
    definition, *"a triangle is a sideways movement"*.
  * **No threshold for "sideways" is derivable.** net/path is a plateau (p25 0.160, p50 0.312,
    p75 0.479). An apparent three-mode structure was rejected by a 1,000-sample bootstrap — **0 of
    3 modes stable above 90%**, mode count varying 1–5 across resamples.
  * **The expected Diagonal collision does not occur.** `3-3-3-3-3` is a permitted diagonal shape,
    but measured overlap is **zero**: diagonals are enumerated only inside impulse wave-1/wave-5
    hosts. The principle still bites — with no gateable host rule a triangle would be "a
    3-3-3-3-3 not inside an impulse host", a definition by exclusion the reference never gives.
  * **OQ-13 is measurable, not decidable.** RSI reads at all six pivots for 326 of 328 candidates.
    "Supports" states no direction, threshold or comparison, and "in every time frame" is
    meaningless in a single-timeframe engine.

**FR-3.8.2 [EN] — what SHALL be recorded.** Each candidate window is emitted to
`AnalysisResult.triangle_candidates` as a plain record, **never** to `waves`, and `StructureType`
SHALL NOT gain `TRIANGLE`. Fields: `TRI-03_subdivision_counts`, `TRI-05_net_over_path`,
`TRI-07_slope_A_C_E`, `TRI-07_slope_B_D`, `TRI-06_rsi_at_pivots`, `confirm_index`, and
`blocked_by: ["OQ-12", "OQ-13"]`. Candidates are records rather than waves precisely because they
are not structures: promoting them would put an unnameable shape into the list the chart renders
as confirmed analysis.

#### FR-5 Candidate lifecycle

| ID | Tier | Requirement |
|---|---|---|
| FR-5.1 | **EN** | Each candidate SHALL carry an explicit lifecycle state. |
| FR-5.2 | **EN** | States: **ENUMERATED** (window formed) → **GATED** (passed every *implementable* mandatory gate) → **MEASURED** (guideline measurements recorded). |
| FR-5.3 | **EN** | A fourth state **UNDECIDABLE** SHALL exist for candidates that pass every implementable gate but whose acceptance depends on a blocked gate. This is required by this project's actual situation: e.g. an Impulse whose IMP-06 comparison bars have `NaN` RSI(13) (FR-3.1a.6) is genuinely neither valid nor invalid, and collapsing that into either would misreport. |
| FR-5.4 | **EN** | There SHALL be **no INVALID/REJECTED state.** A candidate failing an implementable gate is simply never created. Rationale: the reference describes only what patterns *are*; it never describes a rejected pattern as an object. |
| FR-5.5 | **EN** | Later processing SHALL NOT mutate or delete a wave created by earlier processing. |

#### FR-6 Determinism and purity

| ID | Tier | Requirement |
|---|---|---|
| FR-6.1 | **EN** | Identical input SHALL produce byte-identical serialized output across repeated runs. |
| FR-6.2 | **EN** | The engine SHALL be free of wall-clock time, randomness, and I/O. |
| FR-6.3 | **EN** | The engine SHALL NOT mutate its input DataFrame or pivot sequence. |

#### FR-7 Serialization

| ID | Tier | Requirement |
|---|---|---|
| FR-7.1 | **EN** | Output SHALL be JSON-serializable with NaN/Inf normalized to null. |
| FR-7.2 | **EN** | Every emitted record SHALL carry its lifecycle state, so a consumer can distinguish GATED from UNDECIDABLE. |
| FR-7.3 | **EN** | Output SHALL carry an engine version string and the configuration used. |
| FR-7.4 | **SD** | Output SHALL NOT contain a confidence, probability, or score field. The reference states no weighting function anywhere — every ratio is given standalone, with no rule for combining ratios into a single number. Emitting one would be invention. |

---

### 8. Dependency chain — ✅ **BROKEN** *(revised 2026-08-09 after OQ-02 / OQ-03)*

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
                  ├── ❌ Regular Flat   — OQ-09, OQ-10 (no exact criterion at all)
                  └── ❌ Expanded Flat  — FLE-01 exact but not gating (OQ-27)
                        │
                        ▼
              DOUBLE / TRIPLE THREE — DT-03/TT-03 partially satisfied:
              the {zigzag, flat} branch is ✅ available; the
              "of smaller degree" nesting branch is ✅ OQ-18 RESOLVED (depth cap)

  TRIANGLE — never depended on Impulse; still ❌ OQ-12, OQ-13
  EXTENSION — classification still ❌ OQ-24 (keeps OQ-19 circular); quantities measured
```

#### 8.1 What is now unblocked

| Structure | Status | Caveat |
|---|---|---|
| **Impulse** | ✅ **Fully specified** — all 6 gates | — |
| **Leading / Ending Diagonal** | ✅ **All gates specified** (position + subdivision) | **OQ-15** open as a *permissiveness* concern, not a gate: with overlap explicitly non-gating and "wedge" unquantified, the detector may be very permissive. Quality question, your call. |
| **Zigzag** | ✅ **All gates specified** | **OQ-19** open: the reference's own impulse-vs-zigzag tiebreak at C = 161.8% depends on "extension" (OQ-24). Affects labelling preference, not gating. |
| **Flat (generic)** | ✅ **Gates specified** | — |
| **Running Flat** | ✅ **Fully specified** (FLU-01) | The only fully-specified flat subtype (FR-3.7.3) |
| **Regular Flat** | ❌ Blocked | **OQ-09** ("near"), **OQ-10** ("slightly beyond") — investigated 2026-08-10, no cliff. Has **no exact criterion of its own**, so unreachable under any resolution of OQ-10 alone. Quantities measured. |
| **Expanded Flat** | ⚠ Gateable but not gating | **FLE-01 is exact** and unactioned; FLE-02 stays blocked by **OQ-10**. Not promoted because **OQ-27** (Running/Expanded precedence, 29 of 34 overlap) is unresolved. Quantities measured. |
| **Double / Triple Three** | ✅ **Implemented 2026-08-10** | OQ-18 resolved by a depth-1 cap (FR-3.9a). DT-02/TT-02's swing counts remain **OQ-26** — recorded, never gated. OQ-17 is not involved: the gate keys on the ladder's integer `scale`, not a named degree. |
| **Triangle** | ⚠ Measured, never classified | **OQ-12**, **OQ-13** — investigated 2026-08-10 (FR-3.8.1). TRI-01/TRI-03 are exact and selective (8.4%) but ungated: OQ-25 inherited, TRI-02 guideline-tier, and no derivable "sideways" threshold. No `TRIANGLE` type. |
| **Impulse with Extension** | ❌ Classification blocked | **OQ-24** — investigated on real data 2026-08-10 and left open: no cliff in five formulations, EXT-02 unmeasurable on 98.8%. Quantities recorded (FR-3.2.4); no `IMPULSE_WITH_EXTENSION` type emitted. Independent of OQ-05. |
| **Motive Sequence** | ❌ Not implementable | **OQ-14** — excluded from v1 |

#### 8.2 The input is now defined too — the core path is complete

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

#### 8.3 OQ-01 — RESOLVED 2026-08-10 as documentation, with no behaviour change

OQ-01 (is the Mandatory/Guideline split in the inventory the classification the project adopts?)
is **closed**. The answer is yes, with the description corrected: **the tiers are project
judgement calls informed by the reference's grammar, not mechanically derived from it.** The
inventory previously claimed they were "derived purely from the grammar of each statement", which
claimed more rigour than was applied. **No gate was reclassified and no engine behaviour changed.**

**FR-8.3.1 [EN] — the grammar is evidence, not an algorithm.** All eight structure blocks in the
reference are headed "Guidelines"; *rule*, *must*, *mandatory* and *required* never appear as a
classification. Applying grammar mechanically would give a wrong answer: the reference states the
*same* diagonal subdivision constraint as *"can be"* (LD-03) and *"is either"* (ED-03), which
would split an identical rule across two tiers. Both are M, correctly.

**FR-8.3.2 [EN] — the IMP-06 / TRI-06 asymmetry is deliberate.** Both use the modal *"needs to"*
and are tiered oppositely:

  * **IMP-06 is Mandatory by the OQ-04 project decision** (RSI(13), 55/45), taken independently of
    grammar. Its tier does not rest on the wording.
  * **TRI-06 remains Guideline**, measurement-only: *"supports"* states no direction, threshold or
    comparison, and *"in every time frame"* is meaningless in a single-timeframe engine (OQ-13).

They differ on the **evaluability of their content**, not their grammar. This is recorded so a
future reader does not "correct" the asymmetry into a behaviour change without repeating the
review in FR-8.3.3.

**FR-8.3.3 [EN] — measured blast radius, and why nothing moved.** Each gating mandatory rule was
made non-gating on real data (CL 5m, NQ 5m, CL 15m, ES 15m). Baseline **1,891 structures — 765
gated, 1,126 undecidable, 1,140 impulses**:

| Rule relaxed | structures | gated | undecidable | impulses |
|---|---|---|---|---|
| IMP-06 | **+2,560 (+135%)** | +768 | +1,792 | +1,876 |
| IMP-02 | +1,605 (+85%) | +2,731 | −1,126 | +292 |
| IMP-05 | +692 (+37%) | +258 | +434 | +450 |
| IMP-03 | +581 (+31%) | +184 | +397 | +407 |
| IMP-04 | +125 (+7%) | +74 | +51 | +58 |
| DT-05 / TT-05 | +51 (+3%) | +51 | 0 | 0 |
| FLU-01 | 0 | 0 | 0 | 0 |

FLU-01's zero is a **relabel, not a no-op** — relaxed, every flat becomes a running flat
(188 → 0, 23 → 211). IMP-02 is the **sole source of UNDECIDABLE**. Impulse gates cascade into
corrections and diagonals: relaxing IMP-02 takes diagonals from 72 to 1,236. IMP-01, ZZ-01, FL-01,
DT-01 and TT-01 cannot be relaxed this way at all — they define which windows are enumerated.

**FR-8.3.4 [SD] — a third divergence, already tracked.** IMP-F03's *"but no more than 50%"* is an
absolute cap inside a G-classified rule, needing no tolerance (the DT-05 shape). It remains under
**OQ-08**.

### 9. Data model requirements

Specified as field contracts. **This is a specification, not code** — no types, classes, or
interfaces are being declared here for implementation.

#### DM-1 Pivot

| Field | Type | Tier | Notes |
|---|---|---|---|
| `index` | int | EI | Bar position of the extreme in the source OHLCV frame |
| `confirm_index` | int | **EN** | Bar at which the reversal confirmed the pivot. **Always > `index`.** Consumers at bar *t* may use only pivots with `confirm_index <= t` (FR-1b.2). |
| `timestamp` | datetime | EI | For rendering and cross-referencing |
| `price` | float | EI | The bar's own extreme — `high` for a HIGH pivot, `low` for a LOW pivot (FR-1c.1) |
| `kind` | enum {high, low} | EI | Required for direction-aware rules |
| `scale` | int | **EN** | Which threshold in the ladder produced this pivot (FR-1c.3). **Not an Elliott degree** — see FR-1d.3 / OQ-17. |

**DM-1.1 [EN — OQ-21 RESOLVED]** — Pivots come from the engine's own detector, specified in §4a. No existing pivot/swing module is imported or consumed (FR-1f.2).

#### DM-2 Wave

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

#### DM-3 Analysis result (top level)

| Field | Type | Tier | Notes |
|---|---|---|---|
| `engine_version` | string | EN | |
| `config` | map | UD | Contents depend on unresolved parameters (§12, D-03) |
| `waves` | list[Wave] | EI | |
| `blocked_rules` | list[rule id] | EN | Which inventory rules were **not** evaluated on this run, and why. Makes the gap machine-readable instead of silent. |

#### DM-4 Permitted structure_type values

**SD.** Exactly the reference's named structures, and nothing else:
`impulse` · `impulse_with_extension` · `leading_diagonal` · `ending_diagonal` · `zigzag` ·
`flat_regular` · `flat_expanded` · `flat_running` · `triangle` · `double_three` · `triple_three`.

**DM-4.1 [NI]** — `motive_sequence` is **excluded**: FR-3.5.1 (OQ-14).
**DM-4.2 [UD — OQ-12]** — `triangle` is listed but its inclusion in v1 is an open decision.

---

### 10. API requirements

#### API-1 Endpoint

| ID | Tier | Requirement |
|---|---|---|
| API-1.1 | **EN** | One new read-only sub-resource: `GET /api/backtests/{backtest_id}/elliott-wave`. Follows the existing sub-resource convention (`/zigzag`, `/chart-patterns`, `/candlestick-patterns`). |
| API-1.2 | **EN** | It SHALL read `price_data` from the existing result store and SHALL NOT re-run the backtest or re-fetch data. |
| API-1.3 | **EN** | 404 for an unknown/expired `backtest_id`, matching sibling endpoints. |
| API-1.4 | **EN — D-13 CLOSED** | The endpoint SHALL expose the pivot detector's `theta_base`, `ratio` and `scales` as optional query parameters, defaulting to the FR-1e.3 values. FR-1e.4's parity test applies. Any further parameters depend on OQ-05 and are out of v1. `max_combination_depth` is deliberately **not** exposed — it is capped at 1 by the ladder's expressive limit (FR-3.9a.1), so a caller-supplied value could only be wrong. |
| API-1.5 | **EN** | The response SHALL include `blocked_rules` (DM-3) so the client can honestly display what was not evaluated. |
| API-1.6 | **EN** | No existing endpoint's path, parameters, or response shape SHALL change. |
| API-1.7 | **EN** | `GET /api/backtests/{id}/report` SHALL NOT gain Elliott Wave parameters in v1 (§1.3). |

#### API-2 Layering

| ID | Tier | Requirement |
|---|---|---|
| API-2.1 | **EN** | Existing three-layer separation SHALL be preserved: router (HTTP/params) → serializer (domain → JSON) → `src/` (domain math). No Elliott logic in the router; no FastAPI imports in `src/`. |
| API-2.2 | **EN** | The Elliott analysis module SHALL live under `src/analysis/` as a new, self-contained unit and SHALL NOT modify any existing analysis module. |

---

### 11. Frontend requirements

#### FE-1 Dedicated tab

| ID | Tier | Requirement |
|---|---|---|
| FE-1.1 | **EN** | Elliott Wave SHALL be a **dedicated top-level tab** in `ResultsPage.tsx`, added after `✨ Strategy Optimizer` as the 9th tab. |
| FE-1.2 | **EN** | The only permitted edits to `ResultsPage.tsx` are: one import, one data query, one `<TabsTrigger>`, one `<TabsContent>`. |
| FE-1.3 | **EN** | Elliott Wave SHALL NOT be a checkbox, toggle, or overlay on any existing tab. |

#### FE-2 Dedicated chart

| ID | Tier | Requirement |
|---|---|---|
| FE-2.1 | **EN** | A **new, standalone chart component** SHALL be created for the Elliott Wave tab. |
| FE-2.2 | **EN** | **`CandlestickChart.tsx` SHALL NOT be modified, extended, parameterized, or imported by the Elliott Wave chart.** The Price & Trades chart remains a plain Price & Trades chart. This is a hard boundary (§12). |
| FE-2.3 | **EN** | The Elliott chart SHALL be single-panel: candlesticks + Elliott structures only. No RSI, Stochastic, trade markers, or Swing/ZigZag overlay — those belong to Price & Trades. |
| FE-2.4 | **EN** | Rendering SHALL use the existing Plotly stack (`react-plotly.js`); no new charting dependency. |
| FE-2.5 | **EI** | Each structure SHALL render as a connected path through its own labelled legs in order, with each wave's label displayed at its terminal pivot. **Inference:** the reference's structures are defined as ordered sequences (1→2→3→4→5, A→B→C, W→X→Y); scattered independent markers would not convey the ordering that *is* the structure. |
| FE-2.6 | **EN** | Elliott structures SHALL use a colour identity distinct from the Swing/3-Leg palette used elsewhere, so the two systems are never visually confused. |

#### FE-3 Honest display of blocked state

| ID | Tier | Requirement |
|---|---|---|
| FE-3.1 | **EN** | Candidates in **UNDECIDABLE** state SHALL be visually distinguishable from **GATED** ones, or excluded — but MUST NOT be presented as confirmed. |
| FE-3.2 | **EN** | The UI SHALL surface `blocked_rules`, so a user is never shown a partial analysis that looks complete. |
| FE-3.3 | **EN** | The UI SHALL NOT display a confidence value (FR-7.4) — there is nothing truthful to put in it. |

#### FE-4 Types and client

| ID | Tier | Requirement |
|---|---|---|
| FE-4.1 | **EN** | New TypeScript interfaces SHALL be **added** to `lib/types.ts`; no existing interface modified. |
| FE-4.2 | **EN** | One new method SHALL be **added** to `lib/api.ts`; no existing method modified. |
| FE-4.3 | **EN** | `tsc --noEmit` SHALL pass with zero errors. |

---

### 12. Implementation boundaries

#### 12.1 MUST NOT be modified

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

#### 12.2 MAY be created or additively changed

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

### 13. Testing requirements

| ID | Tier | Requirement |
|---|---|---|
| TR-1 | **EN** | Every **implementable** mandatory gate SHALL have both a passing fixture and a fixture violating **only** that gate. Applies to: IMP-01, IMP-02, IMP-03, LD-01, LD-03, ED-01, ED-03, ZZ-01, ZZ-02, ZZ-03, ZZ-04, FL-01, FL-02, FLE-01, FLU-01, TRI-01, TRI-03, DT-01, DT-02, DT-04, TT-01, TT-02, TT-04. |
| TR-2 | **EN** | **Blocked-rule guard tests.** For every rule marked BLOCKED, a test SHALL assert it has **not** been silently implemented — e.g. no Fibonacci tolerance constant exists while OQ-05 is open; no "near"/"slightly"/"substantially" flat-subtype threshold exists while OQ-09/OQ-10 are open, and no flat ratio is compared against a constant; no Fibonacci constant outside the one scoped DT-05/TT-05 ceiling exception; no "extension" verdict, threshold constant or comparison of the extension ratio while OQ-24 is open. This is the primary defence against gaps being quietly filled with invented values. *(The OQ-02, OQ-03 and OQ-04 guards are retired — those rules are now specified and are covered by TR-2a/TR-2b.)* |
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

### 14. Open Questions — 6 resolved, 20 unresolved, 1 not implementable (of 27)

*OQ-01 was resolved 2026-08-10 as documentation only — the tiers are adopted, restated honestly, and no gate changed (§8.3). OQ-14 is counted separately: it is not a pending decision but a terminal
gap in the source (FR-3.5.2). The 21 unresolved await a decision or better wording; OQ-14
awaits content the reference does not contain.*

**Revised 2026-08-09.** **OQ-02, OQ-03, OQ-04 and OQ-21 are RESOLVED by project decision**
(§6.1b, §6.1a, §4a). **The other 20 remain unresolved and none has been silently narrowed.**
OQ-01 is *partially constrained* by those decisions but is **not** resolved (§8.3). For each: the rules it affects, why the reference is
insufficient, and what it blocks.

| OQ | Affected rules | Why the reference is insufficient | What it blocks |
|---|---|---|---|
| ~~**OQ-01**~~ | All 94 | **RESOLVED 2026-08-10 — documentation only, no behaviour change (§8.3).** The split IS adopted, restated as project judgement *informed by* grammar rather than derived from it. Three divergences documented: IMP-06/TRI-06 (same modal, opposite tiers — deliberate, FR-8.3.2), LD-03/ED-03 (same constraint, different grammar), IMP-F03's embedded cap (OQ-08). Blast radius measured; no gate moved. Original wording: Every structure block is headed "Guidelines"; the words *rule*, *must*, *mandatory* never appear as a classification. The M/G split in the inventory is inferred from grammar, not stated. The 2026-08-09 decisions ruled out the blanket-non-gating answer, but did **not** confirm the grammar-based split. See §8.3. | The definition of "gate" itself. Determines whether *anything* can reject a candidate. |
| ~~**OQ-02**~~ | IMP-04 | **✅ RESOLVED 2026-08-09 by project decision** — wave length is **absolute price distance** from pivot prices; %, log and bar-count measures rejected. Full definition: §6.1b. **The reference still says nothing on this**; tier EN, not SD. | *(was: impulse gate 4 — now specified)* |
| ~~**OQ-03**~~ | IMP-05 | **✅ RESOLVED 2026-08-09 by project decision** — territory is the **pivot-price interval**; violated iff wave 4's interval intersects wave 1's. Full-intrabar-range reading rejected. Full definition: §6.1b. **The reference still says nothing on this**; tier EN, not SD. | *(was: impulse gate 5 — now specified)* |
| ~~**OQ-04**~~ | IMP-06, WP-10 | **✅ RESOLVED 2026-08-09 by project decision** — RSI(13) directional comparison, IMP-06 stays mandatory. Full definition: §6.1a. **The reference still says nothing on this**; the resolution is a decision (tier EN), not source-defined behavior. | *(was: the entire §8 chain — now unblocked at this node)* |
| **OQ-05** | 14 Fibonacci rules *(corrected from 16, 2026-08-10)* | **INVESTIGATED, STILL UNRESOLVED (FR-4.2a).** **PRESERVED UNRESOLVED per instruction.** Every ratio is a discrete exact value, never a band. No tolerance stated anywhere. Exact float equality never matches real data. **Investigated 2026-08-10 on three fronts, all negative** (FR-4.2a): the reference writes explicit ranges where it means them, real ratios show no clustering on the stated values once density is controlled for (0 of 5 families significant), and the width any tolerance would need varies 11× across families. | All ratio matching (FR-4.2). Ratios may be *computed*, never *matched*. |
| **OQ-06** | IMP-F02 | "of wave 1-2" — net displacement start-of-1→end-of-2, or wave 1's length projected from end of wave 2? | Wave 3 ratio base |
| **OQ-07** | IMP-F04, FIB-06 | "inverse retracement" is used but never defined on the page. | Wave 5 target, basis 1 of 3 |
| **OQ-08** | IMP-F03, WP-07 | §3.1 says "14.6%, 23.6%, or 38.2% … but no more than 50%"; §4.3 says "typically less than 38.2%". Two sections, different numbers. Cap vs guideline unstated. | Wave 4 ratio; its interaction with IMP-05 |
| **OQ-09** | FLR-01 | **INVESTIGATED 2026-08-10, STILL UNRESOLVED.** "near" unquantified; paired ratio is a single point (90%). Wave B's retracement runs continuously through 1.00 with no trough; only 9% within +/-10%. | Regular Flat wave-B gate. Quantity measured (FR-3.7.1b). |
| **OQ-10** | FLR-02, FLE-02 | **INVESTIGATED 2026-08-10, STILL UNRESOLVED.** Neither word is quantified and wave C's landing point is a broad continuum (p5 0.17 to p95 5.98). **Corrected:** this is *not* the only Regular/Expanded discriminator — the wave-B test is a second one, and FLE-01 is exact. | Regular Flat entirely; Expanded's wave-C half. Quantities measured (FR-3.7.1b). |
| **OQ-11** | FLR-F02, FLE-F02, FLU-F02 | "of wave AB" — net A→B displacement, len(A)+len(B), or len(A)? Undefined. | All three flat wave-C ratios |
| **OQ-12** | TRI-01…07 | No Fibonacci ratios, no rules for waves D/E, no variant discriminators; TRI-04 permits nearly any corrective. | Whether Triangle is in v1 at all (FR-3.8.1) |
| **OQ-13** | TRI-06 | "support" undefined; "every time frame" undefined in a single-timeframe backtest. Only place RSI is named as a requirement. | Triangle momentum gate |
| ~~**OQ-14**~~ | MS-01…03 | **INVESTIGATED 2026-08-10, CONFIRMED NI, CLOSED (FR-3.5.2).** The numbers are never stated; the definition is circular (MS-01 "incomplete" → MS-03 "the numbers" → absent). "Much *like* the Fibonacci sequence" is a simile, not an identity. | Motive Sequence entirely → **NI**, excluded from v1 (FR-3.5.1, DM-4.1). Counted separately from the unresolved questions. |
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
| **OQ-27** | FLE-01, FLU-01 | **NEW 2026-08-10, UNRESOLVED.** Expanded and Running Flat overlap on exact criteria — FLE-01 (wave B beyond wave A's start) and FLU-01 (wave C short of wave A's end) are both exact and mandatory-tier, and 29 of 34 real structures satisfy both. The reference states no precedence. | Whether FLE-01 may gate (FR-3.7.1c). Dormant while it does not. |
| **OQ-23** | FLE-F01, FLU-F01 | Expanded and Running Flat state the **same** wave-B ratio (123.6%). | Wave B cannot separate them (FR-3.7.2) |
| **OQ-24** | EXT-01, EXT-02, ZZ-F03 | **INVESTIGATED 2026-08-10, STILL UNRESOLVED.** No numeric definition anywhere, and none derivable: five formulations over 1,142 impulses show no cliff; EXT-02 unmeasurable on 98.8% and self-contradicting on 36% of the rest. **Independent of OQ-05** — no stated inequality to lift, unlike DT-05. | Extension *classification* (FR-3.2.1); feeds OQ-19. Quantities are measured (FR-3.2.4). |

---

### 14a. Residual sub-detail of the OQ-04 resolution

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

#### 14a.2 Exact-equality boundaries in IMP-04 and IMP-05 (D-02c)

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

### 15. Traceability — all 96 rules

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
| EXT-01, EXT-02 | FR-3.2, FR-3.2.4 | UD | OQ-24 — classification blocked, quantities measured |
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
| FLR-01 | FR-3.7, FR-3.7.1b | UD | OQ-09 — measured, never gated |
| FLR-02 | FR-3.7, FR-3.7.1b | UD | OQ-10 — measured, never gated |
| FLE-01 | FR-3.7, FR-3.7.1c | SD | **Exact and unactioned** — measured; gating pending OQ-27 |
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

#### 15.1 Disposition totals

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
implementable. No other rule's disposition changed; in particular the Fibonacci rules remain
blocked on OQ-05, and no blocked rule was reclassified to make the totals look better.

---

### 16. Assumptions

Only three, all structural rather than Elliott-semantic, and all falsifiable:

| # | Assumption | Basis | If wrong |
|---|---|---|---|
| A-1 | The Elliott module is a **read-only analyser** — it never influences trades, signals, or backtest results. | §1.3; nothing in the reference concerns execution. | Scope changes materially; §12 boundaries would need revisiting. |
| A-2 | Analysis runs against a **completed** backtest's stored `price_data`, not live/streaming bars. | Matches every existing analysis sub-resource (`/zigzag`, `/chart-patterns`). | Would require a streaming interface; out of scope. |
| A-3 | v1 targets a **single timeframe** — whatever the backtest ran on. | The platform is single-timeframe per backtest. | TRI-06's "every time frame" would become addressable — but it is blocked by OQ-13 regardless. |

**No assumption has been made about any Elliott Wave rule.** Where the reference is silent, this
SRS says UNDEFINED rather than assuming.

---

### 17. Decisions Phase 4 (architecture) must make

| # | Decision | Depends on |
|---|---|---|
| ~~**D-01**~~ | ~~Answer OQ-01~~ — **CLOSED 2026-08-10** as documentation, no behaviour change (§8.3). Original: what constitutes a gate, given the reference declares only "Guidelines". **Partially constrained** (blanket-non-gating ruled out, §8.3) but still **OPEN**. No longer on the critical path | — |
| ~~**D-02**~~ | ~~Answer OQ-04~~ — **✅ CLOSED 2026-08-09.** IMP-06 stays mandatory; divergence defined as an RSI(13) directional comparison (§6.1a) | — |
| ~~**D-02a**~~ | ~~Answer OQ-02 and OQ-03~~ — **✅ CLOSED 2026-08-09.** Absolute price distance; pivot-price interval overlap (§6.1b). **This broke the §8 chain.** | — |
| ~~**D-02c**~~ | ~~Confirm FR-3.1b.8~~ — **CLOSED 2026-08-09.** Reject-on-tie confirmed for both IMP-04 and IMP-05; no change made | — |
| ~~**D-02b**~~ | ~~Confirm FR-3.1a.7~~ — **CLOSED 2026-08-09.** Pivot-price reading confirmed; no change made | — |
| **D-03** | Answer OQ-05 — the tolerance model for the 14 discrete-ratio rules. **Investigated 2026-08-10 and deliberately deferred** (FR-4.2a): no tolerance is derivable from either the reference or the data, so the decision stays open rather than being made arbitrarily. Still determines API query parameters (API-1.4) and enumeration bounds (FR-2.6) if ever answered. | — |
| ~~**D-04**~~ | ~~Answer OQ-21 — pivot source~~ — **CLOSED 2026-08-09.** Independent Elliott-specific detector; existing swing/zigzag modules neither modified nor consumed (§4a) | — |
| ~~**D-13**~~ | ~~Choose pivot threshold values~~ — **CLOSED 2026-08-09, REVISED 2026-08-10.** Now 0.10% / r=4.0 / S=4. Rev 1 (0.20% / 2.5) superseded after implementation showed it could never satisfy IMP-02 (ARCHITECTURE §5.6) | — |
| ~~**D-14**~~ | ~~IMP-02 recursion floor~~ — **✅ CLOSED 2026-08-09.** At scale 1 there is no finer scale, so IMP-02 resolves to **UNDECIDABLE**, never a silent pass/fail (ARCHITECTURE §5.3). Confirmed | — |
| **D-05** | Whether to extend CI beyond `test_engine.py` — the 29 swing/zigzag regression tests are currently **not** run in CI (TR-11) | — |
| **D-06** | Whether to introduce TypeScript test infrastructure for the new chart (TR-10) | — |
| **D-07** | Whether Elliott Wave ever appears in the exported HTML report — and if so, how to avoid the existing `CandlestickChart.tsx` ↔ `api/report/charts.py` duplication hazard (§1.3) | — |
| **D-08** | Answer OQ-12 — whether Triangle is in v1 scope. **Investigated 2026-08-10 and deliberately deferred** (FR-3.8.1). The premise was wrong: the gates are NOT near-vacuous (8.4% pass, comparable to flat/zigzag). Triangle stays out of scope for a different reason — 21% of candidates contradict the reference's own definition of "sideways", and no threshold for it is derivable. Candidates are measured (FR-3.8.2). | — |
| ~~**D-09**~~ | ~~Answer OQ-18~~ — **CLOSED 2026-08-10.** `max_combination_depth = 1`, derived from the ladder (ARCHITECTURE §6.7a) | — |
| **D-10** | Answer OQ-20 — how a 3-swing move is classified as motive vs corrective | D-01 |
| **D-11** | Build order, given §8. Now depends on **D-02a**, not D-02 | D-01, D-02a |
| **D-12** | Whether an UNDECIDABLE candidate is surfaced in the UI or withheld (FE-3.1). **More concrete now:** the OQ-04 resolution creates a real UNDECIDABLE path (RSI(13) warmup, FR-1.8), so this is no longer hypothetical | D-02a |

---

### 18. Documentation Summary

#### Files created (1)

| File | Contents |
|---|---|
| `docs/ELLIOTT_WAVE_SRS.md` | This document — 20 sections (SS4a added), 132 tier-tagged requirement statements, full 94-rule traceability matrix, 20 Open Questions carried forward + 4 resolved, 15 Phase 4 decisions (D-02, D-02a, D-04 closed; D-02b/D-02c/D-13 open). |

#### Files modified

**One:** `docs/ELLIOTT_WAVE_RULES.md` — OQ-04 marked RESOLVED with a new "OQ-04 resolution"
section; IMP-06 and WP-10 rows updated; coverage summary recounted (two corrections recorded
there); header revision note added. **No source file, configuration file, or test was changed.**

#### Files deleted

**None.**

#### Sections added

§1 Purpose and scope · §2 Definitions · §3 Requirement classification scheme (SD/EI/UD/NI + EN) ·
§4 Input requirements · §5 Candidate enumeration · §6 Structure classification (11 structures +
degree) · §7 Measurement, lifecycle, determinism, serialization · §8 Critical dependency chain ·
§9 Data model · §10 API requirements · §11 Frontend requirements (dedicated tab + dedicated
chart + honest blocked-state display) · §12 Implementation boundaries · §13 Testing requirements ·
§14 Open Questions carried forward · §15 Traceability · §16 Assumptions · §17 Phase 4 decisions ·
§18 this summary.

#### Rules covered

**All 94 of 94.** Every rule ID appears exactly once in §15 — verified programmatically (no
omissions, no duplicates). Disposition, counted from the matrix (§15.1): **43** implementable
(39 source-defined + 4 specified by the OQ-02/03/04 decisions) · **2** partially implementable ·
**40** UD (blocked) · **5** NI · **4** informational. `ELLIOTT_WAVE_RULES.md` reports the
identical split.

#### Open Questions preserved

**20 of 27 unresolved, plus OQ-14 confirmed not implementable and closed (FR-3.5.2). OQ-01, OQ-02, OQ-03, OQ-04, OQ-18 and OQ-21 resolved by explicit project decision — OQ-01 as a documentation matter with no behavioural change (§8.3). OQ-25, OQ-26 and OQ-27 were added 2026-08-10.**

- **OQ-02, OQ-03** — RESOLVED (§6.1b). **OQ-04** — RESOLVED (§6.1a). **OQ-21** — RESOLVED (§4a).
  All four tagged **EN**, not SD: the reference contributes nothing to any of them, and each is
  recorded as a decision everywhere it appears.
- ~~**OQ-01**~~ — **RESOLVED 2026-08-10** as documentation, no behaviour change (§8.3). The split
  is adopted and restated as judgement informed by grammar; every gate is unchanged.
- **OQ-05, OQ-20** — untouched, still marked *"PRESERVED UNRESOLVED per instruction"* in §14.
- The remaining 17 are unchanged.

No classical Elliott Wave knowledge was substituted for any gap, and **no Open Question beyond
the four named was resolved.**

#### Implementation blockers

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
4. **OQ-12 / OQ-13** — Triangle. **Corrected 2026-08-10:** the gates are *not* near-vacuous (TRI-01/TRI-03 pass 8.4% of windows, exact and mandatory-tier). Triangle stays unclassified because "sideways" has no derivable threshold and 21% of candidates plainly trend. Candidates are measured; no `TRIANGLE` type is emitted.
5. ~~**OQ-18**~~ — **RESOLVED.** Double/Triple Three implemented; the *nested* branch is
   missing; the {zigzag, flat} branch is available. A depth cap would close this.
6. **OQ-24** — Extension undefined and **not derivable from data** (investigated 2026-08-10, FR-3.2.2); this also keeps OQ-19's zigzag/impulse tiebreak circular. Quantities are recorded, the verdict withheld.
7. **OQ-05** — 14 Fibonacci rules (not 16; FLE-F02/FLU-F02 state ranges, FR-4.2b). **Investigated 2026-08-10, no tolerance justifiable.** **Not a classification blocker** — non-gating
   measurements; ratios computable, just not declarable as "matched".
8. ~~**OQ-14**~~ — Motive Sequence **confirmed not implementable and closed 2026-08-10** (FR-3.5.2); excluded from v1 and from the unresolved tally.
9. ~~**OQ-01**~~ — **resolved 2026-08-10**, documentation only (§8.3). No gate changed.

#### Assumptions

Three, all structural, all listed in §16 (A-1 read-only analyser · A-2 completed backtest, not
streaming · A-3 single timeframe). **Zero assumptions about Elliott Wave semantics.**

#### What Phase 4 architecture will need to decide

**Fifteen** decisions in §17; **D-02, D-02a and D-04 are now CLOSED.** No decision now blocks
Phase 4 from beginning. The first item Phase 4 should settle is **D-13** (pivot threshold values),
since every downstream behaviour is observed through it, followed by **D-11** (build order), which
is now answerable — the natural order falls out of §8.2's pipeline. **D-02b** and **D-02c** are
one-line confirmations. **D-03** (Fibonacci tolerance) affects reporting quality, not
classification, and can land later. **D-01**, **D-08** (Triangle scope) and **D-09** (recursion
depth) govern structures outside the v1 core and need not gate the start of Phase 4.

---

<a id="architecture"></a>

## Part 3 — Elliott Wave — Architecture

**Phase 4 deliverable.** Version 1.0 (DRAFT — not approved for implementation).
Written 2026-08-09.

**Governing documents:** [ELLIOTT_WAVE_RULES.md](#rules) (96 rules, 27 OQs — 5
resolved) and [ELLIOTT_WAVE_SRS.md](#requirements) (requirements, rev 0.5). Where this
document and the SRS disagree, **the SRS wins** and this document is the bug.

> **No production code exists.** Function signatures below are *illustrative*, included only
> where prose would be ambiguous. They are not files, and are not binding on the implementer
> beyond the contracts the SRS already fixes.

---

### 1. Scope this architecture serves

**In (the v1 core path):** pivot detection → Impulse → Leading/Ending Diagonal, Zigzag, generic
Flat, Running Flat → serialization → one API sub-resource → one dedicated tab with one dedicated
chart.

**Out (deferred, each blocked by its own Open Question):** Regular Flat and Expanded Flat
(OQ-09/OQ-10) · Triangle **classification** (OQ-12/OQ-13 — candidates measured since
2026-08-10, §6.7b) · Impulse with Extension **classification**
(OQ-24 — its quantities *are* measured since 2026-08-10, §6.8) · Motive Sequence (OQ-14, not implementable) · Fibonacci **matching** (OQ-05 — ratios are
still *computed and recorded*, just never declared "matched").

---

### 2. Package layout

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
├── triangle.py        Triangle candidates — measures, never classifies
├── measurements.py    guideline ratios + extension quantities — records, never decides
├── validation.py      lifecycle transitions + blocked-rule registry
└── pipeline.py        orchestration; the one correct call order
```

**13 files** (11 at v1; `combination.py` and `triangle.py` added 2026-08-10).
Every one earns its place below.

#### 2.1 Modules deliberately NOT created

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

### 3. Dependency graph

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

### 4. Data flow

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

### 5. D-13 — pivot threshold defaults (calibrated, not guessed)

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

#### 5.1 [SUPERSEDED — rev 1] Why θ_base = 0.20%

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

#### 5.2 [SUPERSEDED — rev 1] Why ratio r = 2.5

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

#### 5.3 Why S = 4 (unchanged in rev 2)

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

#### 5.6 [CURRENT — rev 2] Why the rev-1 ladder failed, and what replaced it

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

#### 5.4 Cross-scale containment — measured, still not assumed

FR-1d.4 forbids assuming coarse-scale pivots are a subset of fine-scale pivots. Measured
containment is **99–100%** across every ratio and dataset tested.

**That does not change the requirement.** 99% is not 100%, so hierarchy construction must still
handle the non-contained pivot explicitly rather than crash or silently drop it. TR-7b requires
the rate to be *measured and reported*, not asserted — the number above is the current baseline,
not a guarantee.

#### 5.5 Scale exhaustion

On short inputs a coarse scale may yield fewer than 2 pivots (observed on the 100–390 bar real
CSVs). A scale with <2 pivots contributes **no structures** and SHALL NOT raise. The result's
`blocked_rules` records that the scale was empty, so a thin analysis is visibly thin rather than
indistinguishable from "nothing found".

---

### 6. Module responsibilities

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
| `triangle.py` | Form TRI-01/TRI-03 candidates and measure TRI-05/06/07. Never gate. |
| `measurements.py` | Compute and record guideline ratios and EXT-01/EXT-02 quantities. **Cannot match, cannot classify.** |
| `validation.py` | Own lifecycle transitions and the blocked-rule registry. |
| `pipeline.py` | Run the layers in the one correct order and assemble the result. |
| `__init__.py` | Public surface: `run_analysis`, config defaults, engine version. |

#### 6.1 `models.py`

Owns `Pivot`, `Wave`, `LifecycleState`, `StructureType`, `AnalysisResult`, `EngineConfig`.

- `Pivot` carries `index`, `confirm_index`, `timestamp`, `price`, `kind`, `scale` (DM-1).
- `Wave` carries `id`, `start_pivot`, `end_pivot`, `label`, `structure_type`, `scale`,
  `parent_id`, `child_ids`, `state`, `measurements`, `blocked_by` (DM-2).
- **`Wave` has no `confidence`, `score`, `probability`, `valid`, or `violated_rules` field**
  (DM-2.1, DM-2.2, FR-7.4). Their absence is enforced by TR-4.
- `LifecycleState`: `ENUMERATED → GATED → MEASURED`, plus `UNDECIDABLE`. **No INVALID/REJECTED**
  (FR-5.4) — a candidate failing an implementable gate is never constructed.

#### 6.2 `pivots.py`

Implements SRS §4a in full. Single deterministic pass per scale.

```python
def detect_pivots(df, theta_base=0.002, ratio=2.5, scales=4) -> list[Pivot]: ...
```

- Emits `confirm_index > index` always; **never emits the final unconfirmed extreme** (FR-1b.3).
- Pivot price is the bar's own extreme — high for `H`, low for `L` (FR-1c.1).
- Alternation guaranteed by construction (FR-1c.2).
- **Owns no Elliott knowledge.** It knows nothing about waves, labels, or degrees. This is what
  keeps the "independent detector" claim auditable.

#### 6.3 `momentum.py`

The single point of contact with shared indicator code (A-2).

```python
def has_divergence(rsi, price_idx_a, price_a, price_idx_b, price_b, direction) -> bool | None: ...
```

Returns `None` — meaning **UNDECIDABLE**, not False — when RSI is `NaN` at either bar
(FR-3.1a.6). Isolating this in its own module keeps `impulse.py` free of indicator coupling, and
means the one permitted external dependency lives in one greppable file.

#### 6.4 `hierarchy.py`

Builds the wave tree from scale-tagged pivots. Handles the non-containment case explicitly
(§5.4). Assigns `scale`, never `degree` — degree naming is **OQ-17, still open** (FR-1d.3).

#### 6.5 `impulse.py`

```python
def classify_impulses(tree, rsi, config) -> list[Wave]: ...
```

Gates in order, cheapest first: IMP-01 (leg count) → IMP-03 (wave 2 retrace) → IMP-04 (absolute
price distance, strict `>`) → IMP-05 (pivot-price interval overlap, closed intervals) → IMP-02
(recursive subdivision) → IMP-06 (RSI divergence, via `momentum`).

Ordering is a performance choice only; it must not change results. IMP-02 and IMP-06 are last
because they are the expensive ones, and both can yield UNDECIDABLE.

#### 6.6 `diagonal.py`

LD-01/ED-01 (host position) and LD-03/ED-03 (subdivision). **LD-02/ED-02 overlap is recorded and
must never gate** — the reference is explicit that overlap "is not a condition" (FR-3.3.1), and
TR-3 exists solely to stop that regressing. Wedge geometry is **not** implemented (OQ-15).

##### 6.6.1 Sub-wave grouping — REVISED 2026-08-10 (rev 2 supersedes rev 1)

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

#### 6.7 `correction.py`

Zigzag (ZZ-01…04), generic Flat (FL-01/02), Running Flat (FLU-01). Regular and Expanded Flat are
**not** implemented (OQ-09/OQ-10) — `validation.py` records them as blocked so their absence is
reported rather than inferred.

#### 6.7a `combination.py`

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

#### 6.7b `triangle.py`

Forms candidate windows from **TRI-01** ("labelled as ABCDE" — five sides) and **TRI-03**
("3-3-3-3-3"), measures them, and names nothing. `StructureType` has no `TRIANGLE` member and
candidates never enter `waves`; they go to `AnalysisResult.triangle_candidates` as plain records,
because putting an unnameable shape into the list the chart renders would present a guess as
analysis.

**Both rules are exact and mandatory-tier**, the same signature FLE-01 has, and genuinely
selective: 328 of 3,912 five-leg windows pass (8.4%), against 318 flats and 173 zigzags on the
same data. A prior note calling this gate "near-vacuous" was measured and corrected.

**Why it still does not gate.** Three reasons, in increasing order of weight. The strict reading
of "subdivided into three" finds 1 candidate in 3,912, so the loose predicate `diagonal.py`
already applies to LD-03/ED-03's identical `3-3-3-3-3` is used instead — inheriting **OQ-25**.
TRI-02's host rule is worded "usually" (guideline-tier, an OQ-01 question) and matches only 6 of
328 anyway. And decisively: the reference opens *"a triangle is a sideways movement"*, yet 21% of
candidates have net displacement above half their path length. TRI-01 + TRI-03 is an **incomplete**
criterion for the word — it omits exactly the property that defines it — where FLE-01 was a
complete criterion for its own claim.

`TRI-05_net_over_path` quantifies "sideways" without judging it; no threshold exists, and the
apparent three-mode structure in the data was rejected by bootstrap (0 of 3 modes stable).
`TRI-07`'s two trendline slopes are recorded because they are what *would* name the four variants
— which the reference names and then describes only in a graphic. `TRI-06` records RSI at each
pivot; "supports" states no direction, threshold or comparison.

#### 6.8 `measurements.py`

Computes every guideline ratio the reference states (IMP-F01…F04, ZZ-F01/F02, …) and records the
raw value. **It exposes no comparison, tolerance, or match function at all** — the absence of the
capability is the enforcement mechanism for OQ-05, and TR-2 asserts no tolerance constant exists.

**OQ-05 investigated 2026-08-10 and left open.** The absence stays. The reference states no
tolerance and writes an explicit range where it means one (3 rules do), so its discrete lists
are discrete by intent; real ratios show no clustering on the stated values once density is
controlled for (0 of 5 families significant under shift and empirical nulls); and the width a
tolerance would need varies 11x across families, so no single global value could serve them.
Scope corrected at the same time: OQ-05 blocks **14** rules, not 16 — FLE-F02 and FLU-F02 state
ranges, which need no tolerance, and are blocked by OQ-11 instead.

**Flat subtypes (FLR-01/02, FLE-01/02), added 2026-08-10.** `record_flat_subtype` records wave
B's retracement of wave A, whether wave B passed wave A's start, and where wave C landed relative
to wave A's end. OQ-09 and OQ-10 were investigated over 356 real flats and stayed open: no cliff
in either dimension. **A correction landed with it** — the old claim that Regular and Expanded are
separated only by slightly-vs-substantially was wrong. FLE-01 is a second, *exact* discriminator
needing no threshold, and it was simply never actioned (33.5% of real flats satisfy it). It is
measured but does not gate, because 29 of 34 structures satisfying it also satisfy FLU-01 and the
reference states no precedence — recorded as the new **OQ-27**.

**Extension (EXT-01/EXT-02), added 2026-08-10.** `record_extension` records which motive wave is
longest, its ratio to the second-longest, and finer-scale subdivision counts where a finer scale
exists. It renders **no verdict**: OQ-24 was investigated with the D-13 data-derivation method and
stayed open, because five candidate formulations over 1,142 impulses all decay smoothly with no
cliff, and EXT-02's conjunctive subdivision half is unmeasurable on 98.8% of the population and
names a different wave than length does on 36% of the rest. OQ-24 is **independent of OQ-05** —
unlike DT-05 there is no stated inequality to lift, so a Fibonacci resolution would not unblock it.
Every measured structure carries `blocked_by: ["OQ-24"]`, and `StructureType` still has no
`IMPULSE_WITH_EXTENSION` member. Three TR-2 guards hold the line: no verdict identifier anywhere,
the word "extension" confined to `measurements.py` and `pipeline.py`, and no float literal or
comparison in the extension code — a threshold could not exist without one.

#### 6.9 `validation.py`

Lifecycle transitions (FR-5.2/5.3) and the `blocked_rules` registry (DM-3). Given the set of rules
this build can evaluate, it produces the list of rule IDs that were **not** evaluated and why —
so a client can render an honest "what wasn't checked" panel (FE-3.2) instead of presenting a
partial analysis as complete.

#### 6.10 `pipeline.py`

```python
def run_analysis(df, config=None) -> AnalysisResult: ...
```

The single correct ordering — corrections depend on impulses, diagonals depend on hosts. Ordering
lives here and nowhere else so it can be tested as one fact.

---

### 7. Cross-cutting guarantees

| Concern | Mechanism |
|---|---|
| **Determinism** (FR-6.1) | No randomness, no wall-clock, no I/O anywhere in the package. Wave IDs derived from `(scale, start_index, end_index, structure_type)` — stable across runs, no counters or UUIDs. |
| **No look-ahead** (FR-1b) | `confirm_index` on every pivot; `pivots.py` never emits the unconfirmed tail. TR-7a verifies by truncation. |
| **Immutability** (FR-1a.3, FR-5.5) | Input frame never mutated; later layers add waves and extend `child_ids`, never rewrite or delete an earlier layer's wave. |
| **Independence** (FR-1f.2) | No import of, or dependency on, existing swing/zigzag code. TR-7 checks the resolved import graph. |
| **No scoring** (FR-7.4) | No `scoring.py`, no score field on `Wave`. Two independent guarantees. |
| **Honest gaps** (DM-3) | `blocked_rules` on every result; `blocked_by` on every UNDECIDABLE wave. |

---

### 8. Integration points

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

### 9. Testing architecture

| Test module | Covers |
|---|---|
| `test_ew_pivots.py` | §4a: alternation, `confirm_index > index`, unconfirmed tail withheld, **TR-7a truncation/no-look-ahead**, TR-7b containment measurement, scale exhaustion, determinism |
| `test_ew_impulse.py` | IMP-01…06 each isolated with a pass fixture and a violates-only-this fixture; **TR-2b** boundary cases; **TR-2a** IMP-06's four outcomes incl. `NaN` → UNDECIDABLE |
| `test_ew_diagonal.py` | LD/ED position + subdivision; **TR-3**: overlap never gates |
| `test_ew_correction.py` | Zigzag, generic Flat, Running Flat; Regular/Expanded absent and *reported* as blocked |
| `test_combination.py` | DT-01/03/05, TT-01/03/05, the OQ-18 depth-cap boundary, and OQ-26 swing count recorded-not-gated |
| `test_extension.py` | EXT-01/EXT-02 quantities, reject-on-tie, scale-1 unmeasurability reported as None, and the OQ-24 abstention (no verdict at any ratio) |
| `test_triangle.py` | Candidate formation, sidewaysness at both extremes, RSI None-vs-zero, and the OQ-12/13 abstention (a plainly trending window is recorded, not rejected, and never named) |
| `test_flat_subtype.py` | FLR-01/FLR-02/FLE-01 quantities, sign conventions in both directions, and the OQ-09/OQ-10 abstention (an extreme expanded shape stays generically typed) |
| `test_ew_guards.py` | **TR-2** no invented constants · **TR-4** no score field · **TR-7** independence via import graph · blocked-rule registry completeness |
| `test_ew_pipeline.py` | Ordering, determinism over ≥20 runs, serializer shape, live/report default parity (FR-1e.4) |

`tests/test_engine.py` and `tests/test_swing_zigzag_regression.py` must continue to pass
**unmodified** (TR-6). CI currently runs only `test_engine.py` — extending it is **D-05**, still
open.

---

### 10. Build order

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

### 11. Constraints on implementation (Phase 5)

1. **Do not create the six modules in §2.1.** Their absence is load-bearing.
2. **Do not add a tolerance, epsilon, or buffer anywhere.** OQ-05 is open; TR-2 will catch it.
3. **Do not add a confidence/score field.** FR-7.4; TR-4 will catch it.
4. **Do not import or consume `swing_identification` / `zigzag`.** FR-1f.2; TR-7 will catch it.
5. **Do not implement wedge geometry, Regular/Expanded Flat, or Fibonacci matching.**
   All blocked; register them in `blocked_rules` instead. *(DT/TT were unblocked 2026-08-10 by
   the OQ-18 depth cap. Extension, the Flat subtypes and Triangle candidates are all MEASURED
   but must never be CLASSIFIED — OQ-24, OQ-09/10 and OQ-12/13 all stay open.)*
6. **Do not touch `CandlestickChart.tsx`.**
7. **When a rule cannot be evaluated, return UNDECIDABLE.** Never guess a pass or a fail.

---

### 12. Open items after this document

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

### 13. Documentation Summary

**Files created (1)** — `docs/ELLIOTT_WAVE_ARCHITECTURE.md`: package layout (11 modules), the six
modules deliberately not created and why, dependency graph with five enforced properties, data
flow, **D-13 calibration with measured evidence**, per-module responsibilities and illustrative
signatures, cross-cutting guarantees, integration points, test architecture, build order, seven
implementation constraints, open-items register.

**Files modified (2)** — `ELLIOTT_WAVE_SRS.md` and `ELLIOTT_WAVE_RULES.md`: D-13 values recorded;
D-02b/D-02c marked closed; OQ counts and revision notes updated.

**Files deleted** — none. **Production code written** — none.

---

<a id="implementation"></a>

## Part 4 — Elliott Wave — Implementation Record

**Final documentation for the from-scratch Elliott Wave rebuild.**
Written 2026-08-10. Branch `feature/elliott-wave-rebuild` (local, unpushed).

**Sole rule source:** <https://elliottwave-forecast.com/elliott-wave-theory/>
**Companion documents:** [ELLIOTT_WAVE_RULES.md](#rules) (96 rules, 27 Open
Questions) · [ELLIOTT_WAVE_SRS.md](#requirements) (requirements) ·
[ELLIOTT_WAVE_ARCHITECTURE.md](#architecture) (module design, D-13 calibration)

> **Read this first.** This engine is deliberately incomplete, and its incompleteness is
> reported at runtime rather than hidden. Roughly half the reference's rules cannot be
> implemented because the source does not define them precisely enough. **Of 27 Open Questions:
> 6 resolved, 20 unresolved, 1 confirmed not implementable.** Every affected rule is registered in
> `AnalysisResult.blocked_rules` and surfaced in both the UI and the exported report. Nothing
> here fabricates a value the reference does not supply.
>
> **V2 Step 6 addendum — 2026-08-10.** **OQ-14 (Motive Sequence) investigated and closed as
> NOT IMPLEMENTABLE.** Re-verified against the live reference — unlike the three preceding
> investigations, this one found nothing the extraction had missed. The definition is circular
> with nothing inside it: MS-01 says "incomplete", MS-03 defines completeness by "the numbers
> in the motive sequence", and the numbers are never stated. MS-03's "much *like* the
> Fibonacci number sequence" is a simile, not an identity. Reclassified out of the unresolved
> tally: **5 resolved, 21 unresolved, 1 not implementable**. No code written. *(Superseded by
> Step 7: OQ-01 later resolved as documentation, giving the final **6 / 20 / 1**.)*
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

### 1. What was built

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

### 2. Files

#### 2.1 Created (23)

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

#### 2.2 Modified

`api/serializers.py` (+1 function) · `api/routers/backtests.py` (+1 endpoint) ·
`api/report/report.py` (perf fix + report section) ·
`web/src/components/charts/ElliottWaveChart.tsx` (new component, then hierarchical labelling) ·
`web/src/lib/types.ts` (+6 interfaces) · `web/src/lib/api.ts` (+1 method) ·
`web/src/features/backtest/ResultsPage.tsx` (4 additions) ·
`.github/workflows/ci.yml` (D-05) · `CLAUDE.md`, `CHANGELOG.md`, `Dockerfile`

#### 2.3 Deleted (60) — the previous implementation

9 `src/analysis/*.py` engine modules · `api/routers/elliott_wave.py`, `api/report/wave_layout.py` ·
`benchmark/` (17) · `validation/` (17) · `cli/` (2, the `elliott` CLI) · `tests/elliott/` (10) ·
2 web components · `docs/ELLIOTT_WAVE_NOTATION.md`

#### 2.4 Untouched by design

`src/analysis/swing_identification.py` and `src/analysis/zigzag.py` — neither modified **nor
consumed** (FR-1f.2, OQ-21). `CandlestickChart.tsx` — Price & Trades remains a plain Price &
Trades chart. `api/report/charts.py` — its chart builders have zero call sites; adding to it
would be dead code.

---

### 3. Structures

#### 3.1 Implemented

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

#### 3.2 Not implemented, and why

| Structure / feature | Blocked by | Reason |
|---|---|---|
| **Regular Flat** | OQ-09, OQ-10 | "Wave B terminates **near** the start of wave A", "wave C **slightly** beyond" — neither quantified; the paired ratio is a single point (exactly 90%) with no tolerance |
| **Expanded Flat** *(wave C half)* | OQ-10, OQ-27 | Needs "**substantially** beyond", unquantified and with no cliff in 356 real flats. **Corrected 2026-08-10:** this row previously said Regular and Expanded are separated *only* by slightly-vs-substantially. They are not — **FLE-01** (wave B beyond wave A start) is a second, *exact* discriminator, now measured. It does not gate pending **OQ-27** (29 of 34 structures satisfying it also satisfy FLU-01) |
| **Triangle** *(classification only; candidates measured)* | OQ-12, OQ-13 | No Fibonacci ratios, no rules for waves D/E, no discriminators between the four named variants, and a subdivision gate so permissive it would match almost any 5-leg sideways move. "RSI must support the triangle in every time frame" is undefined |
| ~~**Double / Triple Three**~~ | ~~OQ-18~~ | **IMPLEMENTED 2026-08-10** — recursion capped at depth 1, derived from the ladder. Their DT-02/TT-02 swing counts remain blocked by the new **OQ-26** (recorded, never gated) |
| **Impulse with Extension** *(classification only)* | OQ-24 *(investigated 2026-08-10, no cliff in data; independent of OQ-05)* | "Extension" / "elongated" / "exaggerated subdivisions" have no numeric definition anywhere |
| **Motive Sequence** | ~~OQ-14~~ *(closed 2026-08-10 — confirmed NOT IMPLEMENTABLE, not merely unresolved)* | Defined entirely by reference to "the numbers in the motive sequence" — **and those numbers are never stated**. Not implementable at any effort |
| **Fibonacci matching** | OQ-05 *(investigated 2026-08-10; blocks 14 rules, not 16)* | All 16 ratios are discrete exact values with no stated tolerance. Ratios **are computed and recorded**; they are never declared "matched" |
| **Named wave degrees** | OQ-17 | Only 2 of 9 degrees map to a timeframe and no rule assigns degree from price. Pivots carry an integer `scale` index only |
| **Confidence / scoring** | FR-7.4 | The reference states no weighting function anywhere. No such field exists in the model, the API, or the UI |

Each is registered in `validation.BLOCKED_RULES` and reported at runtime — absent, not silently
missing.

---

### 4. Decisions settled

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

### 5. Known limitations

#### 5.1 Motive-parent nesting does not occur — accepted, not a bug

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

#### 5.2 Other limitations

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

### 6. API

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

### 7. UI

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

### 8. Tests and CI

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

### 9. Performance

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

#### V2 — all deferred-structure investigations complete (2026-08-10)

Seven follow-up steps closed out every deferred structure and every substantive Open Question on
the list. **One was built, four were investigated and deliberately left measurement-only, one was
closed as impossible, and one was resolved on paper with no behavioural change.**

| Step | Question | Outcome |
|---|---|---|
| 1 | **OQ-18** Double/Triple Three | **Resolved and built.** Recursion capped at depth 1, derived from the ladder. Two missed rules (DT-05/TT-05) extracted; new **OQ-26** raised |
| 2 | **OQ-24** Extension | **Measurement-only.** No cliff in five formulations over 1,142 impulses; EXT-02 unmeasurable on 98.7% |
| 3 | **OQ-09/OQ-10** Regular/Expanded Flat | **Measurement-only.** No cliff in either dimension across 356 flats. Found **FLE-01** — exact and unactioned — but gating it needs an unstated precedence rule, raised as **OQ-27** |
| 4 | **OQ-05** Fibonacci matching | **Measurement-only.** No tolerance in the reference, no clustering once density is controlled for, 11× spread in the width one would need. Scope corrected: it blocks 14 rules, not 16 |
| 5 | **OQ-12/OQ-13** Triangle | **Measurement-only.** TRI-01/TRI-03 turned out exact and selective (8.4%), not "near-vacuous" as recorded — but 21% of candidates contradict the reference's own definition of "sideways" |
| 6 | **OQ-14** Motive Sequence | **Closed — not implementable.** The definition is circular and the numbers are never stated; the absent content *is* the rule |
| 7 | **OQ-01** Mandatory/Guideline tiers | **Resolved as documentation.** Tiers adopted, restated as judgement *informed by* grammar rather than derived from it. **No gate reclassified** — blast radius measured per rule first |

The pattern is deliberate. Four of the seven ended in abstention, and in each case the reason is
recorded with its evidence rather than as a bare "blocked", so the question does not need
re-investigating. Along the way the work also **corrected four claims this project had made about
itself**: the missed DT-05/TT-05 rules, the "zero scale-≥2 impulses" absolute, the "separated only
by slightly-vs-substantially" flat claim, and the "near-vacuous" triangle gate — plus the OQ-05
attribution and the grammar-derivation claim. The count of unresolved questions went **up**
(21 → 20 with two closures, but 27 total after three new ones surfaced), which for honest
bookkeeping is the right direction.

**Structures added since v1:** Double Three, Triple Three. **Measurement-only additions:**
extension quantities, flat-subtype quantities, triangle candidates. **Gates changed: none.**

---

### 10. Remaining Open Questions — 20 of 27 unresolved, plus OQ-14 closed as not implementable

**Resolved (4):** OQ-02, OQ-03, OQ-04, OQ-21.

**Unresolved (21):**

| OQ | Subject |
|---|---|
| ~~**OQ-01**~~ *(resolved 2026-08-10 — documentation only, no gate changed)* | Whether the grammar-based Mandatory/Guideline split is the adopted classification. *Partially constrained* (blanket-non-gating ruled out) but not answered |
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

OQ-05 and OQ-20 remain explicitly preserved unresolved by instruction. OQ-01 was preserved throughout the v1 build and resolved only in V2 Step 7, as documentation with no behavioural change. **No Open
Question was resolved by substituting classical Elliott Wave knowledge** — where the reference is
silent, the engine says UNDECIDABLE.

---

### 11. Documentation Summary

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
**Remaining Open Questions:** §10 — **6 resolved, 20 unresolved, 1 not implementable** (of 27),
listed individually, with the V2 investigation summary above them.

**No code changed in this step** — documentation only.
