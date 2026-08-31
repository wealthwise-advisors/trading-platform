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

## 3. Run the test suite

```bash
pytest tests/ -v
```

## Where to go next

- Writing your own strategy: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
- How the platform is layered: [Design Document.md](Design%20Document.md)
- Setting up Schwab/Rithmic for real data: [CONFIGURATION.md](CONFIGURATION.md)
- Something not working: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
