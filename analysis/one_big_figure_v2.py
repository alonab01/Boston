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


def add_legends(envs, env_color, section_style, legend_mode: str, env_font=9, env_title_font=10,
                sec_font=None, sec_title_font=None):
    """legend_mode: inside|outside"""
    ax = plt.gca()

    # Section legend (linestyle)
    sec_handles = []
    for sec, ls in [("section1", section_style["section1"]), ("section2", section_style["section2"])]:
        h, = ax.plot([], [], color="k", linestyle=ls, linewidth=3.0, label=sec)
        sec_handles.append(h)
    leg_sec = ax.legend(
        handles=sec_handles,
        title="Section (linestyle)",
        loc="upper left",
        framealpha=0.95,
        fontsize=(sec_font if sec_font is not None else env_font),
        title_fontsize=(sec_title_font if sec_title_font is not None else env_title_font),
    )
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
            framealpha=0.95,
            fontsize=env_font,
            title_fontsize=env_title_font
        )
    else:
        ncol = 2 if len(envs) > 6 else 1
        ax.legend(
            handles=env_handles,
            title="Environment (color)",
            loc="lower left",
            bbox_to_anchor=(0.02, 0.02),  # small padding from the corner
            ncol=ncol,
            fontsize=env_font,
            title_fontsize=env_title_font,
            framealpha=0.95
        )


# ---------------- NEW: annotation helpers ----------------

def _geom_mid(x1: float, x2: float) -> float:
    if x1 > 0 and x2 > 0:
        return math.sqrt(x1 * x2)
    return 0.5 * (x1 + x2)


def add_pair_arrow(ax, x1, x2, y, color, label=None,
                   lw=2.6, text_size=12,
                   small_gap_rel=0.04):
    """
    If medians are far: draw <-> between x1 and x2.
    If medians are very close: draw a single -> from left (min) to midpoint.
    Always keep env name label (if provided).
    """
    x1 = float(x1); x2 = float(x2)
    lo = min(x1, x2)
    hi = max(x1, x2)
    rel_gap = (hi - lo) / max(lo, 1e-12)

    xm = _geom_mid(x1, x2)

    if rel_gap < small_gap_rel:
        # close -> single arrow from left to midpoint
        ax.annotate(
            "",
            xy=(xm, y),
            xytext=(lo, y),
            arrowprops=dict(arrowstyle="->", color=color, lw=lw),
            annotation_clip=False,
        )
        if label:
            ax.text(
                xm, min(0.995, y + 0.02),
                label,
                color=color,
                ha="center",
                va="bottom",
                fontsize=text_size,
                fontweight="bold",
                clip_on=False,
            )
        return

    # normal -> double arrow
    ax.annotate(
        "",
        xy=(x1, y),
        xytext=(x2, y),
        arrowprops=dict(arrowstyle="<->", color=color, lw=lw),
        annotation_clip=False,
    )
    if label:
        ax.text(
            xm, min(0.995, y + 0.02),
            label,
            color=color,
            ha="center",
            va="bottom",
            fontsize=text_size,
            fontweight="bold",
            clip_on=False,
        )


def add_curve_arrow(ax, x, y, color, label, q=0.65, lw=2.4, text_size=12):
    """Arrow + label pointing to a curve around quantile q."""
    if x.size < 5:
        return
    idx = int(max(0, min(x.size - 1, round(q * (x.size - 1)))))
    x0, y0 = float(x[idx]), float(y[idx])
    # place text to the right; for negative x move left a bit
    xtext = x0 * (1.25 if x0 != 0 else 1.0)
    ytext = max(0.05, min(0.95, y0 - 0.12))
    ax.annotate(
        label,
        xy=(x0, y0),
        xytext=(xtext, ytext),
        textcoords="data",
        arrowprops=dict(arrowstyle="->", color=color, lw=lw),
        color=color,
        fontsize=text_size,
        fontweight="bold",
        annotation_clip=False,
    )


def main():
    ap = argparse.ArgumentParser(description="Paper-ready ONE figure overlay for ALL envs + both sections.")
    ap.add_argument("--root", required=True, help="Root directory, e.g. results/out")
    ap.add_argument("--out-dir", default="results/combined_pics", help="Output directory")
    ap.add_argument("--out", default=None, help="Output PNG path (overrides --out-dir)")

    # ---------------- UPDATED: mode includes ecdf_diff ----------------
    ap.add_argument("--mode", choices=["ecdf", "hist", "ecdf_diff"], default="ecdf",
                    help="ecdf = best readability; hist = log-log histogram overlay; ecdf_diff = ECDF(section1-section2) per env")
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

    # ---------------- NEW: font controls ----------------
    ap.add_argument("--font", type=float, default=16, help="Base font size")
    ap.add_argument("--title-font", type=float, default=18, help="Title font size")
    ap.add_argument("--label-font", type=float, default=16, help="Axis label font size")
    ap.add_argument("--tick-font", type=float, default=14, help="Tick label font size")
    ap.add_argument("--legend-font", type=float, default=12, help="Legend font size")
    ap.add_argument("--legend-title-font", type=float, default=13, help="Legend title font size")

    # ---------------- NEW: ECDF pair arrows ----------------
    ap.add_argument("--pair-arrows", action="store_true",
                    help="ECDF mode: draw horizontal <-> arrows (median s1 <-> median s2) per env")
    ap.add_argument("--pair-arrow-text", action="store_true",
                    help="ECDF mode: also print env name above each pair arrow")
    ap.add_argument("--pair-arrow-y0", type=float, default=0.93,
                    help="ECDF mode: starting y for first arrow (0..1)")
    ap.add_argument("--pair-arrow-dy", type=float, default=0.05,
                    help="ECDF mode: y step per env for arrows")
    ap.add_argument("--pair-arrow-lw", type=float, default=2.8, help="Pair arrow line width")

    # ---------------- NEW: diff ECDF annotations ----------------
    ap.add_argument("--diff-curve-arrows", action="store_true",
                    help="ecdf_diff mode: add arrow+label pointing to each env curve")
    ap.add_argument("--diff-arrow-q", type=float, default=0.65,
                    help="ecdf_diff mode: quantile along curve to point at (0..1)")
    ap.add_argument("--debug", action="store_true", help="Print loading stats")

    args = ap.parse_args()

    # Apply font sizes
    plt.rcParams.update({
        "font.size": args.font,
        "axes.titlesize": args.title_font,
        "axes.labelsize": args.label_font,
        "xtick.labelsize": args.tick_font,
        "ytick.labelsize": args.tick_font,
    })

    root = Path(args.root).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        suffix = "ECDF" if args.mode == "ecdf" else ("HIST" if args.mode == "hist" else "ECDF_DIFF")
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

    if args.debug:
        print(f"[debug] envs={envs}")
        for env in envs:
            for sec in ("section1", "section2"):
                k = (env, sec)
                if k in series:
                    print(f"[debug] {env}/{sec}: {series[k].size} samples")

    # Choose x-range base on mode
    if args.mode in ("ecdf", "hist"):
        all_vals = np.concatenate(list(series.values()))
    else:
        # diff mode: build a pool of diffs to set scale robustly
        diffs_pool = []
        for env in envs:
            k1, k2 = (env, "section1"), (env, "section2")
            if k1 not in series or k2 not in series:
                continue
            a = series[k1]
            b = series[k2]
            m = min(a.size, b.size)
            if m <= 0:
                continue
            diffs_pool.append(a[:m] - b[:m])
        if not diffs_pool:
            raise SystemExit("ecdf_diff: need both section1 and section2 for at least one env.")
        all_vals = np.concatenate(diffs_pool)

    if args.no_robust:
        lo, hi = float(np.min(all_vals)), float(np.max(all_vals))
        robust_used = False
    else:
        lo, hi = robust_range(all_vals, args.robust[0], args.robust[1])
        robust_used = True

    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        raise SystemExit("Bad x-range (lo/hi).")

    # xscale decision
    if args.xscale == "linear":
        use_logx = False
    elif args.xscale == "log":
        use_logx = True
    else:
        use_logx = should_logx(lo, hi)

    plt.figure(figsize=(13.5, 6.8))
    plt.grid(True, which="both", linestyle=":", linewidth=0.6, alpha=0.6)

    if args.mode == "ecdf":
        # Draw curves
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

        # Pair arrows (median s1 <-> median s2)
        if args.pair_arrows:
            ax = plt.gca()
            for i, env in enumerate(envs):
                k1, k2 = (env, "section1"), (env, "section2")
                if k1 not in series or k2 not in series:
                    continue
                a = series[k1]
                b = series[k2]
                if robust_used:
                    a = a[(a >= lo) & (a <= hi)]
                    b = b[(b >= lo) & (b <= hi)]
                if a.size == 0 or b.size == 0:
                    continue
                x1 = float(np.median(a))
                x2 = float(np.median(b))
                y_pos = args.pair_arrow_y0 - i * args.pair_arrow_dy
                if y_pos <= 0.02:
                    break
                label = env if args.pair_arrow_text else None
                add_pair_arrow(ax, x1, x2, y_pos, env_color[env], label=label,
                               lw=args.pair_arrow_lw, text_size=args.legend_font)

        if use_logx:
            plt.xscale("log")
        plt.ylim(0.0, 1.0)
        plt.xlabel("cycles")
        plt.ylabel("ECDF")
        rr_note = f"robust={args.robust[0]:g}-{args.robust[1]:g}%" if robust_used else "robust=off"
        x_note = "logx" if use_logx else "linearx"
        plt.title(f"ALL envs + sections | ECDF | {x_note}, {rr_note}")

        add_legends(
            envs, env_color, section_style, args.legend,
            env_font=args.legend_font, env_title_font=args.legend_title_font,
            sec_font=args.legend_font, sec_title_font=args.legend_title_font
        )

    elif args.mode == "hist":
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

        add_legends(
            envs, env_color, section_style, args.legend,
            env_font=args.legend_font, env_title_font=args.legend_title_font,
            sec_font=args.legend_font, sec_title_font=args.legend_title_font
        )

    else:
        # ecdf_diff: for each env compute diff = section1 - section2 (paired by index, min length)
        ax = plt.gca()
        diffs_by_env = {}
        for env in envs:
            k1, k2 = (env, "section1"), (env, "section2")
            if k1 not in series or k2 not in series:
                continue
            a = series[k1]
            b = series[k2]
            m = min(a.size, b.size)
            if m <= 0:
                continue
            diff = a[:m] - b[:m]
            if robust_used:
                diff = diff[(diff >= lo) & (diff <= hi)]
            if diff.size == 0:
                continue
            diffs_by_env[env] = diff

        if not diffs_by_env:
            raise SystemExit("ecdf_diff: no diffs to plot after filtering.")

        for env in envs:
            if env not in diffs_by_env:
                continue
            x, y = compute_ecdf(diffs_by_env[env])
            plt.plot(
                x, y,
                color=env_color[env],
                linestyle="-",
                linewidth=args.linewidth,
                alpha=args.alpha
            )
            if args.diff_curve_arrows:
                add_curve_arrow(ax, x, y, env_color[env], env, q=args.diff_arrow_q,
                                lw=2.4, text_size=args.legend_font)

        if use_logx:
            plt.xscale("log")

        plt.ylim(0.0, 1.0)
        plt.xlabel("cycle diff (section1 - section2)")
        plt.ylabel("ECDF")
        rr_note = f"robust={args.robust[0]:g}-{args.robust[1]:g}%" if robust_used else "robust=off"
        x_note = "logx" if use_logx else "linearx"
        plt.title(f"ALL envs | ECDF of diffs (section1-section2) | {x_note}, {rr_note}")

        # Only env legend needed (no section styles)
        # Reuse existing legend maker but it will still show section legend; OK, but you can keep it.
        add_legends(
            envs, env_color, section_style, args.legend,
            env_font=args.legend_font, env_title_font=args.legend_title_font,
            sec_font=args.legend_font, sec_title_font=args.legend_title_font
        )

    plt.tight_layout()
    plt.savefig(out_path, dpi=280, bbox_inches="tight")
    plt.close()
    print(f"[OK] wrote {out_path}")


if __name__ == "__main__":
    main()