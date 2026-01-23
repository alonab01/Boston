#!/usr/bin/env python3
import argparse
import numpy as np
import matplotlib.pyplot as plt

def load_two_column_file(path):
    # Skip the first line (header like "Page 1, Page 0")
    data = np.loadtxt(path, delimiter=",", skiprows=1)
    # Ensure we have exactly two columns
    if data.ndim == 1:
        raise ValueError("Expected two columns of data.")
    col0 = data[:, 0]
    col1 = data[:, 1]
    return col0, col1

def main():
    parser = argparse.ArgumentParser(
        description="Plot two-column results and their difference."
    )
    parser.add_argument(
        "file",
        help="Path to CSV/text file with two numeric columns (comma-separated).",
    )
    args = parser.parse_args()

    col0, col1 = load_two_column_file(args.file)
    diff = col0 - col1

    # Compute statistics
    stats = {
        "col0_mean": np.mean(col0),
        "col0_std": np.std(col0, ddof=1),
        "col1_mean": np.mean(col1),
        "col1_std": np.std(col1, ddof=1),
        "diff_mean": np.mean(diff),
        "diff_std": np.std(diff, ddof=1),
    }

    print("Statistics:")
    print(f"  Col 0 mean:  {stats['col0_mean']:.3f}")
    print(f"  Col 0 std:   {stats['col0_std']:.3f}")
    print(f"  Col 1 mean:  {stats['col1_mean']:.3f}")
    print(f"  Col 1 std:   {stats['col1_std']:.3f}")
    print(f"  Diff mean:   {stats['diff_mean']:.3f}")
    print(f"  Diff std:    {stats['diff_std']:.3f}")

    # Simple plot: each sample index vs values
    x = np.arange(len(col0))

    # Histogram plot
    plt.figure(figsize=(8, 5))

    bins = 20  # adjust if you want more/less granularity

    plt.hist(col0, bins=bins, alpha=0.5, label="t page 1")
    plt.hist(col1, bins=bins, alpha=0.5, label="t page 0")
    plt.hist(diff, bins=bins, alpha=0.5, label="delta (t page 1 - t page 0)")

    plt.xlabel("Value")
    plt.ylabel("Count")
    plt.title("Histogram of Values and Difference")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
    
    #save plot
    plt.savefig("plot.png")

if __name__ == "__main__":
    main()