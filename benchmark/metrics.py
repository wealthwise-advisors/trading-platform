"""Independent Industry Benchmark -- metrics (Task 9 requirement 5;
extended by Task 9 Improvement requirements 1, 3, 5, 6): agreement %,
precision, recall, F1, Cohen's Kappa, confusion matrix, confidence
intervals, per-agreement-level breakdown, regime robustness, and
reproducibility summaries.

Accuracy metrics (agreement/precision/recall/kappa/confusion matrix) are
computed ONLY over case_category='synthetic_archetype' rows -- the only
category with a genuine, verifiable expected_structure_type (see
reference_sources for why real-market data has no independent reference
count). Regime/reproducibility metrics below cover BOTH categories, kept
in clearly separate functions so the two question types ("does the engine
agree with a reference" vs "does the engine behave robustly/
deterministically") are never blended into one number.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import math
import sqlite3
from collections import Counter

from benchmark.db import connect, fetch_all


def wilson_score_interval(successes: int, n: int, z: float = 1.96) -> tuple:
    """Wilson score interval -- more reliable than the naive normal
    approximation at small/moderate n (exactly the regime this benchmark's
    synthetic-case counts fall into), and never produces an out-of-[0,1]
    bound the way the naive interval can. z=1.96 -> ~95% confidence."""
    if n == 0:
        return (None, None)
    p = successes / n
    denom = 1 + z ** 2 / n
    center = p + z ** 2 / (2 * n)
    spread = z * math.sqrt((p * (1 - p) + z ** 2 / (4 * n)) / n)
    lower = (center - spread) / denom
    upper = (center + spread) / denom
    return (round(max(0.0, lower), 4), round(min(1.0, upper), 4))


def _rows(conn: sqlite3.Connection) -> list[dict]:
    return fetch_all(
        conn,
        "SELECT c.expected_structure_type as expected, r.engine_structure_type as engine, "
        "cmp.primary_agreement as agree, cmp.agreement_level as agreement_level, "
        "cmp.recommendation as recommendation, "
        "cmp.triangle_agreement as triangle_agree, cmp.diagonal_agreement as diagonal_agree, "
        "cmp.correction_agreement as correction_agree "
        "FROM benchmark_charts c JOIN benchmark_runs r ON r.chart_id = c.chart_id "
        "JOIN benchmark_comparisons cmp ON cmp.run_id = r.run_id "
        "WHERE c.case_category = 'synthetic_archetype'",
    )


def agreement_rate(conn: sqlite3.Connection) -> dict:
    rows = _rows(conn)
    n = len(rows)
    agree = sum(r["agree"] for r in rows)
    by_recommendation = Counter(r["recommendation"] for r in rows)
    by_agreement_level = Counter(r["agreement_level"] for r in rows)
    ci = wilson_score_interval(agree, n) if n else (None, None)
    return {
        "n": n, "primary_agreement_pct": round(agree / n, 4) if n else None,
        "primary_agreement_ci_95": {"lower": ci[0], "upper": ci[1]},
        "by_recommendation": dict(by_recommendation),
        "by_agreement_level": dict(by_agreement_level),
    }


def dimension_agreement(conn: sqlite3.Connection) -> dict:
    rows = _rows(conn)
    out = {}
    for dim, key in [("triangle_agreement", "triangle_agree"), ("diagonal_agreement", "diagonal_agree"),
                     ("correction_agreement", "correction_agree")]:
        applicable = [r[key] for r in rows if r[key] is not None]
        out[dim] = {"n_applicable": len(applicable), "agreement_pct": round(sum(applicable) / len(applicable), 4) if applicable else None}
    return out


def confusion_matrix(conn: sqlite3.Connection) -> dict:
    rows = _rows(conn)
    labels = sorted(set(r["expected"] for r in rows) | set(r["engine"] for r in rows))
    matrix = {e: {a: 0 for a in labels} for e in labels}
    for r in rows:
        matrix[r["expected"]][r["engine"]] += 1
    return {"labels": labels, "matrix": matrix}


def precision_recall_f1_per_class(conn: sqlite3.Connection) -> dict:
    """Multi-class precision/recall/F1, one-vs-rest per structure type."""
    rows = _rows(conn)
    labels = sorted(set(r["expected"] for r in rows) | set(r["engine"] for r in rows))
    out = {}
    for label in labels:
        tp = sum(1 for r in rows if r["expected"] == label and r["engine"] == label)
        fp = sum(1 for r in rows if r["expected"] != label and r["engine"] == label)
        fn = sum(1 for r in rows if r["expected"] == label and r["engine"] != label)
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (2 * precision * recall / (precision + recall)) if (precision and recall and (precision + recall)) else None
        out[label] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
        }
    return out


def cohens_kappa(conn: sqlite3.Connection) -> dict:
    """Cohen's Kappa between 'expected' (reference) and 'engine' (this
    engine's top-level classification) as two raters over the same fixed
    label set -- measures agreement beyond what chance alone would produce.
    """
    rows = _rows(conn)
    n = len(rows)
    if n == 0:
        return {"kappa": None, "n": 0}
    labels = sorted(set(r["expected"] for r in rows) | set(r["engine"] for r in rows))
    observed_agreement = sum(1 for r in rows if r["expected"] == r["engine"]) / n

    expected_counts = Counter(r["expected"] for r in rows)
    engine_counts = Counter(r["engine"] for r in rows)
    chance_agreement = sum((expected_counts.get(l, 0) / n) * (engine_counts.get(l, 0) / n) for l in labels)

    if chance_agreement >= 1.0:
        kappa = None   # degenerate -- no variance to measure agreement against
    else:
        kappa = (observed_agreement - chance_agreement) / (1 - chance_agreement)

    return {
        "kappa": round(kappa, 4) if kappa is not None else None,
        "observed_agreement": round(observed_agreement, 4),
        "chance_agreement": round(chance_agreement, 4),
        "n": n,
        "note": (f"n={n} synthetic archetype variants (up from 13 in Task 9). Still all derived, via "
                "documented scale/mirror transforms, from 13 independently-sourced textbook "
                "definitions rather than 104 independently-labeled real charts -- Kappa here is "
                "more statistically stable than Task 9's n=13 estimate (see the 95% CI on the "
                "agreement rate), but the underlying source diversity has not grown 8x, only the "
                "transform coverage has. Treat as a methodology-validated estimate, not equivalent "
                "to 104 independently-sourced expert-labelled charts."),
    }


def rule_comparison_summary(conn: sqlite3.Connection) -> list:
    return fetch_all(conn, "SELECT * FROM rule_comparisons")


def dataset_summary(conn: sqlite3.Connection) -> dict:
    """Task 9 Improvement requirement 7: dataset + source breakdown."""
    by_category = fetch_all(conn, "SELECT case_category, COUNT(*) n FROM benchmark_charts GROUP BY case_category")
    by_source = fetch_all(
        conn,
        "SELECT s.name, s.access_status, COUNT(c.chart_id) n FROM reference_sources s "
        "LEFT JOIN benchmark_charts c ON c.source_id = s.source_id GROUP BY s.source_id ORDER BY s.category, s.name",
    )
    by_symbol_timeframe = fetch_all(
        conn,
        "SELECT symbol, timeframe, COUNT(*) n FROM benchmark_charts WHERE case_category = 'real_market_regime' "
        "GROUP BY symbol, timeframe ORDER BY symbol, timeframe",
    )
    by_regime = fetch_all(
        conn,
        "SELECT regime_trend, regime_volatility, COUNT(*) n FROM benchmark_charts "
        "WHERE case_category = 'real_market_regime' GROUP BY regime_trend, regime_volatility "
        "ORDER BY regime_trend, regime_volatility",
    )
    total = fetch_all(conn, "SELECT COUNT(*) n FROM benchmark_charts")[0]["n"]
    return {
        "total_cases": total,
        "by_category": {r["case_category"]: r["n"] for r in by_category},
        "by_source": by_source,
        "by_symbol_timeframe": by_symbol_timeframe,
        "by_regime": by_regime,
    }


def reproducibility_summary(conn: sqlite3.Connection) -> dict:
    """Task 9 Improvement requirement 6."""
    rows = fetch_all(
        conn,
        "SELECT rc.all_identical, rc.n_runs, rc.distinct_outputs, c.case_category "
        "FROM reproducibility_checks rc JOIN benchmark_charts c ON c.chart_id = rc.chart_id",
    )
    n = len(rows)
    if n == 0:
        return {"n_checked": 0, "deterministic_pct": None, "by_category": {}}
    n_det = sum(r["all_identical"] for r in rows)
    by_category: dict[str, dict] = {}
    for cat in set(r["case_category"] for r in rows):
        cat_rows = [r for r in rows if r["case_category"] == cat]
        cat_det = sum(r["all_identical"] for r in cat_rows)
        by_category[cat] = {"n_checked": len(cat_rows), "deterministic_pct": round(cat_det / len(cat_rows), 4)}
    return {
        "n_checked": n,
        "runs_per_check": rows[0]["n_runs"],
        "deterministic_pct": round(n_det / n, 4),
        "by_category": by_category,
        "note": ("Tests ENGINE determinism (same pre-generated price series run through the "
                "pipeline repeatedly), not fixture-generation determinism (that was a separate, "
                "already-fixed Task 9 bug -- see pipeline.py). 'Cross-platform' is not literally "
                "testable from a single machine in this environment; what's measured is repeatability "
                "across independent process invocations."),
    }


def regime_robustness_summary(conn: sqlite3.Connection) -> dict:
    """Task 9 Improvement requirement 1 (regime coverage) + a robustness
    read on real market data that does NOT fabricate an accuracy number --
    see real_regime.py's docstring for why no reference count exists here.
    """
    rows = fetch_all(
        conn,
        "SELECT c.symbol, c.timeframe, c.regime_trend, c.regime_volatility, "
        "r.engine_structure_type, r.rule_warnings_json "
        "FROM benchmark_charts c JOIN benchmark_runs r ON r.chart_id = c.chart_id "
        "WHERE c.case_category = 'real_market_regime'",
    )
    import json as _json
    n = len(rows)
    resolved = sum(1 for r in rows if r["engine_structure_type"] not in (None, "no_structure_found"))
    zero_warnings = sum(1 for r in rows if _json.loads(r["rule_warnings_json"] or "[]") == [])

    by_regime: dict[str, dict] = {}
    for key_fn, label in [
        (lambda r: r["regime_trend"], "trend"),
        (lambda r: r["regime_volatility"], "volatility"),
    ]:
        groups: dict[str, list] = {}
        for r in rows:
            groups.setdefault(key_fn(r), []).append(r)
        by_regime[label] = {
            g: {
                "n": len(grows),
                "resolved_structure_pct": round(sum(1 for r in grows if r["engine_structure_type"] not in (None, "no_structure_found")) / len(grows), 4),
                "zero_hard_rule_warnings_pct": round(sum(1 for r in grows if _json.loads(r["rule_warnings_json"] or "[]") == []) / len(grows), 4),
            }
            for g, grows in groups.items()
        }

    return {
        "n": n,
        "resolved_structure_pct": round(resolved / n, 4) if n else None,
        "zero_hard_rule_warnings_pct": round(zero_warnings / n, 4) if n else None,
        "by_regime": by_regime,
        "note": ("These are ROBUSTNESS properties (does the pipeline produce a resolved structure "
                "and pass its own hard-rule checks cleanly across real market conditions), NOT "
                "accuracy/agreement numbers -- no independent reference wave count exists for "
                "arbitrary real-market windows, so no 'agreement %' is computed here."),
    }


def full_summary(conn: sqlite3.Connection) -> dict:
    return {
        "dataset_summary": dataset_summary(conn),
        "agreement": agreement_rate(conn),
        "dimension_agreement": dimension_agreement(conn),
        "confusion_matrix": confusion_matrix(conn),
        "precision_recall_f1_per_class": precision_recall_f1_per_class(conn),
        "cohens_kappa": cohens_kappa(conn),
        "rule_comparisons": rule_comparison_summary(conn),
        "reproducibility": reproducibility_summary(conn),
        "regime_robustness": regime_robustness_summary(conn),
    }


if __name__ == "__main__":
    import json
    with connect() as conn:
        print(json.dumps(full_summary(conn), indent=2, default=str))
