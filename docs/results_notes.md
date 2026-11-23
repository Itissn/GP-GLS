# Results interpretation and reconciliation

## Calculation

For a recorded objective value `v` and best-known value `b`, gap (%) is `100 * (v - b) / b`. The analysis averages the 15 recorded GP-GLS objective columns for each instance, then averages instance-level percentage gaps across the 79 rows. This gives every instance equal weight. The KGLS summary uses the same instance-level convention.

All 79 stored GP-GLS instance means agree with the 15 recorded objective values within the script's floating-point tolerance. The issues found are in footer summaries, not those per-instance means.

## Why the original footer is not reused

Ten footer values differ from a full recalculation. Several average ranges stop at row 80 although the final instance is row 81. For example, `I82 = AVERAGE(I3:I80)`. Two formulas reference neighbouring footer cells rather than a complete result column: `S82 = AVERAGE(Q82:R82)` and `W82 = AVERAGE(U82:V82)`.

The original Excel file is unchanged. `results/derived/reconciliation_issues.csv` records the stored and recalculated values; `summary.json` records its SHA-256 hash. The chart and README use the per-instance recalculation.

## What is not established

The workbook does not supply executable training/solver code, seed metadata or complete timing conditions. Its 15 result columns should not be assumed to be independent random-seed trials. The second sheet contains tree/feature information, but this analysis does not infer undocumented feature definitions. No statistical significance or deployment benefit is claimed.
