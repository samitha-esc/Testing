"""Figure set: frame-rate / throughput (#2).

Reads results/data/profile.csv and produces:
  - fps_hist.png        : distribution of loop frame-rate
  - fps_timeseries.png  : fps over time, shaded by tracking state
  - fps_vs_tracking.png : fps when fully tracked vs partially/lost
                          (quantifies the hybrid fast-path benefit)

The 'fps' column is the loop's EMA-smoothed rate. We also derive the
compute-bound ceiling (1000 / sum of stage times) for comparison.
"""
import numpy as np
from common import load_profile, save, C, plt


def main():
    d = load_profile()
    fps = d["fps"]
    n = d["n_markers"]
    compute_ms = d["t_capture_ms"] + d["t_hsv_ms"] + d["t_search_ms"] + d["t_map_ms"]
    ceiling = 1000.0 / np.clip(compute_ms, 1e-6, None)

    # warm-up: drop first 30 frames where the EMA is still settling
    warm = slice(30, None)

    print("\nFrame-rate summary:")
    print(f"  achieved fps : mean={fps[warm].mean():.1f}  "
          f"median={np.median(fps[warm]):.1f}  min={fps[warm].min():.1f}")
    print(f"  compute ceil : mean={ceiling[warm].mean():.1f} fps "
          f"(={compute_ms[warm].mean():.2f} ms/frame compute)")

    # --- Fig 1: fps histogram --------------------------------------------
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.hist(fps[warm], bins=40, color=C["capture"], alpha=0.85,
            edgecolor="white")
    ax.axvline(np.median(fps[warm]), color=C["search"], linestyle="--",
               linewidth=2, label=f"median = {np.median(fps[warm]):.0f} fps")
    ax.set_xlabel("Loop frame-rate (fps)")
    ax.set_ylabel("Frame count")
    ax.set_title("Throughput distribution")
    ax.legend()
    save(fig, "fps_hist.png")

    # --- Fig 2: fps time-series shaded by tracking ------------------------
    fig, ax = plt.subplots(figsize=(8, 4))
    frames = d["frame"]
    ax.plot(frames, fps, color=C["capture"], linewidth=1.0, label="achieved fps")
    ax.plot(frames, ceiling, color=C["search"], linewidth=0.8, alpha=0.5,
            label="compute-bound ceiling")
    # shade where all 3 markers tracked (fast path)
    tracked = n >= 3
    ax.fill_between(frames, 0, fps.max() * 1.05, where=tracked,
                    color=C["tier1"], alpha=0.12, step="mid",
                    label="all 3 markers tracked")
    ax.set_xlabel("Frame index")
    ax.set_ylabel("Frame-rate (fps)")
    ax.set_ylim(0, fps.max() * 1.1)
    ax.set_title("Frame-rate over time vs tracking state")
    ax.legend(loc="lower right", fontsize=9)
    save(fig, "fps_timeseries.png")

    # --- Fig 3: fps grouped by tracking state -----------------------------
    groups = {
        "All 3 tracked\n(fast path)": fps[(n >= 3)],
        "1-2 tracked": fps[(n >= 1) & (n < 3)],
        "0 tracked\n(full-frame hunt)": fps[(n == 0)],
    }
    groups = {k: v for k, v in groups.items() if len(v) > 5}
    if len(groups) >= 2:
        fig, ax = plt.subplots(figsize=(6.5, 4))
        bp = ax.boxplot(list(groups.values()), patch_artist=True,
                        showfliers=False,
                        medianprops=dict(color="black", linewidth=1.5),
                        widths=0.55)
        pal = [C["tier1"], C["tier2"], C["tier3"]]
        for patch, col in zip(bp["boxes"], pal):
            patch.set_facecolor(col)
            patch.set_alpha(0.85)
        ax.set_xticklabels(list(groups.keys()))
        ax.set_ylabel("Frame-rate (fps)")
        ax.set_title("Throughput by tracking state")
        save(fig, "fps_vs_tracking.png")
    else:
        print("  (fps_vs_tracking skipped: not enough variety in tracking "
              "state — wave the glove in/out of frame during capture)")


if __name__ == "__main__":
    main()
