"""Figure: calibrated marker separation in HSV space (#12).

Reads the calibration JSON (results/data/glove_colors.json, pulled from the
Pi) and plots each marker's accepted Hue-Saturation rectangle plus its mean,
showing the three markers occupy well-separated colour regions. Also draws
the hue number line. Falls back to the engine's default colours if no
calibration file is present, so the figure is always producible.

OpenCV HSV ranges: H in [0,179], S/V in [0,255]. Red wraps around H=0.
"""
import os
import json
import numpy as np
from matplotlib.patches import Rectangle
from common import DATA, RESULTS, save, C, plt

# Engine default ranges (lower/upper as [H,S,V]); used only as a fallback.
DEFAULTS = {
    "wrist": ([20, 100, 100], [35, 255, 255]),
    "thumb": ([0, 120, 100], [15, 255, 255]),
    "index": ([100, 100, 100], [130, 255, 255]),
}
MARK_COL = {"wrist": C["wrist"], "thumb": C["thumb"], "index": C["index"]}


def load_colors():
    """Return {marker: (lower, upper, mean_or_None)} and a source label."""
    candidates = [
        os.path.join(DATA, "glove_colors.json"),
        os.path.join(RESULTS, "..", "config", "glove_colors.json"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path) as f:
                cc = json.load(f).get("calibrated_colors", {})
            out = {}
            for m, r in cc.items():
                out[m] = (r["lower"], r["upper"], r.get("mean"))
            if out:
                return out, f"calibrated ({os.path.basename(path)})"
    return ({m: (lo, hi, None) for m, (lo, hi) in DEFAULTS.items()},
            "engine defaults (no calibration file found)")


def main():
    colors, source = load_colors()
    print(f"\nHSV clusters from: {source}")

    fig, (ax, axh) = plt.subplots(
        2, 1, figsize=(7, 5.2), gridspec_kw={"height_ratios": [5, 1]})

    for m, (lo, hi, mean) in colors.items():
        col = MARK_COL.get(m, "#555")
        h_lo, s_lo = lo[0], lo[1]
        h_hi, s_hi = hi[0], hi[1]
        # Handle red hue-wrap (lower H > upper H) by drawing two boxes.
        spans = ([(h_lo, 179), (0, h_hi)] if h_lo > h_hi else [(h_lo, h_hi)])
        for i, (a, b) in enumerate(spans):
            ax.add_patch(Rectangle((a, s_lo), b - a, s_hi - s_lo,
                                   facecolor=col, alpha=0.30, edgecolor=col,
                                   linewidth=1.8,
                                   label=(m.capitalize() if i == 0 else None)))
            axh.add_patch(Rectangle((a, 0), b - a, 1, facecolor=col, alpha=0.6))
        if mean:
            ax.plot(mean[0], mean[1], "o", color=col, markersize=9,
                    markeredgecolor="black", zorder=5)
            ax.annotate(f"  {m}\n  H={mean[0]} S={mean[1]}",
                        (mean[0], mean[1]), fontsize=8, color="black")

    ax.set_xlim(0, 179)
    ax.set_ylim(0, 255)
    ax.set_xlabel("Hue (OpenCV, 0–179)")
    ax.set_ylabel("Saturation (0–255)")
    ax.set_title("Calibrated marker separation in Hue–Saturation space")
    ax.legend(loc="lower right")

    axh.set_xlim(0, 179)
    axh.set_ylim(0, 1)
    axh.set_yticks([])
    axh.set_xlabel("Hue band coverage")
    axh.grid(False)

    save(fig, "hsv_clusters.png")


if __name__ == "__main__":
    main()
