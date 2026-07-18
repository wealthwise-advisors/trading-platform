# Quick Start

## 1. Install

```bash
pip install -e ".[dev]"
```

See [INSTALLATION.md](INSTALLATION.md) if this fails.

## 2. Run your first backtest (no credentials needed)

```bash
uvicorn api.main:app --reload --port 8000
```

In a second terminal:

```bash
cd web
npm install
npm run dev
```

Open http://localhost:5173, leave **Data Source** on **Synthetic Data**,
pick a strategy (e.g. **MA Crossover**), and click **Run Backtest**. You
should see an equity curve, trade log, and candlestick chart within a
couple seconds.

## 3. Run your first Elliott Wave analysis

The engine works standalone from any OHLC CSV — you don't need the API or
frontend running for this.

```bash
elliott analyze validation/charts/chart-0073e04da895.csv
```

```
Elliott Wave analysis: validation/charts/chart-0073e04da895.csv (60 bars)

  [primary]  trend=downtrend  swings=8  bias=short
      wave labels=3  alternates=0  warnings=['No valid impulse structure.']
  [minor]  trend=range / transition  swings=13  bias=neutral
      wave labels=0  alternates=0  warnings=[]
```

Export the full result:

```bash
elliott export validation/charts/chart-0073e04da895.csv --format json
```

To analyze your own data, any CSV with `open,high,low,close` columns
works (a `timestamp` and `volume` column are fine too, just unused by the
engine itself).

## 4. Run the regression suite

```bash
elliott validate
```

56 tests covering every Elliott Wave pattern type (impulses, all
correction variants, triangles, complex corrections, diagonals), prior
bugfix regressions, performance, determinism, and API behavior. Should
finish in a few seconds and report `56 passed`.

## 5. Look at the industry benchmark

```bash
elliott benchmark --report-only
```

Summarizes the existing 473-case benchmark (104 synthetic archetype
variants + 369 real-market robustness cases) without re-running it. Drop
`--report-only` to rebuild it from scratch (~40 seconds). Full
methodology: [benchmark/TASK9_IMPROVEMENT_REPORT.md](../benchmark/TASK9_IMPROVEMENT_REPORT.md).

## Where to go next

- Writing your own strategy: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
- How the Elliott Wave engine is layered: [ARCHITECTURE.md](ARCHITECTURE.md)
- Setting up Schwab/Rithmic for real data: [CONFIGURATION.md](CONFIGURATION.md)
- Something not working: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
