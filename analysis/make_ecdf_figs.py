#!/usr/bin/env python3
"""Render the ALL-envs ECDF figure (docker/gvisor/kata/qemu, both sections) as PDFs.

Reproduces the look of ecdf_all_envs (8).pdf:
  - tab20 env palette (stable, sorted env order)
  - section shown via linestyle (solid vs dashed)
  - horizontal <-> pair arrows (median cold <-> median primed) with env label
  - outside legends: "Section" (linestyle) and "Environment" (color)
  - log x-axis, robust 1-99% clip

Changes requested:
  - the upper (Section) legend now reads "cold" / "primed" instead of
    section1 / section2  (section1 == first/cold read, section2 == primed read)
  - several font-size variants are rendered so the best one can be picked
  - outputs are PDFs written to a dedicated folder

Usage:
    python analysis/make_ecdf_figs.py --root results/out --out-dir results/figs_ecdf
"""
import argparse
import math
import re
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt


# section1 = fresh/cold read; section2 = read of a page already primed by peer
SECTION_LABELS = {"section1": "cold", "section2": "primed"}
SECTION_STYLE = {"section1": "-", "section2": "--"}


# ---------------- data loading (same logic as one_big_figure_v2.py) ----------------

def read_cycles_even_rows(csv_path: Path) -> np.ndarray:
    """Parse cycles; keep only even-indexed samples (2,4,6,... in 1-based)."""
    lines = csv_path.read_text(errors="ignore").splitlines()
    if lines and lines[-1].strip().startswith("SUMMARY"):
        lines = lines[:-1]

    data_cycles = []
    for ln in lines:
        ln = ln.strip()
        if not ln or re.match(r"^[A-Za-z]", ln):
            continue
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) < 2 or not re.match(r"^\d+$", parts[0]):
            continue
        try:
            data_cycles.append(float(parts[1]))
        except ValueError:
            continue

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


def robust_range(vals, lo_p, hi_p):
    return float(np.percentile(vals, lo_p)), float(np.percentile(vals, hi_p))


def should_logx(lo, hi):
    eps = 1e-12
    lo_safe = max(float(lo), eps)
    hi_safe = max(float(hi), lo_safe + eps)
    return (hi_safe / lo_safe) >= 30.0


def make_env_colors(envs):
    cmap = plt.get_cmap("tab20")
    return {env: cmap(i % cmap.N) for i, env in enumerate(envs)}


# ---------------- annotations ----------------

def _geom_mid(x1, x2):
    if x1 > 0 and x2 > 0:
        return math.sqrt(x1 * x2)
    return 0.5 * (x1 + x2)


def add_pair_arrow(ax, x1, x2, y, color, label, lw, text_size, small_gap_rel=0.04):
    x1, x2 = float(x1), float(x2)
    lo, hi = min(x1, x2), max(x1, x2)
    rel_gap = (hi - lo) / max(lo, 1e-12)
    xm = _geom_mid(x1, x2)

    if rel_gap < small_gap_rel:
        ax.annotate("", xy=(xm, y), xytext=(lo, y),
                    arrowprops=dict(arrowstyle="->", color=color, lw=lw),
                    annotation_clip=False)
    else:
        ax.annotate("", xy=(x1, y), xytext=(x2, y),
                    arrowprops=dict(arrowstyle="<->", color=color, lw=lw),
                    annotation_clip=False)
    if label:
        ax.text(xm, min(0.995, y + 0.02), label, color=color, ha="center",
                va="bottom", fontsize=text_size, fontweight="bold", clip_on=False)


def add_legends(ax, envs, env_color, fonts):
    # Both legends sit OUTSIDE on the right, stacked: Section above Environment.
    # Section legend (linestyle) -> cold / primed
    sec_handles = [
        ax.plot([], [], color="k", linestyle=SECTION_STYLE[s], linewidth=3.0,
                label=SECTION_LABELS[s])[0]
        for s in ("section1", "section2")
    ]
    leg_sec = ax.legend(handles=sec_handles, title="Section", loc="upper left",
                        bbox_to_anchor=(1.01, 1.0), framealpha=0.95,
                        fontsize=fonts["legend"], title_fontsize=fonts["legend_title"])
    ax.add_artist(leg_sec)

    # Environment legend (color), directly below the Section legend
    env_handles = [
        ax.plot([], [], color=env_color[env], linestyle="-", linewidth=3.2,
                label=env)[0]
        for env in envs
    ]
    ax.legend(handles=env_handles, title="Environment", loc="upper left",
              bbox_to_anchor=(1.01, fonts["env_leg_y"]), framealpha=0.95,
              fontsize=fonts["legend"], title_fontsize=fonts["legend_title"])


# ---------------- figure ----------------

def load_series(root: Path):
    csvs = sorted(root.rglob("*.csv"))
    if not csvs:
        raise SystemExit(f"No CSV files found under: {root}")
    buckets = defaultdict(list)
    for p in csvs:
        sec = section_from_name(p)
        if sec not in ("section1", "section2"):
            continue
        arr = read_cycles_even_rows(p)
        if arr.size:
            buckets[(env_from_path(p, root), sec)].append(arr)
    series = {k: np.concatenate(v) for k, v in buckets.items() if v}
    if not series:
        raise SystemExit("No usable data (need section1_/section2_ filenames).")
    return series


def render(series, out_path: Path, fonts, robust=(1.0, 99.0)):
    plt.rcParams.update({
        "font.size": fonts["base"],
        "axes.labelsize": fonts["label"],
        "xtick.labelsize": fonts["tick"],
        "ytick.labelsize": fonts["tick"],
    })

    envs = sorted({env for (env, _) in series})
    env_color = make_env_colors(envs)

    all_vals = np.concatenate(list(series.values()))
    lo, hi = robust_range(all_vals, *robust)
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        raise SystemExit("Bad x-range (lo/hi).")
    use_logx = should_logx(lo, hi)

    fig = plt.figure(figsize=(13.5, 6.8))
    ax = plt.gca()
    ax.grid(True, which="both", linestyle=":", linewidth=0.6, alpha=0.6)

    for env in envs:
        for sec in ("section1", "section2"):
            key = (env, sec)
            if key not in series:
                continue
            arr = series[key]
            arr = arr[(arr >= lo) & (arr <= hi)]
            if arr.size == 0:
                continue
            x, y = compute_ecdf(arr)
            ax.plot(x, y, color=env_color[env], linestyle=SECTION_STYLE[sec],
                    linewidth=2.4, alpha=0.95)

    # pair arrows: median cold <-> median primed
    # wider vertical step so the env labels above each arrow don't overlap
    y0, dy = 0.93, 0.075
    for i, env in enumerate(envs):
        k1, k2 = (env, "section1"), (env, "section2")
        if k1 not in series or k2 not in series:
            continue
        a = series[k1]; a = a[(a >= lo) & (a <= hi)]
        b = series[k2]; b = b[(b >= lo) & (b <= hi)]
        if a.size == 0 or b.size == 0:
            continue
        y_pos = y0 - i * dy
        if y_pos <= 0.02:
            break
        add_pair_arrow(ax, np.median(a), np.median(b), y_pos, env_color[env],
                       label=env, lw=2.8, text_size=fonts["arrow"])

    if use_logx:
        ax.set_xscale("log")
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel("# clock cycles")
    ax.set_ylabel("ECDF")

    add_legends(ax, envs, env_color, fonts)

    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] wrote {out_path}")


# Font-size variants (base sizes; others scale with it). Pick your favourite.
# env_leg_y = top of the Environment legend (axis fraction), placed just below
# the Section legend; larger fonts make the Section box taller so it sits lower.
VARIANTS = {
    "M":   dict(base=16, label=16, tick=14, legend=12, legend_title=13, arrow=12, env_leg_y=0.80),
    "L":   dict(base=20, label=21, tick=18, legend=16, legend_title=17, arrow=15, env_leg_y=0.76),
    "XL":  dict(base=24, label=25, tick=21, legend=19, legend_title=20, arrow=18, env_leg_y=0.73),
    "XXL": dict(base=28, label=30, tick=25, legend=22, legend_title=24, arrow=21, env_leg_y=0.70),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="results/out", help="Root dir with env subfolders")
    ap.add_argument("--out-dir", default="results/figs_ecdf", help="Output folder for PDFs")
    ap.add_argument("--variants", nargs="*", default=list(VARIANTS),
                    help="Which font variants to render (default: all)")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    series = load_series(root)
    for name in args.variants:
        if name not in VARIANTS:
            raise SystemExit(f"Unknown variant '{name}'. Choices: {list(VARIANTS)}")
        render(series, out_dir / f"ecdf_all_envs_{name}.pdf", VARIANTS[name])


if __name__ == "__main__":
    main()
