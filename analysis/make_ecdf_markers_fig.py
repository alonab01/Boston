#!/usr/bin/env python3
"""ECDF figure in the original ecdf_all_envs (8).pdf style, plus a distinct
marker per environment (circle / square / triangle / diamond / ...).

Encoding:
  - env      -> color (tab20) AND marker shape
  - section  -> linestyle (solid = cold, dashed = primed)

Layout matches the original: Section legend inside upper-left, Environment
legend outside center-right, base font 16, log x, robust 1-99% clip, and the
median cold<->primed pair arrows with env labels.

Usage:
    python analysis/make_ecdf_markers_fig.py --root results/out \
        --out results/figs_ecdf/ecdf_all_envs_markers.pdf
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# reuse the loader / helpers from the sibling script
sys.path.insert(0, str(Path(__file__).parent))
from make_ecdf_figs import (  # noqa: E402
    SECTION_LABELS, SECTION_STYLE,
    load_series, compute_ecdf, robust_range, should_logx,
    make_env_colors, add_pair_arrow,
)

# one distinct marker per env (sorted env order); 7 envs here
MARKERS = ["o", "s", "^", "D", "v", "P", "X"]

FONTS = dict(base=16, label=16, tick=14, legend=12, legend_title=13, arrow=12)


def render(series, out_path: Path, robust=(1.0, 99.0)):
    plt.rcParams.update({
        "font.size": FONTS["base"],
        "axes.labelsize": FONTS["label"],
        "xtick.labelsize": FONTS["tick"],
        "ytick.labelsize": FONTS["tick"],
    })

    envs = sorted({env for (env, _) in series})
    env_color = make_env_colors(envs)
    env_marker = {env: MARKERS[i % len(MARKERS)] for i, env in enumerate(envs)}

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
            ax.plot(
                x, y,
                color=env_color[env], linestyle=SECTION_STYLE[sec],
                linewidth=2.4, alpha=0.95,
                marker=env_marker[env], markevery=0.07,
                markersize=7, markeredgecolor="white", markeredgewidth=0.5,
            )

    # pair arrows: median cold <-> median primed (kept below top to avoid clipping)
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
                       label=env, lw=2.8, text_size=FONTS["arrow"])

    if use_logx:
        ax.set_xscale("log")
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel("# clock cycles")
    ax.set_ylabel("ECDF")

    # Section legend (linestyle) inside upper-left -> cold / primed
    sec_handles = [
        Line2D([], [], color="k", linestyle=SECTION_STYLE[s], linewidth=3.0,
               label=SECTION_LABELS[s])
        for s in ("section1", "section2")
    ]
    leg_sec = ax.legend(handles=sec_handles, title="Section", loc="upper left",
                        framealpha=0.95, fontsize=FONTS["legend"],
                        title_fontsize=FONTS["legend_title"])
    ax.add_artist(leg_sec)

    # Environment legend (color + marker) outside center-right
    env_handles = [
        Line2D([], [], color=env_color[env], linestyle="-", linewidth=2.4,
               marker=env_marker[env], markersize=8, markeredgecolor="white",
               markeredgewidth=0.5, label=env)
        for env in envs
    ]
    ax.legend(handles=env_handles, title="Environment", loc="center left",
              bbox_to_anchor=(1.01, 0.5), framealpha=0.95,
              fontsize=FONTS["legend"], title_fontsize=FONTS["legend_title"])

    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] wrote {out_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="results/out")
    ap.add_argument("--out", default="results/figs_ecdf/ecdf_all_envs_markers.pdf")
    args = ap.parse_args()

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    series = load_series(Path(args.root).expanduser().resolve())
    render(series, out_path)


if __name__ == "__main__":
    main()
