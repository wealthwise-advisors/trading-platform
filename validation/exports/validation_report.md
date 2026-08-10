# Elliott Wave Expert Chart Validation Report

**Analyses in database:** 369  
**Reviews recorded:** 5  

## Coverage by market / timeframe

| market | 15m | 1d | 1h | 4h | 5m |
|---|---|---|---|---|---|
| CL | 19 | 3 | 16 | 7 | 29 |
| ES | 19 | 3 | 16 | 7 | 29 |
| GC | 19 | 3 | 16 | 7 | 29 |
| NQ | 19 | 3 | 16 | 7 | 29 |
| SPY | 19 | 3 | 16 | 7 | 28 |

## Hard-rule compliance

- 0 of 369 analyses show a rule violation on independent re-audit -- compliance rate **100.0%**

## Quality score distribution (direct engine output, no review needed)

| Structure | n | min | median | mean | max |
|---|---|---|---|---|---|
| impulse_quality | 240 | 0.0 | 0.5 | 0.47 | 1.0 |
| corrective_quality | 357 | 0.627 | 0.842 | 0.839 | 0.996 |
| triangle_quality | 42 | 0.293 | 0.406 | 0.419 | 0.746 |
| diagonal_quality | 95 | 0.33 | 0.51 | 0.512 | 0.757 |
| confidence | 364 | 0.317 | 0.545 | 0.546 | 0.933 |

## Structure accuracy

```json
{
  "total_reviewed": 5,
  "by_verdict": {
    "Acceptable Alternate": 2,
    "Ambiguous": 1,
    "Correct": 2
  },
  "structure_accuracy": 0.8
}
```

## Precision / Recall / F1 by miss-type

| Miss type | Precision | Recall | F1 |
|---|---|---|---|
| missed_triangle | 1.0 | 1.0 | 1.0 |
| missed_diagonal | 1.0 | 1.0 | 1.0 |
| mis_numbering | 1.0 | 1.0 | 1.0 |
| wrong_correction | 1.0 | 1.0 | 1.0 |
| wrong_degree | 1.0 | 1.0 | 1.0 |