#!/usr/bin/env python3
import argparse
import math
import re
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt


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
    n = len(values)
    m = sum(values) / n
    v = sum((x - m) ** 2 for x in values) / n
    return m, math.sqrt(v)


def main():
    ap = argparse.ArgumentParser(
        description="Group CSVs by identifier (last token after '_'), overlay histograms per identifier, save PNGs."
    )
    ap.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing the CSV files (e.g. results/out).",
    )
    ap.add_argument(
        "--out-dir",
        default="results/pics",
        help="Output directory for PNGs (default: results/pics).",
    )
    ap.add_argument(
        "--bins",
        type=int,
        default=50,
        help="Histogram bins (default: 50).",
    )
    ap.add_argument(
        "--alpha",
        type=float,
        default=0.5,
        help="Histogram transparency for overlay (default: 0.5).",
    )
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
        ident = identifier_from_filename(f)
        groups[ident].append(f)

    print(f"Found {len(csv_files)} CSVs in {input_dir}")
    print(f"Grouped into {len(groups)} identifiers")
    print(f"Output dir: {out_dir}")
    print()

    for ident, files in sorted(groups.items(), key=lambda x: x[0]):
        # You said each identifier appears twice; but we’ll handle 1+ files safely.
        plt.figure()

        any_plotted = False
        for f in sorted(files):
            cycles, mean_s, std_s = read_cycles_even_rows(f)
            if not cycles:
                print(f"[SKIP] {f.name}: no cycles parsed (even rows)")
                continue

            # If SUMMARY missing, compute mean/std from extracted cycles
            if mean_s is None or std_s is None:
                mean_s, std_s = mean_std(cycles)

            label = f"{f.name}"
            if mean_s is not None and std_s is not None:
                label += f" | mean={mean_s:.2f}, std={std_s:.2f}"

            plt.hist(cycles, bins=args.bins, alpha=args.alpha, label=label)
            any_plotted = True

        if not any_plotted:
            print(f"[SKIP GROUP] id={ident}: nothing to plot")
            plt.close()
            continue

        plt.title(f"Identifier: {ident} (overlay of {len(files)} CSVs)")
        plt.xlabel("cycles")
        plt.ylabel("count")
        plt.legend(fontsize="small")

        out_png = out_dir / f"{ident}.png"
        plt.savefig(out_png, dpi=200, bbox_inches="tight")
        plt.close()

        print(f"[OK] id={ident}: saved {out_png}")

    print("\nDone.")


if __name__ == "__main__":
    main()
