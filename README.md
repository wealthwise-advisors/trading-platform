<div align="center">

<img src="docs/assets/hero.svg" alt="AutoTrader — Algorithmic Trading Research & Execution Platform" width="100%">

<br><br>

### Market data goes in. A number you can defend comes out.

**AutoTrader** is a futures research platform: it reads the market, tests an idea
against it bar by bar, charges realistic costs for every fill, and follows the live
tape while it does. Built at **WealthWise Advisors**.

<br>

[![CI](https://img.shields.io/badge/CI-passing-22c55e?style=for-the-badge&logo=githubactions&logoColor=white)](../../actions/workflows/ci.yml)
[![Deploy](https://img.shields.io/badge/deploy-live-ff9900?style=for-the-badge&logo=amazonaws&logoColor=white)](../../actions/workflows/deploy.yml)
[![Tests](https://img.shields.io/badge/tests-1771%20passing-22c55e?style=for-the-badge&logo=pytest&logoColor=white)](#-testing--quality)

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](api)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](web)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)](web/tsconfig.json)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white)](web/vite.config.ts)
[![pandas](https://img.shields.io/badge/pandas-150458?style=flat-square&logo=pandas&logoColor=white)](requirements.txt)
[![Tailwind](https://img.shields.io/badge/Tailwind-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)](web/package.json)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](Dockerfile)
[![AWS](https://img.shields.io/badge/AWS_EC2-232F3E?style=flat-square&logo=amazonec2&logoColor=white)](.github/workflows/deploy.yml)
[![Schwab](https://img.shields.io/badge/Schwab-live_data-00a0df?style=flat-square)](src/data/schwab_provider.py)
[![Ruff](https://img.shields.io/badge/ruff-clean-D7FF64?style=flat-square&logo=ruff&logoColor=black)](pyproject.toml)
[![License](https://img.shields.io/badge/license-proprietary-64748b?style=flat-square)](LICENSE)

</div>

<br>

<div align="center">
<img src="docs/assets/pipeline.svg" alt="Market data flows through resampling, analysis, strategy and the paper broker to a scored result" width="100%">
</div>

<br>

---

## 📑 Table of Contents

<table>
<tr><td valign="top" width="33%">

**◆ Understanding it**
- [About the Platform](#-about-the-platform)
- [Why It Exists](#-why-it-exists)
- [Highlights](#-highlights)
- [Live Replay](#-live-replay)

</td><td valign="top" width="33%">

**◆ How it works**
- [Architecture](#-architecture)
- [Project Workflow](#-project-workflow)
- [Market Intelligence](#-market-intelligence)
- [Strategy Engine](#-strategy-engine)
- [Backtesting & Execution](#-backtesting--execution)
- [Dashboard](#-dashboard)
- [API Reference](#-api-reference)

</td><td valign="top" width="33%">

**◆ Working with it**
- [Technology Stack](#-technology-stack)
- [Folder Structure](#-folder-structure)
- [Getting Started](#-getting-started)
- [Testing & Quality](#-testing--quality)
- [Deployment](#-deployment)
- [Repository Ecosystem](#-repository-ecosystem)
- [Documentation](#-documentation)

</td></tr>
</table>

<br>

---

## 🎯 About the Platform

Most trading tools tell you what to buy. **This one tells you whether you should
have believed the last thing that told you what to buy.**

AutoTrader is an instrument for measuring trading ideas. You give it an instrument,
a date range and a strategy; it replays the market bar by bar, executes the strategy
against a broker that charges commission and slippage on every fill, and hands back a
result you can reproduce exactly.

<table>
<tr>
<td width="33%" valign="top" align="center">

### 📖
**Read the market**

Elliott Wave structure, swing pivots, chart and candlestick patterns, VWAP with
deviation bands, volume profile, and a regime classifier that says whether the
market is trending, ranging or volatile.

</td>
<td width="33%" valign="top" align="center">

### ⚖️
**Test the idea**

Bar-by-bar replay with a paper broker. Commission per contract, slippage in ticks,
prices rounded to the real increment — a plausible fill, not a closing price.

</td>
<td width="33%" valign="top" align="center">

### 🔬
**Trust the number**

1,771 tests, deterministic runs, one shared bar aggregator, and a deploy that
refuses to succeed unless the server is actually running the commit it claims.

</td>
</tr>
</table>

> **What it is not.** Not a signal service, not an auto-trading bot, not a promise
> about tomorrow. Live *data* is production-ready; live *execution* is deliberately
> experimental and unwired. The output is evidence, and evidence is only worth
> something if you can say how it was produced.

<br>

---

## 💡 Why It Exists

A backtest is easy to write and very easy to fool yourself with. Four specific ways —
each one a real bug this codebase has hit and fixed — shape how the platform is built:

<table>
<tr><td width="6%" align="center">

**❶**

</td><td>

**A bar that changes after you have seen it.** A bar polled mid-minute has a high and
a low that are still moving. Show it, and every number derived from it is provisional
without saying so. → *Only closed bars ever reach the tape.*

</td></tr>
<tr><td align="center">

**❷**

</td><td>

**Two code paths that disagree about a bar.** Aggregation was once duplicated across
three providers; the copy that forgot to anchor to the session kept reintroducing
shifted bars. → *One aggregator, in [`src/data/resample.py`](src/data/resample.py).*

</td></tr>
<tr><td align="center">

**❸**

</td><td>

**A number that moves when you touch a checkbox.** The same 30-minute bar reported
two different VWAPs depending on which other timeframes were selected. → *Each bar
carries its own volume-weighted price, built from the minutes inside it.*

</td></tr>
<tr><td align="center">

**❹**

</td><td>

**A deploy that quietly changes nothing.** → *The pipeline asks the running server
which commit it is serving and fails the run unless it matches.*

</td></tr>
</table>

<br>

---

## ✨ Highlights

<table>
<tr>
<td width="50%" valign="top">

### 📡 Follows the live market
Load today, press Play, and the tape keeps up on its own — new bars land **within
~15 seconds of closing**. No reloading, no checkbox to remember.

</td>
<td width="50%" valign="top">

### 🌊 Elliott Wave engine
Thirteen modules — impulses, corrections, diagonals, triangles, combinations — with
explicit rules a count must satisfy and a hierarchy pass that nests degrees.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### ⏱️ Eleven timeframes, one clock
Panes advance off a **shared market clock** measured in market time, not in bars, so
a 1m pane and a 1h pane always show the same instant.

</td>
<td width="50%" valign="top">

### 📊 Broker-accurate VWAP
Volume-weighted price per bar with σ bands at any level, colour-grouped by whole
number so agreement across timeframes is visible at a glance.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 💰 Costs that are actually charged
Commission per contract, slippage in ticks, tick-size rounding, and per-instrument
contract specifications so P&L lands in real currency.

</td>
<td width="50%" valign="top">

### 📤 Exports that match the screen
**CSV · XLSX · PDF · DOCX**, with charts rendered server-side from the same data the
dashboard drew.

</td>
</tr>
</table>

<br>

---

## 📡 Live Replay

<div align="center">
<img src="docs/assets/live-tape.svg" alt="Candles arriving on their own as the market prints them, with the status line reporting what is happening" width="100%">
</div>

<br>

The flagship surface. A session loads history, plays it bar by bar, and then **keeps
going** — following the live market instead of stopping at the snapshot it loaded.

```mermaid
flowchart LR
    L["⬇ Load Data"] ==> P["▶ Play"]
    P ==> E["Live edge<br/>reached"]
    E ==> F["⟳ Follow live<br/><i>starts by itself</i>"]
    F ==> Q["Poll every 15s"]
    Q ==> C{"New closed<br/>bar?"}
    C ==>|yes| U["Tape advances<br/>VWAP · bands · signals"]
    C ==>|no| W["“still forming”"]
    U ==> Q
    W ==> Q

    classDef a fill:#0b1220,stroke:#2dd4bf,stroke-width:2px,color:#e2e8f0
    classDef b fill:#0b1220,stroke:#334155,stroke-width:1px,color:#94a3b8
    class L,P,F,U a
    class E,Q,C,W b
```

**What makes it trustworthy rather than merely live**

| | |
|---|---|
| **Only closed bars** | A bar polled mid-minute is still moving. Showing it puts a number on screen that changes afterwards — so it waits for the close |
| **Never silent** | The status line always states what is happening: `1 new bar, now at 15:56` · `the newest bar is still forming` · `could not reach the data source`. A quiet screen during an outage looks exactly like a calm market |
| **A pause is respected** | Following keeps the tape at the live edge; it does not drag you back from a bar you paused to study |
| **The gap is named** | *"1 min behind the clock — the current bar is still forming."* And when the gap exceeds what the design accounts for, it says the feed may be delayed instead of reassuring you |

> [!NOTE]
> **Why it looks one bar behind a broker platform.** thinkorswim draws the bar
> *currently forming*; this app draws the last bar that **closed**. Same instant,
> different bar. That is a difference in what is displayed, not a delay — and
> measured against the live feed, a closed bar reaches the tape in **5–16 seconds**.

<br>

---

## 🏗 Architecture

```mermaid
flowchart TB
    subgraph SRC["📥 Data Sources"]
        SCH["Schwab API<br/><i>live · ~180 days</i>"]
        CSV["CSV archive<br/><i>18 years</i>"]
        SYN["Synthetic<br/><i>deterministic</i>"]
    end

    subgraph CORE["⚙️ Core Engine · src/"]
        RS["Resampler<br/><i>one shared aggregator</i>"]
        AN["Analysis<br/><i>waves · patterns · VWAP</i>"]
        ST["Strategies<br/><i>five, one interface</i>"]
        BR["Paper Broker<br/><i>commission · slippage</i>"]
        RE["Replay Engine<br/><i>shared market clock</i>"]
    end

    subgraph IF["🖥 Interfaces"]
        API["FastAPI<br/><i>REST + WebSocket</i>"]
        WEB["React Dashboard"]
        EXP["Export<br/><i>CSV · XLSX · PDF · DOCX</i>"]
    end

    SCH ==> RS
    CSV ==> RS
    SYN ==> RS
    RS ==> AN ==> ST ==> BR
    RS ==> RE
    RE ==> API
    BR ==> API
    API <==> WEB
    API ==> EXP

    classDef src  fill:#0b1220,stroke:#38bdf8,stroke-width:2px,color:#e2e8f0
    classDef core fill:#0b1220,stroke:#a78bfa,stroke-width:2px,color:#e2e8f0
    classDef ifc  fill:#0b1220,stroke:#2dd4bf,stroke-width:2px,color:#e2e8f0
    class SCH,CSV,SYN src
    class RS,AN,ST,BR,RE core
    class API,WEB,EXP ifc
```

**The engine knows nothing about how it is called.** No HTTP, no React, no framework
inside [`src/`](src) — which is what lets the same analysis run from a test, from the
API and from a script and give the same answer each time.

<br>

---

## 🔄 Project Workflow

How a change actually travels from an idea to the live URL.

```mermaid
flowchart LR
    ID["💡 Idea"] ==> RE["🔬 Research<br/><i>measure it</i>"]
    RE ==> IM["⌨️ Implement<br/><i>+ tests that can fail</i>"]
    IM ==> VA["✅ Verify<br/><i>1,771 tests · ruff · tsc</i>"]
    VA ==> BR["📉 Backtest & Replay<br/><i>against real bars</i>"]
    BR ==> PR["🔀 Pull Request<br/><i>6 CI checks</i>"]
    PR ==> MG["🎯 Merge"]
    MG ==> DP["🚀 Deploy<br/><i>SHA asserted</i>"]
    DP ==> LV["🌐 Live"]

    classDef n fill:#0b1220,stroke:#334155,stroke-width:1px,color:#94a3b8
    classDef k fill:#0b1220,stroke:#2dd4bf,stroke-width:2px,color:#e2e8f0
    class ID,RE,IM,BR,PR,MG n
    class VA,DP,LV k
```

<table>
<tr><th width="18%">Stage</th><th>What has to be true to move on</th></tr>
<tr><td><b>Research</b></td><td>The problem is <i>measured</i>, not assumed. A reported "2-minute lag" was sampled nine times against the live feed before a line of code changed — which showed the provider was not the cause</td></tr>
<tr><td><b>Implement</b></td><td>A test exists that <b>fails against the previous commit</b>. A test that passes either way defends nothing</td></tr>
<tr><td><b>Verify</b></td><td>1,771 tests, <code>ruff</code>, and <code>npm run build</code> — <i>not</i> <code>tsc --noEmit</code>, which reports success on broken JSX</td></tr>
<tr><td><b>Deploy</b></td><td>The running server is asked which commit it serves. Mismatch fails the run</td></tr>
</table>

<br>

---

## 🔍 Market Intelligence

<div align="center">
<img src="docs/assets/elliott-wave.svg" alt="An Elliott Wave impulse drawing itself wave by wave, then the ABC correction, with each rule checked as it completes" width="100%">
</div>

<br>

<table>
<tr><td valign="top" width="50%">

### 🌊 Elliott Wave
[`src/analysis/elliott_wave/`](src/analysis/elliott_wave)

- ➜ [`impulse`](src/analysis/elliott_wave/impulse.py) · [`correction`](src/analysis/elliott_wave/correction.py) · [`diagonal`](src/analysis/elliott_wave/diagonal.py)
- ➜ [`triangle`](src/analysis/elliott_wave/triangle.py) · [`combination`](src/analysis/elliott_wave/combination.py)
- ➜ [`pivots`](src/analysis/elliott_wave/pivots.py) — swing detection feeding the search
- ➜ [`hierarchy`](src/analysis/elliott_wave/hierarchy.py) — nesting wave degrees
- ➜ [`validation`](src/analysis/elliott_wave/validation.py) — **the rules a count must satisfy**
- ➜ [`measurements`](src/analysis/elliott_wave/measurements.py) · [`momentum`](src/analysis/elliott_wave/momentum.py)
- ➜ [`pipeline`](src/analysis/elliott_wave/pipeline.py) — the pass that ties it together

</td><td valign="top" width="50%">

### 📐 Price structure
[`src/analysis/`](src/analysis)

- ➜ [`swing_identification`](src/analysis/swing_identification.py) · [`zigzag`](src/analysis/zigzag.py) — the skeleton of a trend
- ➜ [`chart_patterns`](src/analysis/chart_patterns.py) — triangles, wedges, head-and-shoulders
- ➜ [`candlestick_patterns`](src/analysis/candlestick_patterns.py) — single and multi-bar formations
- ➜ [`indicators`](src/analysis/indicators.py) — RSI, Stochastic, moving averages, VWAP
- ➜ [`regime`](src/analysis/regime.py) — trending, ranging or volatile

</td></tr>
</table>

> **`validation` is the module that matters most.** Without it, a pattern search finds
> a "wave count" in any random walk you hand it.

**VWAP the way a broker platform computes it.** Each bar carries its own
volume-weighted price, built from the minutes inside it, rather than `(H+L+C)/3`.
Measured on the same closed 30-minute bar:

| Selection | Source | VWAP |
|---|---|---|
| 30m alone | 30m | 7810.2336 |
| 1m + 30m | 1m | **7809.9279** ← matches the reference platform |

Same bar, two answers, decided by a checkbox — which is exactly the class of
non-determinism the shared aggregator exists to kill.

<br>

---

## 🧠 Strategy Engine

Five strategies ship, all behind one interface
([`base_strategy.py`](src/strategies/base_strategy.py)), so any of them drops into any
run without the engine knowing which it holds.

| | Strategy | The idea |
|---|---|---|
| 🔀 | [**`rsi_divergence`**](src/strategies/rsi_divergence.py) | Price makes a new extreme, RSI does not — momentum failing to confirm |
| ↩️ | [**`rsi_mean_reversion`**](src/strategies/rsi_mean_reversion.py) | Fade an exhausted move back toward the mean |
| 📈 | [**`ma_crossover`**](src/strategies/ma_crossover.py) | Fast and slow moving averages crossing |
| 🚀 | [**`breakout`**](src/strategies/breakout.py) | Range resolution on expanding volume |
| 🎛️ | [**`regime_adaptive`**](src/strategies/regime_adaptive.py) | Switches behaviour on the [regime classifier's](src/analysis/regime.py) reading |

> **Each timeframe gets its own strategy instance and its own paper broker.**
> Strategies are stateful — RSI divergence arms a setup on one bar and confirms it
> several bars later — so sharing one instance would let an hourly bar corrupt the
> one-minute strategy's pre-conditions and silently change its signals.

<br>

---

## ⚙️ Backtesting & Execution

```mermaid
flowchart LR
    D["📊 Bars"] ==> S["🧠 Strategy<br/>signal"]
    S ==> B["💰 Paper Broker"]
    B ==> F["🎯 Fill<br/><i>+ slippage<br/>+ commission</i>"]
    F ==> PL["📈 Position & P&L"]
    PL ==> M["📋 Metrics"]

    classDef n fill:#0b1220,stroke:#334155,stroke-width:1px,color:#94a3b8
    classDef h fill:#0b1220,stroke:#f59e0b,stroke-width:2px,color:#e2e8f0
    class D,S,PL,M n
    class B,F h
```

- ➜ **Fills are charged, not assumed** — commission per contract, slippage in ticks, prices rounded to the instrument's real increment
- ➜ **Contract specifications per instrument** — tick size, tick value and point value for ES, NQ, MES, CL and others, so P&L lands in real currency
- ➜ **Session-aware** — RTH, Globex (18:00–17:00) or 24-hour, with VWAP anchored to the session open rather than to midnight
- ➜ **Deterministic** — the same inputs produce the same output every time, which is what makes a rebuilt result comparable to the one it replaced

### One clock, eleven timeframes

The obvious implementation — keep N engines and step them all once per tick — does
**not** produce a synchronised view. `step()` advances one *bar*, and a bar is a
different amount of time on each timeframe: after 100 ticks a 1m pane has moved 100
minutes while a 1h pane has moved 100 hours.

So the clock is measured in **market time**. One tick advances time by exactly one
base bar; every other timeframe steps only when its next bar has *closed*. See
[`multi_replay.py`](src/backtesting/multi_replay.py).

<br>

---

## 📊 Dashboard

A React 19 single-page application over the FastAPI backend.

| Page | What it does |
|---|---|
| ⚡ [**Live Replay**](web/src/features/replay) | Multi-timeframe grid, consolidated tape, playback controls, live following |
| 📉 [**Backtest**](web/src/features/backtest) | Configure, run and read a scored result |
| 📤 [**Export Data**](web/src/features/export) | Pull bars out for use elsewhere |

- ➜ **Charts** — candles with VWAP, deviation bands, volume profile and wave overlays
- ➜ **Deviation colouring** — band values grouped by whole number, with disjoint palettes for upper and lower so the two can never be confused
- ➜ **Logic lives in [`web/src/lib`](web/src/lib)** — 279 tests run without a browser

<br>

---

## 🔌 API Reference

FastAPI, with interactive documentation at **`/docs`** while running.

| Area | Method | Endpoint | Purpose |
|---|---|---|---|
| Replay | `POST` | `/api/replay` | Create a session |
| Replay | `WS` | `/api/replay/ws/{id}` | Drive it bar by bar |
| Replay | `WS` | `↳ action: extend` | Pull bars that printed since |
| Backtest | `POST` | `/api/backtests` | Run and score a strategy |
| Market | `GET` | `/api/symbols` | Instruments and their specs |
| Market | `GET` | `/api/strategies` | Available strategies and parameters |
| Schwab | `GET` | `/api/schwab/status` | Auth state and token life |
| Export | `GET` | `/api/export/...` | CSV · XLSX · PDF · DOCX |
| Meta | `GET` | `/api/version` | Build commit — used by the deploy assertion |

See [`api/routers/`](api/routers) and the [API Guide](docs/API_GUIDE.md).

<br>

---

## 🛠 Technology Stack

<table>
<tr><td valign="top" width="33%">

### ⚙️ Backend
- **Python 3.12**
- FastAPI · Uvicorn
- pandas · numpy
- pandas-ta
- Pydantic
- pytest · ruff · mypy · bandit

</td><td valign="top" width="33%">

### 🖥 Frontend
- **React 19** · TypeScript
- Vite
- Tailwind CSS
- shadcn/ui · Radix
- Recharts
- Vitest · oxlint

</td><td valign="top" width="33%">

### ☁️ Infrastructure
- Docker · Compose
- GitHub Actions
- AWS EC2
- GitHub App auth
- Nginx

</td></tr>
</table>
<br>

---

## 📂 Folder Structure

> **Every name below is a link.** Click a folder to open it, or a file to read
> it. Each directory also carries its own README explaining what it holds and why.

<pre>
<a href=".">trading-platform</a>
|------------▶  <a href="src">src/</a>   <i>the engine — no HTTP, no React, no framework</i>  <b>61</b>
|               |------------▶  <a href="src/analysis">analysis/</a>   <i>reading the market</i>  <b>22</b>
|               |               |- - - ▶  <a href="src/analysis/candlestick_patterns.py">candlestick_patterns.py</a>
|               |               |- - - ▶  <a href="src/analysis/chart_patterns.py">chart_patterns.py</a>
|               |               |- - - ▶  <a href="src/analysis/indicators.py">indicators.py</a>
|               |               |- - - ▶  <a href="src/analysis/regime.py">regime.py</a>
|               |               |- - - ▶  <a href="src/analysis/swing_identification.py">swing_identification.py</a>
|               |               └- - - ▶  <a href="src/analysis/zigzag.py">zigzag.py</a>
|
|               |               └------------▶  <a href="src/analysis/elliott_wave">elliott_wave/</a>   <i>wave detection, rules and hierarchy</i>  <b>14</b>
|               |                               |- - - ▶  <a href="src/analysis/elliott_wave/combination.py">combination.py</a>
|               |                               |- - - ▶  <a href="src/analysis/elliott_wave/correction.py">correction.py</a>
|               |                               |- - - ▶  <a href="src/analysis/elliott_wave/diagonal.py">diagonal.py</a>
|               |                               |- - - ▶  <a href="src/analysis/elliott_wave/hierarchy.py">hierarchy.py</a>
|               |                               |- - - ▶  <a href="src/analysis/elliott_wave/impulse.py">impulse.py</a>
|               |                               |- - - ▶  <a href="src/analysis/elliott_wave/measurements.py">measurements.py</a>
|               |                               |- - - ▶  <a href="src/analysis/elliott_wave/models.py">models.py</a>
|               |                               |- - - ▶  <a href="src/analysis/elliott_wave/momentum.py">momentum.py</a>
|               |                               |- - - ▶  <a href="src/analysis/elliott_wave/pipeline.py">pipeline.py</a>
|               |                               |- - - ▶  <a href="src/analysis/elliott_wave/pivots.py">pivots.py</a>
|               |                               |- - - ▶  <a href="src/analysis/elliott_wave/triangle.py">triangle.py</a>
|               |                               └- - - ▶  <a href="src/analysis/elliott_wave/validation.py">validation.py</a>
|
|               |------------▶  <a href="src/strategies">strategies/</a>   <i>turning a reading into a decision</i>  <b>8</b>
|               |               |- - - ▶  <a href="src/strategies/base_strategy.py">base_strategy.py</a>
|               |               |- - - ▶  <a href="src/strategies/breakout.py">breakout.py</a>
|               |               |- - - ▶  <a href="src/strategies/ma_crossover.py">ma_crossover.py</a>
|               |               |- - - ▶  <a href="src/strategies/regime_adaptive.py">regime_adaptive.py</a>
|               |               |- - - ▶  <a href="src/strategies/rsi_divergence.py">rsi_divergence.py</a>
|               |               └- - - ▶  <a href="src/strategies/rsi_mean_reversion.py">rsi_mean_reversion.py</a>
|
|               |------------▶  <a href="src/backtesting">backtesting/</a>   <i>replay engine and the shared market clock</i>  <b>8</b>
|               |               |- - - ▶  <a href="src/backtesting/engine.py">engine.py</a>
|               |               |- - - ▶  <a href="src/backtesting/metrics.py">metrics.py</a>
|               |               |- - - ▶  <a href="src/backtesting/multi_replay.py">multi_replay.py</a>
|               |               |- - - ▶  <a href="src/backtesting/replay_engine.py">replay_engine.py</a>
|               |               |- - - ▶  <a href="src/backtesting/results.py">results.py</a>
|               |               └- - - ▶  <a href="src/backtesting/trade_quality.py">trade_quality.py</a>
|
|               |------------▶  <a href="src/broker">broker/</a>   <i>what a fill actually costs</i>  <b>5</b>
|               |               |- - - ▶  <a href="src/broker/base_broker.py">base_broker.py</a>
|               |               |- - - ▶  <a href="src/broker/paper_broker.py">paper_broker.py</a>
|               |               └- - - ▶  <a href="src/broker/rithmic_broker.py">rithmic_broker.py</a>
|
|               |------------▶  <a href="src/data">data/</a>   <i>providers, and one shared resampler</i>  <b>12</b>
|               |               |- - - ▶  <a href="src/data/base_provider.py">base_provider.py</a>
|               |               |- - - ▶  <a href="src/data/csv_provider.py">csv_provider.py</a>
|               |               |- - - ▶  <a href="src/data/external_csv_provider.py">external_csv_provider.py</a>
|               |               |- - - ▶  <a href="src/data/resample.py">resample.py</a>
|               |               |- - - ▶  <a href="src/data/rithmic_provider.py">rithmic_provider.py</a>
|               |               |- - - ▶  <a href="src/data/sample_data.py">sample_data.py</a>
|               |               └- - - ▶  <a href="src/data/schwab_provider.py">schwab_provider.py</a>
|
|               └------------▶  <a href="src/live">live/</a>   <i>live loop (experimental)</i>  <b>3</b>
|                               └- - - ▶  <a href="src/live/trader.py">trader.py</a>
|------------▶  <a href="api">api/</a>   <i>the FastAPI service</i>  <b>32</b>
|               |------------▶  <a href="api/routers">routers/</a>   <i>REST endpoints and the replay socket</i>  <b>8</b>
|               |               |- - - ▶  <a href="api/routers/backtests.py">backtests.py</a>
|               |               |- - - ▶  <a href="api/routers/data_export.py">data_export.py</a>
|               |               |- - - ▶  <a href="api/routers/meta.py">meta.py</a>
|               |               |- - - ▶  <a href="api/routers/optimize.py">optimize.py</a>
|               |               |- - - ▶  <a href="api/routers/replay.py">replay.py</a>
|               |               └- - - ▶  <a href="api/routers/schwab.py">schwab.py</a>
|
|               |------------▶  <a href="api/schemas">schemas/</a>   <i>request and response models</i>  <b>7</b>
|               |               |- - - ▶  <a href="api/schemas/backtest.py">backtest.py</a>
|               |               |- - - ▶  <a href="api/schemas/elliott_wave.py">elliott_wave.py</a>
|               |               |- - - ▶  <a href="api/schemas/optimize.py">optimize.py</a>
|               |               |- - - ▶  <a href="api/schemas/replay.py">replay.py</a>
|               |               └- - - ▶  <a href="api/schemas/schwab.py">schwab.py</a>
|
|               |------------▶  <a href="api/report">report/</a>   <i>charts rendered on the server</i>  <b>4</b>
|               |               |- - - ▶  <a href="api/report/charts.py">charts.py</a>
|               |               └- - - ▶  <a href="api/report/report.py">report.py</a>
|
|               └------------▶  <a href="api/export">export/</a>   <i>CSV · XLSX · PDF · DOCX</i>  <b>4</b>
|                               |- - - ▶  <a href="api/export/formats.py">formats.py</a>
|                               └- - - ▶  <a href="api/export/report_export.py">report_export.py</a>
|------------▶  <a href="web">web/</a>   <i>the React dashboard</i>  <b>92</b>
|               |------------▶  <a href="web/src/features">features/</a>   <i>replay, backtest and export pages</i>  <b>5</b>
|
|               |------------▶  <a href="web/src/components">components/</a>   <i>shared UI</i>  <b>34</b>
|
|               └------------▶  <a href="web/src/lib">lib/</a>   <i>pure logic, unit-tested away from React</i>  <b>31</b>
|                               |- - - ▶  <a href="web/src/lib/api.ts">api.ts</a>
|                               |- - - ▶  <a href="web/src/lib/bandAgreement.test.ts">bandAgreement.test.ts</a>
|                               |- - - ▶  <a href="web/src/lib/bandAgreement.ts">bandAgreement.ts</a>
|                               |- - - ▶  <a href="web/src/lib/chartAxis.test.ts">chartAxis.test.ts</a>
|                               |- - - ▶  <a href="web/src/lib/clock.test.ts">clock.test.ts</a>
|                               |- - - ▶  <a href="web/src/lib/clock.ts">clock.ts</a>
|                               |- - - ▶  <a href="web/src/lib/dayRange.test.ts">dayRange.test.ts</a>
|                               |- - - ▶  <a href="web/src/lib/dayRange.ts">dayRange.ts</a>
|                               └- - - ▶  <i>+22 more</i>
|------------▶  <a href="tests">tests/</a>   <i>what every number on screen rests on</i>  <b>26</b>
|               |- - - ▶  <a href="tests/test_api_provider_errors.py">test_api_provider_errors.py</a>
|               |- - - ▶  <a href="tests/test_engine.py">test_engine.py</a>
|               |- - - ▶  <a href="tests/test_follow_live_matrix.py">test_follow_live_matrix.py</a>
|               |- - - ▶  <a href="tests/test_indicator_correctness.py">test_indicator_correctness.py</a>
|               |- - - ▶  <a href="tests/test_multi_replay.py">test_multi_replay.py</a>
|               |- - - ▶  <a href="tests/test_provider_timeframes.py">test_provider_timeframes.py</a>
|               └- - - ▶  <i>+7 more</i>
|------------▶  <a href="docs">docs/</a>   <i>architecture, rules and guides</i>  <b>22</b>
|               |- - - ▶  <a href="docs/API_GUIDE.md">API_GUIDE.md</a>
|               |- - - ▶  <a href="docs/ARCHITECTURE.md">ARCHITECTURE.md</a>
|               |- - - ▶  <a href="docs/CONFIGURATION.md">CONFIGURATION.md</a>
|               |- - - ▶  <a href="docs/DEVELOPER_GUIDE.md">DEVELOPER_GUIDE.md</a>
|               |- - - ▶  <a href="docs/ELLIOTT_WAVE_ARCHITECTURE.md">ELLIOTT_WAVE_ARCHITECTURE.md</a>
|               |- - - ▶  <a href="docs/ELLIOTT_WAVE_IMPLEMENTATION.md">ELLIOTT_WAVE_IMPLEMENTATION.md</a>
|               └- - - ▶  <i>+10 more</i>
|------------▶  <a href="config">config/</a>   <i>settings and credential templates</i>  <b>3</b>
|               |- - - ▶  <a href="config/credentials.yaml.example">credentials.yaml.example</a>
|               └- - - ▶  <a href="config/settings.yaml">settings.yaml</a>
|------------▶  <a href="data">data/</a>   <i>bundled samples, and where downloads land</i>  <b>18</b>
|------------▶  <a href="scripts">scripts/</a>   <i>CLI entry points and the local launcher</i>  <b>5</b>
|               |- - - ▶  <a href="scripts/download_rithmic_data.py">download_rithmic_data.py</a>
|               |- - - ▶  <a href="scripts/generate_data.py">generate_data.py</a>
|               |- - - ▶  <a href="scripts/run-autotrader.cmd">run-autotrader.cmd</a>
|               └- - - ▶  <a href="scripts/run_backtest.py">run_backtest.py</a>
|------------▶  <a href="reports">reports/</a>   <i>generated output</i>  <b>3</b>
└------------▶  <a href="legacy">legacy/</a>   <i>archived predecessor repositories</i>  <b>451</b>
                └------------▶  <a href=".github/workflows">workflows/</a>   <i>CI and deploy</i>  <b>3</b>
                                |- - - ▶  <a href=".github/workflows/ci.yml">ci.yml</a>
                                |- - - ▶  <a href=".github/workflows/deploy.yml">deploy.yml</a>
                                └- - - ▶  <a href=".github/workflows/probe-creds.yml">probe-creds.yml</a>
</pre>

<br>

---

## 🚀 Getting Started

### ◆ Prerequisites

| | |
|---|---|
| 🐍 **Python 3.12** | **Not 3.14** — `pandas_ta` breaks on it and produces a test failure that looks real but is not |
| 🟢 **Node.js 20+** | For the dashboard |
| 🔑 **Schwab credentials** | Only for live data. CSV and synthetic sources work without any |

### ◆ 1 · Clone and install

```bash
git clone https://github.com/wealthwise-advisors/trading-platform.git
cd trading-platform

py -3.12 -m pip install -r requirements.txt
cd web && npm install && cd ..
```

### ◆ 2 · Configure

```bash
cp config/credentials.yaml.example config/credentials.yaml
```

Fill in your Schwab app key and secret.

> [!CAUTION]
> **`config/credentials.yaml` and `config/schwab_tokens.json` are gitignored and must
> never be committed.** Five predecessor repositories hardcoded live credentials into
> source files — see [`legacy/REDACTIONS.md`](legacy/REDACTIONS.md) for what that cost.

### ◆ 3 · Run it

```bash
# API  →  http://127.0.0.1:8000
py -3.12 -m uvicorn api.main:app --reload

# Web  →  http://localhost:5173
cd web && npm run dev
```

On Windows, [`scripts/run-autotrader.cmd`](scripts/run-autotrader.cmd) does both —
frees the ports first and pins the right Python.

> [!TIP]
> Open **`http://localhost:5173`**, not `127.0.0.1:5173`. Vite binds to IPv6 only, so
> the numeric address is refused — that "site can't be reached" error is the address,
> not a broken app.

### ◆ 4 · First run

<table>
<tr><td width="6%" align="center"><b>1</b></td><td><b>Data Source</b> → <i>Live Data (Schwab)</i></td></tr>
<tr><td align="center"><b>2</b></td><td><b>Start</b> and <b>End</b> → today's date, both</td></tr>
<tr><td align="center"><b>3</b></td><td>Tick <b>1m</b> under Timeframes</td></tr>
<tr><td align="center"><b>4</b></td><td><b>⬇ Load Data</b> → <b>▶ Play</b></td></tr>
<tr><td align="center"><b>5</b></td><td><b>Touch nothing else.</b> At 100% the tape starts following the live market on its own</td></tr>
</table>

<br>

---

## 🧪 Testing & Quality

```bash
py -3.12 -m pytest              # 1,492 Python tests
cd web && npm test              #   279 web tests
cd web && npm run build         # tsc -b — the real typecheck
py -3.12 -m ruff check .        # lint
```

<div align="center">

| Suite | Count | Covers |
|:---|---:|:---|
| 🐍 **Python** | **1,492** | engine, analysis, API, providers, replay |
| ⚛️ **Web** | **279** | pure logic in [`web/src/lib`](web/src/lib) |
| **Total** | **1,771** | |

</div>

### ◆ What the tests defend

- ➜ **Follow-live across every timeframe** — all eleven, every position within a bar, seven combinations, five dates including both DST switches and a leap day
- ➜ **Bar aggregation** — one aggregator, session-anchored, so no two paths can disagree about what a bar is
- ➜ **Determinism** — a session grown bar by bar must be byte-identical to one handed all the data at once
- ➜ **Elliott Wave rules** — a count that breaks a rule must be rejected
- ➜ **Error messages** — a bad request must name the field to change, not return a 500

### ◆ A test earns its place by being able to fail

The [follow-live matrix](tests/test_follow_live_matrix.py) was written after a bug
that only appeared on timeframes coarser than 1m. **67 of its 107 cases fail against
the commit that shipped that bug** — which is the property that makes it worth
running. A test that passes either way defends nothing.

> [!WARNING]
> `npx tsc --noEmit` reports **success on broken JSX**, because the root tsconfig is a
> solution file with project references only. **`npm run build` (`tsc -b`) is the real
> typecheck.**

<br>

---

## 📦 Deployment

```mermaid
flowchart LR
    PR["🔀 Pull Request"] ==> CI["🧪 CI<br/><i>6 checks</i>"]
    CI ==> MG["🎯 Merge to master"]
    MG ==> DP["🚀 Deploy workflow"]
    DP ==> EC["☁️ AWS EC2<br/><i>Docker Compose</i>"]
    EC ==> AS{"Served commit<br/>== github.sha ?"}
    AS ==>|yes| OK["✅ Deployment confirmed"]
    AS ==>|no| FA["❌ Fail the run"]

    classDef n fill:#0b1220,stroke:#334155,stroke-width:1px,color:#94a3b8
    classDef g fill:#0b1220,stroke:#22c55e,stroke-width:2px,color:#e2e8f0
    classDef r fill:#0b1220,stroke:#ef4444,stroke-width:2px,color:#e2e8f0
    class PR,CI,MG,DP,EC,AS n
    class OK g
    class FA r
```

Every deploy asks the running server which commit it is serving and **fails the run
unless it matches**. A deploy that quietly leaves the old build running is the exact
failure this exists to catch.

| | |
|---|---|
| 🔐 **Auth** | GitHub App installation token, minted per run and revoked when the job ends |
| 🛡️ **Firewall** | The SSH rule is opened for the run and **always** revoked, even if the run fails |
| 🔑 **Tokens** | Schwab tokens follow **newer-wins**, so a container's own refresh is never clobbered by a redeploy |
| ✅ **Proof** | `CONFIRMED: port 80 is served by <sha>` appears in the log, or the run goes red |

<br>

---

## 🗂 Repository Ecosystem

```mermaid
flowchart LR
    HUB(["<b>trading-platform</b><br/>the platform · legacy archive"])
    DATA(["<b>data</b><br/>market history · Git LFS"])
    HUB ==>|reads full history from| DATA

    classDef hub  fill:#0b1220,stroke:#2dd4bf,stroke-width:3px,color:#e2e8f0
    classDef node fill:#0b1220,stroke:#334155,stroke-width:2px,color:#94a3b8
    class HUB hub
    class DATA node
```

| Repository | Purpose | |
|---|---|---|
| **trading-platform** | This repository — the platform, plus [`legacy/`](legacy) | *you are here* |
| **data** | Full market history in Git LFS, including an **18-year 1-minute ES series** too large for an ordinary repository | [Open ↗](https://github.com/wealthwise-advisors/data) |

**Five predecessor repositories were consolidated into [`legacy/`](legacy) and
retired** — `trading-strategy`, `trading-web`, `Wealthwise`, `backtest` and
`Project_work`. Their 442 files live on here; hardcoded credentials were stripped on
the way in and recorded in [`legacy/REDACTIONS.md`](legacy/REDACTIONS.md).

`legacy/` is reference only — excluded from linting, from the test suite, and from
every Docker image.

<br>

---

## 📚 Documentation

<table>
<tr><td valign="top" width="50%">

### ◆ Getting oriented
- 📗 [Quickstart](docs/QUICKSTART.md)
- 📘 [Installation](docs/INSTALLATION.md)
- 📙 [Configuration](docs/CONFIGURATION.md)
- ❓ [FAQ](docs/FAQ.md)
- 🔧 [Troubleshooting](docs/TROUBLESHOOTING.md)

</td><td valign="top" width="50%">

### ◆ Going deeper
- 🏛 [Architecture](docs/ARCHITECTURE.md)
- 👩‍💻 [Developer Guide](docs/DEVELOPER_GUIDE.md)
- 🔌 [API Guide](docs/API_GUIDE.md)
- 🌊 Elliott Wave — [rules](docs/ELLIOTT_WAVE_RULES.md) · [architecture](docs/ELLIOTT_WAVE_ARCHITECTURE.md) · [implementation](docs/ELLIOTT_WAVE_IMPLEMENTATION.md) · [SRS](docs/ELLIOTT_WAVE_SRS.md)
- 🔒 [Security Audit](docs/SECURITY_AUDIT.md)
- 📋 [Release Notes](docs/RELEASE_NOTES.md) · [Audit](docs/RELEASE_AUDIT.md)

</td></tr>
</table>

Every directory also has its own README — [`src/`](src/README.md) ·
[`api/`](api/README.md) · [`web/src/lib/`](web/src/lib/README.md) ·
[`tests/`](tests/README.md) · [`config/`](config/README.md) and the rest.

<br>

---

## ⚠️ Disclaimer

**For research and education. Not investment advice.**

Futures trading carries substantial risk of loss and is not suitable for every
investor. Backtested results are hypothetical: they benefit from hindsight, cannot
account for every market condition, and **do not predict future performance**.

Nothing here should be traded with real money without independent validation and your
own understanding of the risk.

<br>

---

## 📄 License

Proprietary — © **WealthWise Advisors**. All rights reserved. See [LICENSE](LICENSE).

<br>

<div align="center">

### Built for research that has to hold up.

<sub>If a number is on the screen, something in <a href="tests">tests/</a> defends it.</sub>

<br><br>

<sub><a href="#-table-of-contents">↑ Back to top</a></sub>

</div>
