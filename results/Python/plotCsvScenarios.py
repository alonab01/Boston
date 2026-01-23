#!/usr/bin/env python3
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def load_csv_scenarios(path):
    """
    Load CSV with 4 scenarios:
    - Lines 1-200: no priming
    - Lines 201-400: priming file 0
    - Lines 401-600: priming file 1
    - Lines 601-800: priming both files
    
    Every 2 consecutive lines represent a measurement at the same time.
    Returns dict with keys: 'no_priming', 'prime_file0', 'prime_file1', 'prime_both'
    Each value is a dict with 'page0' and 'page1' arrays.
    """
    df = pd.read_csv(path)
    
    scenarios = {}
    scenario_names = ['no_priming', 'prime_file0', 'prime_file1', 'prime_both']
    
    for i, name in enumerate(scenario_names):
        start_idx = i * 200
        end_idx = start_idx + 200
        
        scenario_df = df.iloc[start_idx:end_idx]
        
        # Extract avg_cycles for file 0 (rand0.bin) and file 1 (rand1.bin)
        # Every 2 lines are a pair - lines are alternating rand0 and rand1
        page0_values = []
        page1_values = []
        
        for j in range(0, len(scenario_df), 2):
            if j + 1 < len(scenario_df):
                row0 = scenario_df.iloc[j]
                row1 = scenario_df.iloc[j + 1]
                
                # Assuming rand0.bin is always first, rand1.bin second
                if 'rand0' in row0['filename']:
                    page0_values.append(row0['avg_cycles'])
                    page1_values.append(row1['avg_cycles'])
                else:
                    page0_values.append(row1['avg_cycles'])
                    page1_values.append(row0['avg_cycles'])
        
        scenarios[name] = {
            'page0': np.array(page0_values),
            'page1': np.array(page1_values)
        }
    
    return scenarios

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

def plot_bars(stats0, stats1, statsd, extents, title, ax):
    mean0, std0 = stats0
    mean1, std1 = stats1
    meand, stdd = statsd

    values = [mean0, mean1, meand]
    errors = [std0, std1, stdd]
    labels = ["Page 0\n(rand0.bin)", "Page 1\n(rand1.bin)", "Diff\n(P0 - P1)"]

    x = np.arange(len(labels))

    bars = ax.bar(x, values, yerr=errors, capsize=5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Cycles")
    ax.set_title(title)
    ax.grid(True, alpha=0.3, axis='y')

    (min0, max0), (min1, max1), (mind, maxd) = extents
    mins = [min0, min1, mind]
    maxs = [max0, max1, maxd]

    for xi, bar, ymin, ymax in zip(x, bars, mins, maxs):
        ax.scatter([xi], [ymin], marker="v", color="red", zorder=3, s=50)
        ax.scatter([xi], [ymax], marker="^", color="darkgreen", zorder=3, s=50)

def parse_args():
    p = argparse.ArgumentParser(description="Plot CSV data with 4 priming scenarios")
    p.add_argument("csv", help="CSV file with scenario data")
    p.add_argument("--out", default="scenarios_plot.png", help="Output filename")
    return p.parse_args()

def main():
    args = parse_args()
    
    print(f"Loading scenarios from {args.csv}...")
    scenarios = load_csv_scenarios(args.csv)
    
    # Create 2x2 subplot
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Page Read Latency - Priming Scenarios", fontsize=16, fontweight='bold')
    
    scenario_titles = {
        'no_priming': "No Priming",
        'prime_file0': "Priming File 0",
        'prime_file1': "Priming File 1",
        'prime_both': "Priming Both Files"
    }
    
    positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
    scenario_order = ['no_priming', 'prime_file0', 'prime_file1', 'prime_both']
    
    for (row, col), scenario_name in zip(positions, scenario_order):
        data = scenarios[scenario_name]
        page0 = data['page0']
        page1 = data['page1']
        
        stats0, stats1, statsd = compute_stats(page0, page1)
        extents = compute_extents(page0, page1)
        
        print(f"\n{scenario_titles[scenario_name]}:")
        print(f"  Page 0: mean = {stats0[0]:.1f}, std = {stats0[1]:.1f}")
        print(f"  Page 1: mean = {stats1[0]:.1f}, std = {stats1[1]:.1f}")
        print(f"  Diff  : mean = {statsd[0]:.1f}, std = {statsd[1]:.1f}")
        print(f"  Page 0 range: [{extents[0][0]:.1f}, {extents[0][1]:.1f}]")
        print(f"  Page 1 range: [{extents[1][0]:.1f}, {extents[1][1]:.1f}]")
        print(f"  Diff  range: [{extents[2][0]:.1f}, {extents[2][1]:.1f}]")
        plot_bars(stats0, stats1, statsd, extents, 
                 scenario_titles[scenario_name], axes[row, col])
    
    plt.tight_layout()
    plt.savefig(args.out, dpi=300, bbox_inches='tight')
    print(f"\nSaved plot to {args.out}")
    
    # Create individual plots for scenarios 2 and 3 (prime_file0 and prime_file1)
    # First, compute global y-axis limits across both scenarios
    global_ymin = float('inf')
    global_ymax = float('-inf')
    
    for scenario_name in ['prime_file0', 'prime_file1']:
        data = scenarios[scenario_name]
        page0 = data['page0']
        page1 = data['page1']
        stats0, stats1, statsd = compute_stats(page0, page1)
        extents = compute_extents(page0, page1)
        
        # Consider all values: means +/- std and min/max
        all_values = [
            stats0[0] - stats0[1], stats0[0] + stats0[1], extents[0][0], extents[0][1],
            stats1[0] - stats1[1], stats1[0] + stats1[1], extents[1][0], extents[1][1],
            statsd[0] - statsd[1], statsd[0] + statsd[1], extents[2][0], extents[2][1]
        ]
        global_ymin = min(global_ymin, min(all_values))
        global_ymax = max(global_ymax, max(all_values))
    
    # Add some padding (5%)
    y_range = global_ymax - global_ymin
    global_ymin -= 0.05 * y_range
    global_ymax += 0.05 * y_range
    
    # Now create the individual plots with the same scale
    for scenario_name in ['prime_file0', 'prime_file1']:
        data = scenarios[scenario_name]
        page0 = data['page0']
        page1 = data['page1']
        
        stats0, stats1, statsd = compute_stats(page0, page1)
        extents = compute_extents(page0, page1)
        
        fig_single, ax_single = plt.subplots(1, 1, figsize=(8, 6))
        plot_bars(stats0, stats1, statsd, extents, 
                 scenario_titles[scenario_name], ax_single)
        
        # Set the same y-axis limits for both plots
        ax_single.set_ylim(global_ymin, global_ymax)
        
        # Generate output filename based on input
        base_name = args.out.rsplit('.', 1)[0]
        ext = args.out.rsplit('.', 1)[1] if '.' in args.out else 'png'
        single_out = f"{base_name}_{scenario_name}.{ext}"
        
        plt.tight_layout()
        plt.savefig(single_out, dpi=300, bbox_inches='tight')
        print(f"Saved individual plot to {single_out}")
        plt.close(fig_single)

if __name__ == "__main__":
    main()
