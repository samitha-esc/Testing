"""Figure set: search-tier usage (#3).

Reads results/data/profile.csv and produces:
  - tier_usage.png    : per-marker composition (% frames in each tier)
  - tier_timeline.png : tier of each marker over time (shows the engine
                        staying on the cheap continuity path once locked,
                        with MediaPipe only rescuing re-acquisition)

Tier codes (see engine_glove._find_marker):
  1 = continuity ROI (cheap, runs every frame once locked)
  2 = MediaPipe hint ROI (re-acquisition guide)
  3 = full-frame search (expensive cold-start / loss)
  0 = lost (not found this frame)
"""
import numpy as np
from common import load_profile, save, C, plt

MARKERS = ["wrist", "thumb", "index"]
TIER_ORDER = [1, 2, 3, 0]
TIER_NAME = {1: "Tier 1: continuity ROI", 2: "Tier 2: MediaPipe hint",
             3: "Tier 3: full-frame", 0: "Lost"}
TIER_COL = {1: C["tier1"], 2: C["tier2"], 3: C["tier3"], 0: C["tier0"]}


def main():
    d = load_profile()
    tiers = {m: d[f"tier_{m}"].astype(int) for m in MARKERS}
    nframes = len(d["frame"])

    print("\nSearch-tier usage (% of frames):")
    frac = {}
    for m in MARKERS:
        frac[m] = {t: 100.0 * np.mean(tiers[m] == t) for t in TIER_ORDER}
        print(f"  {m:6s}: " + "  ".join(
            f"T{t}={frac[m][t]:5.1f}%" if t else f"lost={frac[m][t]:5.1f}%"
            for t in TIER_ORDER))

    # --- Fig 1: stacked composition bar per marker ------------------------
    fig, ax = plt.subplots(figsize=(7, 4))
    bottoms = np.zeros(len(MARKERS))
    x = np.arange(len(MARKERS))
    for t in TIER_ORDER:
        vals = np.array([frac[m][t] for m in MARKERS])
        ax.bar(x, vals, bottom=bottoms, color=TIER_COL[t],
               edgecolor="white", label=TIER_NAME[t])
        for xi, (v, b) in enumerate(zip(vals, bottoms)):
            if v > 4:
                ax.text(xi, b + v / 2, f"{v:.0f}%", ha="center", va="center",
                        color="white", fontsize=9, fontweight="bold")
        bottoms += vals
    ax.set_xticks(x)
    ax.set_xticklabels([m.capitalize() for m in MARKERS])
    ax.set_ylabel("Share of frames (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Which search tier resolved each marker")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2,
              fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    save(fig, "tier_usage.png")

    # --- Fig 2: tier timeline per marker ----------------------------------
    fig, axes = plt.subplots(len(MARKERS), 1, figsize=(8, 4.5), sharex=True)
    frames = d["frame"]
    for ax, m in zip(axes, MARKERS):
        tarr = tiers[m]
        for t in TIER_ORDER:
            mask = tarr == t
            ax.scatter(frames[mask], np.full(mask.sum(), t),
                       s=4, color=TIER_COL[t], marker="s")
        ax.set_yticks(TIER_ORDER)
        ax.set_yticklabels(["T1", "T2", "T3", "lost"])
        ax.set_ylabel(m.capitalize(), rotation=0, ha="right", va="center")
        ax.set_ylim(-0.5, 3.5)
        ax.grid(axis="x", alpha=0.2)
    axes[-1].set_xlabel("Frame index")
    axes[0].set_title("Search tier per marker over time")
    save(fig, "tier_timeline.png")


if __name__ == "__main__":
    main()
