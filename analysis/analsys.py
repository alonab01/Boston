#!/usr/bin/env python3
import argparse
import math
import re
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


def identifier_from_filename(csv_path: Path) -> str:
    """Identifier = last token after last '_' in filename stem."""
    stem = csv_path.stem
    return stem.split("_")[-1] if "_" in stem else stem


def parse_summary_line(line: str):
    """
    Expected: SUMMARY,COUNT=...,MEAN=...,STD=...
    Returns (mean, std) or (None, None).
    """
    line = line.strip()
    if not line.startswith("SUMMARY"):
        return None, None

    mean = None
    std = None
    for part in line.split(","):
        part = part.strip()
        if part.startswith("MEAN="):
            try:
                mean = float(part.split("=", 1)[1])
            except ValueError:
                pass
        elif part.startswith("STD="):
            try:
                std = float(part.split("=", 1)[1])
            except ValueError:
                pass
    return mean, std


def read_cycles_even_rows(csv_path: Path):
    """
    Reads numeric data rows that look like:
        <int_index>,<cycles>,...
    Then takes cycles from even-numbered data rows (2,4,6,...) in 1-based indexing.
    Also reads MEAN/STD from last SUMMARY line if present.

    Returns:
        cycles_even (list[float]),
        mean_from_summary (float|None),
        std_from_summary (float|None)
    """
    lines = csv_path.read_text(errors="ignore").splitlines()

    mean_sum = std_sum = None
    if lines and lines[-1].strip().startswith("SUMMARY"):
        mean_sum, std_sum = parse_summary_line(lines[-1])
        lines = lines[:-1]

    data_cycles = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue

        # skip header-like lines
        if re.match(r"^[A-Za-z]", ln):
            continue

        parts = [p.strip() for p in ln.split(",")]
        if len(parts) < 2:
            continue

        if not re.match(r"^\d+$", parts[0]):
            continue

        try:
            cyc = float(parts[1])
        except ValueError:
            continue

        data_cycles.append(cyc)

    cycles_even = [c for i, c in enumerate(data_cycles, start=1) if i % 2 == 0]
    return cycles_even, mean_sum, std_sum


def mean_std(values):
    if not values:
        return None, None
    x = np.asarray(values, dtype=float)
    m = float(np.mean(x))
    s = float(np.std(x, ddof=0))
    return m, s


def nice_power_of_10(x: float) -> float:
    """Round x down to nearest power of 10."""
    if x <= 0 or not math.isfinite(x):
        return 1.0
    return 10 ** math.floor(math.log10(x))


def should_use_symlog(all_vals: np.ndarray, per_series: list[np.ndarray], lo: float, hi: float) -> bool:
    """
    Heuristic to decide if symlog helps:
      - If overall spread (hi/lo) is large
      - Or if medians across series differ a lot
    """
    eps = 1e-9
    lo_safe = max(float(lo), eps)
    hi_safe = max(float(hi), lo_safe + eps)

    spread_ratio = hi_safe / lo_safe

    medians = [float(np.median(s)) for s in per_series if s.size > 0]
    med_ratio = 1.0
    if len(medians) >= 2:
        mmin = max(min(medians), eps)
        mmax = max(medians)
        med_ratio = mmax / mmin

    return (spread_ratio >= 50.0) or (med_ratio >= 20.0)


def make_symlog_bins(lo: float, hi: float, linthresh: float, n_bins: int) -> np.ndarray:
    """
    Bin edges that behave nicely on a symlog axis:
      - linear spacing from lo..linthresh
      - log spacing from linthresh..hi
    Assumes cycles >= 0.
    """
    lo = float(max(lo, 0.0))
    hi = float(hi)
    linthresh = float(max(linthresh, 1e-9))

    if not (math.isfinite(lo) and math.isfinite(hi) and math.isfinite(linthresh)):
        return np.linspace(0.0, 1.0, n_bins + 1)

    if hi <= lo:
        return np.array([lo, hi], dtype=float)

    if hi <= linthresh:
        return np.linspace(lo, hi, n_bins + 1)

    # split bins between linear and log
    n_lin = max(10, int(n_bins * 0.35))
    n_log = max(10, n_bins - n_lin)

    lin_hi = min(linthresh, hi)
    lin_edges = np.linspace(lo, lin_hi, n_lin + 1)

    log_edges = np.logspace(np.log10(linthresh), np.log10(hi), n_log + 1)

    edges = np.concatenate([lin_edges[:-1], log_edges])
    edges[0] = lo
    edges[-1] = hi

    edges = np.unique(edges)
    if edges.size < 2:
        edges = np.array([lo, hi], dtype=float)

    return edges


def main():
    ap = argparse.ArgumentParser(
        description="Group CSVs by identifier (last token after '_'), overlay histograms per identifier, save PNGs."
    )
    ap.add_argument("--input-dir", required=True, help="Directory containing CSV files (e.g. results/out).")
    ap.add_argument("--out-dir", default="results/scaled_pics", help="Output directory for PNGs.")
    ap.add_argument("--bins", type=int, default=50, help="Histogram bins (default: 50).")
    ap.add_argument("--alpha", type=float, default=0.5, help="Histogram alpha (default: 0.5).")

    # Fix A defaults ON
    ap.add_argument("--no-shared-bins", action="store_false", dest="shared_bins",
                    help="Disable shared bin edges per identifier.")
    ap.set_defaults(shared_bins=True)

    ap.add_argument("--robust-range", nargs=2, type=float, default=(1.0, 99.0), metavar=("LO", "HI"),
                    help="Percentile range to plot (default: 1 99).")
    ap.add_argument("--no-robust-range", action="store_true",
                    help="Disable percentile clipping (use full min..max).")

    ap.add_argument("--counts", action="store_true",
                    help="Use raw counts instead of density normalization (default: density).")

    # Fix B: auto xscale
    ap.add_argument("--xscale", choices=["auto", "linear", "symlog"], default="auto",
                    help="X-axis scale (default: auto).")
    ap.add_argument("--linthresh", type=float, default=None,
                    help="symlog linear threshold (default: auto per identifier).")

    args = ap.parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(input_dir.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in: {input_dir}")
        return

    groups = defaultdict(list)
    for f in csv_files:
        groups[identifier_from_filename(f)].append(f)

    print(f"Found {len(csv_files)} CSVs in {input_dir}")
    print(f"Grouped into {len(groups)} identifiers")
    print(f"Output dir: {out_dir}\n")

    density = not args.counts

    for ident, files in sorted(groups.items(), key=lambda x: x[0]):
        # Parse all series first
        series = []
        meta = []

        for f in sorted(files):
            cycles, mean_s, std_s = read_cycles_even_rows(f)
            if not cycles:
                print(f"[SKIP] {f.name}: no cycles parsed (even rows)")
                continue

            if mean_s is None or std_s is None:
                mean_s, std_s = mean_std(cycles)

            arr = np.asarray(cycles, dtype=float)
            arr = arr[np.isfinite(arr)]
            if arr.size == 0:
                print(f"[SKIP] {f.name}: no finite cycles")
                continue

            series.append(arr)
            meta.append((f.name, mean_s, std_s))

        if not series:
            print(f"[SKIP GROUP] id={ident}: nothing to plot")
            continue

        all_vals = np.concatenate(series)
        if all_vals.size == 0:
            print(f"[SKIP GROUP] id={ident}: empty data")
            continue

        # Robust range (default ON)
        if args.no_robust_range:
            lo = float(np.min(all_vals))
            hi = float(np.max(all_vals))
            robust_used = False
        else:
            lo_p, hi_p = args.robust_range
            lo = float(np.percentile(all_vals, lo_p))
            hi = float(np.percentile(all_vals, hi_p))
            robust_used = True

        if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
            print(f"[SKIP GROUP] id={ident}: invalid range lo={lo}, hi={hi}")
            continue

        # Decide symlog (ALWAYS defines use_symlog)
        if args.xscale == "linear":
            use_symlog = False
        elif args.xscale == "symlog":
            use_symlog = True
        else:
            use_symlog = should_use_symlog(all_vals, series, lo, hi)

        # Choose linthresh if symlog
        linthresh = args.linthresh
        if use_symlog and linthresh is None:
            p10 = float(np.percentile(all_vals, 10))
            linthresh = nice_power_of_10(p10)
        if use_symlog:
            linthresh = float(max(linthresh, 1e-9))

        # Build bins
        if args.shared_bins:
            if use_symlog:
                bins = make_symlog_bins(lo, hi, linthresh, args.bins)
            else:
                bins = np.linspace(lo, hi, args.bins + 1)
        else:
            bins = args.bins  # Matplotlib computes bins per dataset

        plt.figure()

        any_plotted = False
        for arr, (name, mean_s, std_s) in zip(series, meta):
            plot_arr = arr

            # Clip to robust range so outliers don't dominate axis
            if robust_used:
                plot_arr = plot_arr[(plot_arr >= lo) & (plot_arr <= hi)]
                if plot_arr.size == 0:
                    print(f"[SKIP] {name}: all samples outside robust range {lo:.2f}..{hi:.2f}")
                    continue

            label = f"{name}"
            if mean_s is not None and std_s is not None:
                label += f" | mean={mean_s:.2f}, std={std_s:.2f}"

            plt.hist(plot_arr, bins=bins, alpha=args.alpha, label=label, density=density)
            any_plotted = True

        if not any_plotted:
            print(f"[SKIP GROUP] id={ident}: nothing to plot after filtering")
            plt.close()
            continue

        scale_note = "symlog" if use_symlog else "linear"
        rr_note = f"robust={args.robust_range[0]:g}-{args.robust_range[1]:g}%" if robust_used else "robust=off"
        plt.title(f"Identifier: {ident} (overlay of {len(series)} CSVs) | {scale_note}, {rr_note}")
        plt.xlabel("cycles")
        plt.ylabel("density" if density else "count")

        if use_symlog:
            plt.xscale("symlog", linthresh=linthresh)

        plt.legend(fontsize="small")

        out_png = out_dir / f"{ident}.png"
        plt.savefig(out_png, dpi=200, bbox_inches="tight")
        plt.close()

        print(f"[OK] id={ident}: saved {out_png}")

    print("\nDone.")


if __name__ == "__main__":
    main()
