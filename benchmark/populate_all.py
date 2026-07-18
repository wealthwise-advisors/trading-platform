"""Independent Industry Benchmark -- Task 9 Improvement orchestrator.
Rebuilds benchmark.db from scratch against the extended schema.sql (new
columns/CHECK constraints -- CREATE TABLE IF NOT EXISTS would silently
keep the OLD Task 9 schema otherwise) and populates every tier:

  1. reference_sources     (9 rows: Task 9's 7 + tv_rk_chaarts + schwab_real_market)
  2. rule_comparisons       (Task 9's rule-level Pine-script comparison, unchanged)
  3. synthetic_archetype    (104 cases: 13 archetypes x 2 scales x 2 mirrors x 2 seeds)
  4. real_market_regime     (369 cases: real ES/NQ/SPY/GC/CL x 5m/15m/1h/4h/1d,
                             objectively regime-classified)
  5. benchmark_comparisons  (synthetic_archetype only -- see compare.py docstring)
  6. reproducibility_checks (engine determinism sample across both categories)

Nothing under src/ or api/ is touched by this script.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.db import init_db, connect, DB_PATH
from benchmark import seed_sources, seed_rule_comparisons, pipeline, real_regime, compare, reproducibility


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"removed old {DB_PATH.name} (rebuilding against extended schema)")

    init_db()
    print("schema initialized")

    seed_sources.seed()
    seed_rule_comparisons.seed()

    t0 = time.time()
    with connect() as conn:
        n_synth = pipeline.populate_synthetic(conn, verbose=False)
        print(f"{n_synth} synthetic_archetype cases populated ({time.time()-t0:.1f}s)")

    t0 = time.time()
    with connect() as conn:
        n_real = real_regime.populate_real_regime(conn)
        print(f"{n_real} real_market_regime cases populated ({time.time()-t0:.1f}s)")

    t0 = time.time()
    with connect() as conn:
        n_cmp = compare.run_all_comparisons(conn)
        print(f"{n_cmp} comparisons computed ({time.time()-t0:.1f}s)")

    t0 = time.time()
    with connect() as conn:
        n_repro = reproducibility.run_reproducibility_checks(conn, verbose=False)
        print(f"{n_repro} reproducibility checks recorded ({time.time()-t0:.1f}s)")

    print(f"\ntotal benchmark cases: {n_synth + n_real}")


if __name__ == "__main__":
    main()
