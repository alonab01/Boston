#!/usr/bin/env python3
import argparse
import math
import re
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt


def read_cycles_even_rows(csv_path: Path) -> np.ndarray:
    """Parse cycles from data rows; keep only even-indexed samples (2,4,6,...) in 1-based indexing.
    Supports an optional trailing SUMMARY line.
    Expects data rows like: <int_index>,<cycles>,...
    """
    lines = csv_path.read_text(errors="ignore").splitlines()
    if lines and lines[-1].strip().startswith("SUMMARY"):
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
    arr = np.asarray(cycles_even, dtype=float)
    return arr[np.isfinite(arr)]


def section_from_name(path: Path) -> str:
    stem = path.stem
    if stem.startswith("section1_"):
        return "section1"
    if stem.startswith("section2_"):
        return "section2"
    return "unknown"


def env_from_path(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    return rel.parts[0] if len(rel.parts) >= 2 else "root"


def compute_ecdf(arr: np.ndarray):
    x = np.sort(arr)
    n = x.size
    y = np.arange(1, n + 1, dtype=float) / float(n)
    return x, y


def robust_range(vals: np.ndarray, lo_p: float, hi_p: float):
    lo = float(np.percentile(vals, lo_p))
    hi = float(np.percentile(vals, hi_p))
    return lo, hi


def should_logx(lo: float, hi: float) -> bool:
    eps = 1e-12
    lo_safe = max(float(lo), eps)
    hi_safe = max(float(hi), lo_safe + eps)
    return (hi_safe / lo_safe) >= 30.0


def logspace_bins(lo: float, hi: float, n_bins: int) -> np.ndarray:
    lo = max(float(lo), 1e-12)
    hi = float(hi)
    return np.logspace(np.log10(lo), np.log10(hi), n_bins + 1)


def linear_bins(lo: float, hi: float, n_bins: int) -> np.ndarray:
    return np.linspace(float(lo), float(hi), n_bins + 1)


def make_env_colors(envs):
    """Stable, readable palette (tab20) that can handle up to ~20 envs nicely."""
    cmap = plt.get_cmap("tab20")
    colors = {}
    for i, env in enumerate(envs):
        colors[env] = cmap(i % cmap.N)
    return colors


def add_legends(envs, env_color, section_style, legend_mode: str):
    """legend_mode: inside|outside"""
    ax = plt.gca()

    # Section legend (linestyle)
    sec_handles = []
    for sec, ls in [("section1", section_style["section1"]), ("section2", section_style["section2"])]:
        h, = ax.plot([], [], color="k", linestyle=ls, linewidth=3.0, label=sec)
        sec_handles.append(h)
    leg_sec = ax.legend(handles=sec_handles, title="Section (linestyle)", loc="upper left", framealpha=0.95)
    ax.add_artist(leg_sec)

    # Env legend (color)
    env_handles = []
    for env in envs:
        h, = ax.plot([], [], color=env_color[env], linestyle="-", linewidth=3.2, label=env)
        env_handles.append(h)

    if legend_mode == "outside":
        ax.legend(
            handles=env_handles,
            title="Environment (color)",
            loc="center left",
            bbox_to_anchor=(1.01, 0.5),
            framealpha=0.95
        )
    else:
        # Put inside, bottom-right, multiple columns to avoid covering data
        ncol = 2 if len(envs) > 6 else 1
        ax.legend(
            handles=env_handles,
            title="Environment (color)",
            loc="lower right",
            ncol=ncol,
            fontsize=9,
            title_fontsize=10,
            framealpha=0.95
        )


def main():
    ap = argparse.ArgumentParser(description="Paper-ready ONE figure overlay for ALL envs + both sections.")
    ap.add_argument("--root", required=True, help="Root directory, e.g. results/out")
    ap.add_argument("--out-dir", default="results/combined_pics", help="Output directory")
    ap.add_argument("--out", default=None, help="Output PNG path (overrides --out-dir)")

    ap.add_argument("--mode", choices=["ecdf", "hist"], default="ecdf",
                    help="ecdf = best readability; hist = log-log histogram overlay")
    ap.add_argument("--bins", type=int, default=140, help="Bins for hist mode")

    ap.add_argument("--match", default=None, help="Only include CSVs whose filename matches this regex")

    ap.add_argument("--robust", nargs=2, type=float, default=(1.0, 99.0), metavar=("LO", "HI"),
                    help="Percentile clip for x-range (default: 1 99). Use --no-robust to disable.")
    ap.add_argument("--no-robust", action="store_true", help="Disable percentile clipping")

    ap.add_argument("--xscale", choices=["auto", "linear", "log"], default="auto")
    ap.add_argument("--hist-yscale", choices=["log", "linear"], default="log",
                    help="Hist mode: use log y to make spikes + tails visible together")
    ap.add_argument("--hist-ymin", type=float, default=1e-8, help="Hist mode: y-lower bound when logy")
    ap.add_argument("--hist-ymax", type=float, default=None, help="Hist mode: optional y-upper bound")
    ap.add_argument("--legend", choices=["inside", "outside"], default="inside",
                    help="Legend placement. inside is usually better for papers.")

    ap.add_argument("--alpha", type=float, default=0.95)
    ap.add_argument("--linewidth", type=float, default=2.2)
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        suffix = "ECDF" if args.mode == "ecdf" else "HIST"
        out_path = out_dir / f"ALL_ENVS_{suffix}.png"

    csvs = sorted(root.rglob("*.csv"))
    if args.match:
        rx = re.compile(args.match)
        csvs = [p for p in csvs if rx.search(p.name)]
    if not csvs:
        raise SystemExit(f"No CSV files found under: {root}")

    # Concatenate per (env, section)
    buckets = defaultdict(list)
    for p in csvs:
        sec = section_from_name(p)
        if sec not in ("section1", "section2"):
            continue
        env = env_from_path(p, root)
        arr = read_cycles_even_rows(p)
        if arr.size:
            buckets[(env, sec)].append(arr)

    series = {k: np.concatenate(v) for k, v in buckets.items() if v}
    if not series:
        raise SystemExit("No usable data found (need filenames starting with section1_/section2_).")

    envs = sorted({env for (env, _) in series.keys()})
    env_color = make_env_colors(envs)
    section_style = {"section1": "-", "section2": "--"}

    all_vals = np.concatenate(list(series.values()))
    if args.no_robust:
        lo, hi = float(np.min(all_vals)), float(np.max(all_vals))
        robust_used = False
    else:
        lo, hi = robust_range(all_vals, args.robust[0], args.robust[1])
        robust_used = True

    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        raise SystemExit("Bad x-range (lo/hi).")

    # xscale
    if args.xscale == "linear":
        use_logx = False
    elif args.xscale == "log":
        use_logx = True
    else:
        use_logx = should_logx(lo, hi)

    plt.figure(figsize=(13.5, 6.8))
    plt.grid(True, which="both", linestyle=":", linewidth=0.6, alpha=0.6)

    if args.mode == "ecdf":
        for env in envs:
            for sec in ("section1", "section2"):
                key = (env, sec)
                if key not in series:
                    continue
                arr = series[key]
                if robust_used:
                    arr = arr[(arr >= lo) & (arr <= hi)]
                if arr.size == 0:
                    continue
                x, y = compute_ecdf(arr)
                plt.plot(
                    x, y,
                    color=env_color[env],
                    linestyle=section_style[sec],
                    linewidth=args.linewidth,
                    alpha=args.alpha
                )

        if use_logx:
            plt.xscale("log")
        plt.ylim(0.0, 1.0)
        plt.xlabel("cycles")
        plt.ylabel("ECDF")
        rr_note = f"robust={args.robust[0]:g}-{args.robust[1]:g}%" if robust_used else "robust=off"
        x_note = "logx" if use_logx else "linearx"
        plt.title(f"ALL envs + sections | ECDF | {x_note}, {rr_note}")

    else:
        # Hist mode: plot probability mass per bin (sum bins = 1), not "density".
        if use_logx:
            bins = logspace_bins(lo, hi, args.bins)
            plt.xscale("log")
        else:
            bins = linear_bins(lo, hi, args.bins)

        for env in envs:
            for sec in ("section1", "section2"):
                key = (env, sec)
                if key not in series:
                    continue
                arr = series[key]
                if robust_used:
                    arr = arr[(arr >= lo) & (arr <= hi)]
                if arr.size == 0:
                    continue
                counts, edges = np.histogram(arr, bins=bins, density=False)
                total = counts.sum()
                if total <= 0:
                    continue
                pmf = counts.astype(float) / float(total)  # probability mass per bin
                x = edges
                y = np.r_[pmf, pmf[-1] if pmf.size else 0.0]
                plt.step(
                    x, y,
                    where="post",
                    color=env_color[env],
                    linestyle=section_style[sec],
                    linewidth=args.linewidth,
                    alpha=args.alpha
                )

        plt.xlabel("cycles")
        plt.ylabel("probability per bin")

        if args.hist_yscale == "log":
            plt.yscale("log")
            plt.ylim(bottom=max(args.hist_ymin, 1e-14))
            if args.hist_ymax is not None:
                plt.ylim(top=args.hist_ymax)
        rr_note = f"robust={args.robust[0]:g}-{args.robust[1]:g}%" if robust_used else "robust=off"
        x_note = "logx" if use_logx else "linearx"
        y_note = f"logy (ymin={args.hist_ymin:g})" if args.hist_yscale == "log" else "lineary"
        plt.title(f"ALL envs + sections | Histogram overlay (PMF) | {x_note}, {y_note}, {rr_note}")

    add_legends(envs, env_color, section_style, args.legend)

    plt.tight_layout()
    # bbox_inches tight so outside legend is included
    plt.savefig(out_path, dpi=280, bbox_inches="tight")
    plt.close()
    print(f"[OK] wrote {out_path}")


if __name__ == "__main__":
    main()
