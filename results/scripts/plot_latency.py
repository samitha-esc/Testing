"""Figure set: end-to-end pipeline latency (#1).

Reads results/data/profile.csv and produces:
  - latency_breakdown.png : stacked bar, mean contribution of each stage
  - latency_box.png       : per-stage + total latency distributions (box)
  - latency_cdf.png       : CDF of total per-frame compute latency w/ p50/95/99

The four instrumented stages are:
  capture  - cam.get_frame()           (sensor + libcamera + V4L2)
  hsv      - resize + BGR->HSV          (engine pre-processing)
  search   - 3-tier marker search       (the tracking core)
  map      - gesture -> MIDI mapping    (incl. MIDI send)
"""
import numpy as np
from common import load_profile, save, C, plt, stats_line

STAGES = ["capture", "hsv", "search", "map"]
LABELS = {"capture": "Capture", "hsv": "HSV pre-proc",
          "search": "Marker search", "map": "Mapping + MIDI"}


def main():
    d = load_profile()
    stage = {s: d[f"t_{s}_ms"] for s in STAGES}
    total = sum(stage.values())

    print("\nLatency summary (ms):")
    for s in STAGES:
        print("  " + stats_line(LABELS[s], stage[s]))
    print("  " + stats_line("TOTAL pipeline", total))

    # --- Fig 1: stacked mean-contribution bar -----------------------------
    fig, ax = plt.subplots(figsize=(7, 1.9))
    left = 0.0
    for s in STAGES:
        m = stage[s].mean()
        ax.barh(0, m, left=left, color=C[s], edgecolor="white",
                label=f"{LABELS[s]} ({m:.2f} ms)")
        if m > 0.04 * total.mean():
            ax.text(left + m / 2, 0, f"{m:.2f}", ha="center", va="center",
                    color="white", fontsize=9, fontweight="bold")
        left += m
    ax.set_xlim(0, left * 1.02)
    ax.set_yticks([])
    ax.set_xlabel("Mean per-frame latency (ms)")
    ax.set_title(f"Pipeline latency breakdown  (total ≈ {left:.2f} ms / frame)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.55),
              ncol=2, fontsize=9)
    ax.grid(axis="x", alpha=0.3)
    save(fig, "latency_breakdown.png")

    # --- Fig 2: per-stage + total distribution boxes ----------------------
    fig, ax = plt.subplots(figsize=(7, 4))
    data = [stage[s] for s in STAGES] + [total]
    labels = [LABELS[s] for s in STAGES] + ["TOTAL"]
    colors = [C[s] for s in STAGES] + [C["total"]]
    bp = ax.boxplot(data, vert=True, patch_artist=True, showfliers=False,
                    medianprops=dict(color="black", linewidth=1.5),
                    widths=0.6)
    for patch, col in zip(bp["boxes"], colors):
        patch.set_facecolor(col)
        patch.set_alpha(0.85)
    ax.set_xticklabels(labels, rotation=15)
    ax.set_ylabel("Latency per frame (ms)")
    ax.set_title("Per-stage latency distribution")
    save(fig, "latency_box.png")

    # --- Fig 3: CDF of total compute latency ------------------------------
    fig, ax = plt.subplots(figsize=(6.5, 4))
    xs = np.sort(total)
    ys = np.linspace(0, 1, len(xs))
    ax.plot(xs, ys, color=C["total"], linewidth=2)
    for p, style in [(50, ":"), (95, "--"), (99, "-.")]:
        v = np.percentile(total, p)
        ax.axvline(v, color=C["search"], linestyle=style, alpha=0.8,
                   label=f"p{p} = {v:.2f} ms")
    ax.set_xlabel("Total pipeline latency per frame (ms)")
    ax.set_ylabel("Cumulative probability")
    ax.set_title("CDF of end-to-end compute latency")
    ax.set_ylim(0, 1.0)
    ax.legend(loc="lower right")
    save(fig, "latency_cdf.png")


if __name__ == "__main__":
    main()
