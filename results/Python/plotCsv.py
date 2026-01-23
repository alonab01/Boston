#!/usr/bin/env python3
import argparse
import numpy as np
import matplotlib.pyplot as plt

def load_two_column_file(path):
    # First line is header: "Page 1, Page 0"
    data = np.loadtxt(path, delimiter=",", skiprows=1)
    if data.ndim != 2 or data.shape[1] != 2:
        raise ValueError(f"Expected 2 columns, got shape {data.shape}")
    # Column order matches your file: "Page 1, Page 0"
    page1 = data[:, 0]
    page0 = data[:, 1]
    return page0, page1

def compute_stats(page0, page1):
    diff = page0 - page1

    mean0 = np.mean(page0)
    std0  = np.std(page0, ddof=1)

    mean1 = np.mean(page1)
    std1  = np.std(page1, ddof=1)

    meand = np.mean(diff)
    stdd  = np.std(diff, ddof=1)

    return (mean0, std0), (mean1, std1), (meand, stdd)

def compute_extents(page0, page1):
    diff = page0 - page1
    return (
        (float(np.min(page0)), float(np.max(page0))),
        (float(np.min(page1)), float(np.max(page1))),
        (float(np.min(diff)),  float(np.max(diff))),
    )

def plot_bars(stats0, stats1, statsd, extents, title, out):
    mean0, std0 = stats0
    mean1, std1 = stats1
    meand, stdd = statsd

    values = [mean0, mean1, meand]
    errors = [std0, std1, stdd]
    labels = ["Page 0", "Page 1", "Diff"]

    x = np.arange(len(labels))

    plt.figure()
    bars = plt.bar(x, values, yerr=errors, capsize=5)
    plt.xticks(x, labels)
    plt.ylabel("Cycles")
    plt.title(title)

    (min0, max0), (min1, max1), (mind, maxd) = extents
    mins = [min0, min1, mind]
    maxs = [max0, max1, maxd]

    first_min = True
    first_max = True
    for xi, bar, ymin, ymax in zip(x, bars, mins, maxs):
        color = bar.get_facecolor()
        plt.scatter([xi], [ymin], marker="v", color=color, zorder=3,
                    label="min" if first_min else None)
        plt.scatter([xi], [ymax], marker="^", color=color, zorder=3,
                    label="max" if first_max else None)
        first_min = False
        first_max = False

    plt.tight_layout()
    plt.savefig(out, dpi=300)
    print(f"Saved {out}")

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("csv", help="CSV/text file like qemu_p*_50_results.txt")
    p.add_argument("--title", default="Cycles", help="Plot title")
    p.add_argument("--out", default="plot.png", help="Output filename")
    return p.parse_args()

def main():
    args = parse_args()
    page0, page1 = load_two_column_file(args.csv)
    stats0, stats1, statsd = compute_stats(page0, page1)
    extents = compute_extents(page0, page1)

    print("Page 0: mean = %.3f, std = %.3f" % stats0)
    print("Page 1: mean = %.3f, std = %.3f" % stats1)
    print("Diff  : mean = %.3f, std = %.3f" % statsd)

    plot_bars(stats0, stats1, statsd, extents, args.title, args.out)

if __name__ == "__main__":
    main()