# FAQ

**Is the Elliott Wave engine an AI/LLM feature?**
No. It's deterministic, rule-based Python — fractal swing detection,
hard-rule validation (Wave 2/3/4 rules), Fibonacci confidence scoring, and
dynamic-programming candidate selection. No model calls, no external API,
fully reproducible (see the 100% determinism result in
`benchmark/TASK9_IMPROVEMENT_REPORT.md`).

**Can I trust the engine's wave count as "the" correct answer?**
No — and the engine doesn't claim to. Elliott Wave counting is inherently
somewhat subjective even among human experts; the engine surfaces
alternates, confidence scores, and rule warnings rather than a single
unchallengeable answer. The independent benchmark measured genuine
agreement with textbook definitions at ~30% exact top-level match, with
most disagreements traced to legitimate "multiple valid interpretations"
competition rather than detection errors — read
`benchmark/TASK9_IMPROVEMENT_REPORT.md` section 4 before treating any
single count as ground truth.

**Does this place real trades?**
Not in v1.0.0. `src/live/trader.py` and `src/broker/rithmic_broker.py` are
an intentional stub. Backtesting (`PaperBroker`, simulated fills) and
bar-by-bar replay are fully implemented; live order placement is not
wired to a real broker.

**Why is there both an `engine_structure_type` and a `direct_detection` result?**
They answer different questions — see [ARCHITECTURE.md](ARCHITECTURE.md).
`direct_detection` asks "does this specific pattern's own detector confirm
it at this exact span" (detection logic, isolated). `engine_structure_type`
asks "did it win the whole chart's top-level competition against every
other candidate structure" (chart-wide prioritization). A diagonal or
triple-three can pass the first and lose the second — this is by design,
not a bug, and is one of the benchmark's most consistent findings (100%
reproducible across all 16 diagonal test variants).

**Why does `elliott benchmark` take ~40 seconds?**
It rebuilds the full 473-case benchmark from scratch (104 synthetic
archetype variants + running the engine on 369 real market windows across
5 symbols × 5 timeframes) rather than just reading cached numbers. Use
`elliott benchmark --report-only` to summarize the existing
`benchmark/benchmark.db` instantly instead.

**Why isn't the whole repo under one `src/autotrader/` package?**
It predates this packaging pass and every existing import across `src/`,
`api/`, `tests/`, `benchmark/`, and `validation/` (dozens of files) already
uses the current flat layout (`from src.analysis import ...`,
`from api import ...`, etc.). Restructuring into a nested package would
touch every one of those imports for a purely cosmetic gain — out of scope
for a release audit whose job is to certify the existing structure, not
redesign it. `pyproject.toml` packages the existing top-level directories
as-is.

**Is this open source?**
No — proprietary, all rights reserved. See [LICENSE](../LICENSE).

**Where do I report a bug or ask for a feature?**
See [CONTRIBUTING.md](../CONTRIBUTING.md).
