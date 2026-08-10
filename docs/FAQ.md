# FAQ

**Does this place real trades?**
Not in v1.0.0. `src/live/trader.py` and `src/broker/rithmic_broker.py` are
an intentional stub. Backtesting (`PaperBroker`, simulated fills) and
bar-by-bar replay are fully implemented; live order placement is not
wired to a real broker.

**Why isn't the whole repo under one `src/autotrader/` package?**
It predates this packaging pass and every existing import across `src/`,
`api/`, and `tests/` (dozens of files) already uses the current flat
layout (`from src.analysis import ...`, `from api import ...`, etc.).
Restructuring into a nested package would touch every one of those imports
for a purely cosmetic gain — out of scope for a release audit whose job is
to certify the existing structure, not redesign it. `pyproject.toml`
packages the existing top-level directories as-is.

**Is this open source?**
No — proprietary, all rights reserved. See [LICENSE](../LICENSE).

**Where do I report a bug or ask for a feature?**
See [CONTRIBUTING.md](../CONTRIBUTING.md).
