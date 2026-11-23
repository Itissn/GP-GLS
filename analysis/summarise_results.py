"""Recalculate archived vehicle-routing results from the workbook's objective values."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results" / "Final Result.xlsx"
OUTPUT = ROOT / "results" / "derived"
RUNS = 15


def number(row, column, row_number, field):
    value = row[column]
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"Row {row_number}: expected a numeric, finite {field}, found {value!r}")
    return float(value)


def read_sheet(sheet):
    rows = iter(enumerate(sheet.values, 1))
    _, primary = next(rows)
    _, secondary = next(rows)
    headers = [b if b is not None else a for a, b in zip(primary, secondary)]

    def column(name):
        if headers.count(name) != 1:
            raise ValueError(f"Expected exactly one column named {name}")
        return headers.index(name)

    instance_col = column("Instances")
    bks_col, kgls_col = column("BKS"), column("KGLS(10)")
    kgls_gap_col, avg_col, avg_gap_col = column("Gap"), column("GPGLS_A"), column("Gap_A")
    objectives = [column(f"GPGLS_{i}") for i in range(1, RUNS + 1)]
    gaps = [column(f"Gap_{i}" if f"Gap_{i}" in headers else f"GAPS_{i}") for i in range(1, RUNS + 1)]
    observations, issues, seen = [], [], set()
    footer = None

    def reconcile(row, index, field, col, recomputed):
        stored = number(row, col, index, field)
        if not math.isclose(stored, recomputed, rel_tol=1e-9, abs_tol=1e-12):
            issues.append(dict(sheet=sheet.title, row=index, field=field, stored=stored, recomputed=recomputed))

    for index, row in rows:
        if all(v is None for v in row):
            continue
        name = str(row[instance_col]).strip()
        if name == "Avg Gap" and footer is None:
            footer = (index, row)
            continue
        if footer or not name.startswith("X-") or name in seen:
            raise ValueError(f"Row {index}: unexpected or duplicate instance {name!r}")
        seen.add(name)
        bks = number(row, bks_col, index, "BKS")
        ref = number(row, kgls_col, index, "KGLS(10)")
        values = [number(row, col, index, f"GPGLS_{i}") for i, col in enumerate(objectives, 1)]
        if min(bks, ref, *values) <= 0:
            raise ValueError(f"Row {index}: routing objectives and BKS must be positive")
        avg = mean(values)
        ref_gap, avg_gap = (ref - bks) / bks, (avg - bks) / bks
        reconcile(row, index, "KGLS_gap", kgls_gap_col, ref_gap)
        reconcile(row, index, "GPGLS_A", avg_col, avg)
        reconcile(row, index, "Gap_A", avg_gap_col, avg_gap)
        result = dict(instance=name, bks=bks, kgls_objective=ref, kgls_gap=ref_gap,
                      gpgls_mean_objective=avg, gpgls_mean_gap=avg_gap)
        for i, (objective, col) in enumerate(zip(values, gaps), 1):
            gap = (objective - bks) / bks
            result[f"result_{i}_gap"] = gap
            reconcile(row, index, f"Gap_{i}", col, gap)
        observations.append(result)

    if not observations or footer is None:
        raise ValueError("Expected instance rows followed by an Avg Gap footer")
    index, row = footer
    fields = [("KGLS_gap", kgls_gap_col, "kgls_gap"), ("Gap_A", avg_gap_col, "gpgls_mean_gap")]
    fields.extend((f"gap_{i}", col, f"result_{i}_gap") for i, col in enumerate(gaps, 1))
    for field, col, key in fields:
        reconcile(row, index, "footer_" + field, col, mean(r[key] for r in observations))
    return observations, issues


def comparison(row):
    a, b = row["gpgls_mean_gap"], row["kgls_gap"]
    if math.isclose(a, b, rel_tol=0, abs_tol=1e-12):
        return "equal"
    return "lower" if a < b else "higher"


def write_csv(path, fields, records):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def plot(observations, path):
    fig, ax = plt.subplots(figsize=(7.6, 6.5), layout="constrained")
    points = [(100*r["kgls_gap"], 100*r["gpgls_mean_gap"], comparison(r)) for r in observations]
    for group, color, marker in [("lower", "#057e79", "o"), ("higher", "#b85420", "^"), ("equal", "#53697a", "D")]:
        subset = [(x, y) for x, y, result in points if result == group]
        if subset:
            x, y = zip(*subset)
            ax.scatter(x, y, s=35, marker=marker, color=color, alpha=.85, edgecolors="white",
                       linewidth=.6, zorder=3, label=f"GP-GLS {group} ({len(subset)})")
    values = [v for x, y, _ in points for v in (x, y)]
    low, high = min(0, min(values)), max(0, max(values))
    margin = max(high - low, .1) * .04
    bounds = [low - margin, high + margin]
    ax.plot(bounds, bounds, "--", color="#748392", lw=1, label="Equal gap")
    ax.set(xlim=bounds, ylim=bounds, aspect="equal", xlabel="KGLS(10) gap to best-known objective (%)",
           ylabel="GP-GLS mean gap to best-known objective (%)")
    ax.set_title(f"Routing solution quality across {len(points)} benchmark instances", loc="left",
                 weight="bold", fontsize=14, color="#19374b", pad=12)
    ax.grid(color="#e0e6eb", linewidth=.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper left", frameon=False)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=SOURCE)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()
    workbook = load_workbook(args.workbook, read_only=True, data_only=True)
    try:
        observations, issues = read_sheet(workbook["Sheet1"])
    finally:
        workbook.close()

    gp = 100 * mean(row["gpgls_mean_gap"] for row in observations)
    kgls = 100 * mean(row["kgls_gap"] for row in observations)
    summary = {
        "source_sha256": hashlib.sha256(args.workbook.read_bytes()).hexdigest(),
        "instances": len(observations), "recorded_result_columns": RUNS,
        "gpgls_mean_gap_pct": gp, "kgls_mean_gap_pct": kgls,
        "kgls_minus_gpgls_gap_percentage_points": kgls - gp,
        "gpgls_paired_gap": {g: sum(comparison(r) == g for r in observations) for g in ("lower", "equal", "higher")},
        "reconciliation_issue_count": len(issues), "algorithm_rerun": False,
        "scope": "Descriptive comparison of archived values; solver budgets and seeds are undocumented."
    }
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "instance_summary.csv", list(observations[0]), observations)
    write_csv(out / "reconciliation_issues.csv", ["sheet", "row", "field", "stored", "recomputed"], issues)
    plot(observations, out / "benchmark_results.png")
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
