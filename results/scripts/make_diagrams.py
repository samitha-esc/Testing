"""Figure set: system diagrams (#8-10), drawn with matplotlib patches.

  - architecture.png    : data-flow from sensors to DAW (gesture + hardware)
  - threading.png       : main loop + MediaPipe background worker
  - search_flowchart.png: the 3-tier marker search decision flow

Pure layout code, no measured data. Editable for the camera-ready paper.
"""
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from common import save, C, plt


def box(ax, xy, w, h, text, fc, tc="white", fs=10):
    x, y = xy
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
        linewidth=1.2, edgecolor="#222", facecolor=fc, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            color=tc, fontsize=fs, fontweight="bold", zorder=3, wrap=True)
    return (x, y, w, h)


def arrow(ax, p1, p2, color="#333", style="-|>", label=None, rad=0.0):
    ax.add_patch(FancyArrowPatch(
        p1, p2, arrowstyle=style, mutation_scale=14, linewidth=1.5,
        color=color, connectionstyle=f"arc3,rad={rad}", zorder=1))
    if label:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        ax.text(mx, my + 0.12, label, ha="center", fontsize=8, color=color)


def architecture():
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)
    ax.axis("off")
    ax.set_title("System architecture: gesture & hardware → MIDI → DAW",
                 fontsize=12, fontweight="bold")

    # Gesture pipeline (top row)
    cam = box(ax, (0.3, 4.6), 2.1, 1.1,
              "CSI Camera\n(ov5647)\nlibcamerify", C["capture"])
    eng = box(ax, (3.0, 4.6), 2.4, 1.1,
              "GloveEngine\nHSV + MediaPipe\nhybrid tracker", C["hsv"])
    mapp = box(ax, (6.1, 4.6), 2.3, 1.1,
               "MappingEngine\ngesture → CC\n(per-mode)", C["map"])
    # Hardware pipeline (bottom row)
    hw = box(ax, (0.3, 1.0), 2.1, 1.4,
             "C++ controller\nkeys / buttons\nLEDs / LCD\n(pigpio)", "#555")
    # Convergence
    gadget = box(ax, (9.0, 2.9), 2.6, 1.1,
                 "f_midi USB\ngadget\n(ALSA seq)", C["search"])
    daw = box(ax, (9.0, 0.9), 2.6, 1.1, "DAW\n(Waveform)\n4OSC / plugins",
              C["total"])

    arrow(ax, (2.4, 5.15), (3.0, 5.15), label="frame")
    arrow(ax, (5.4, 5.15), (6.1, 5.15), label="gestures")
    arrow(ax, (8.4, 5.05), (10.3, 4.0), color=C["map"], label="CC msgs")
    arrow(ax, (2.4, 1.7), (10.3, 3.0), color="#555", label="note on/off")
    arrow(ax, (10.3, 2.9), (10.3, 2.0), color=C["search"], label="USB")
    ax.text(6, 6.4, "Raspberry Pi 4B (Debian Trixie, venv311)",
            ha="center", fontsize=9, style="italic", color="#444")
    ax.add_patch(FancyBboxPatch((0.1, 0.5), 8.6, 5.7,
                 boxstyle="round,pad=0.1", fill=False, linestyle="--",
                 edgecolor="#999", linewidth=1.0))
    save(fig, "architecture.png")


def threading():
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6)
    ax.axis("off")
    ax.set_title("Concurrency model: HSV hot path + MediaPipe worker",
                 fontsize=12, fontweight="bold")

    box(ax, (0.3, 3.6), 2.0, 1.0, "Capture\nframe", C["capture"])
    box(ax, (2.7, 3.6), 2.2, 1.0, "HSV 3-tier\nsearch\n(every frame)", C["hsv"])
    box(ax, (5.4, 3.6), 2.0, 1.0, "Map → MIDI", C["map"])
    box(ax, (7.9, 3.6), 2.6, 1.0, "every 5th frame:\nenqueue (drop if full)",
        "#777", fs=8)

    box(ax, (2.7, 0.7), 2.4, 1.1,
        "MediaPipe Hands\nbackground thread\n(~30 ms)", C["search"])
    box(ax, (5.6, 0.9), 2.4, 0.9, "latest landmarks\n(shared, locked)",
        "#999", fs=9)

    arrow(ax, (2.3, 4.1), (2.7, 4.1))
    arrow(ax, (4.9, 4.1), (5.4, 4.1))
    arrow(ax, (7.4, 4.1), (7.9, 4.1))
    arrow(ax, (9.2, 3.6), (3.9, 1.8), color="#777", rad=-0.2,
          label="queue (maxsize 1)")
    arrow(ax, (5.1, 1.35), (5.6, 1.35), color=C["search"])
    arrow(ax, (6.8, 1.8), (3.8, 3.6), color="#999", rad=0.25,
          label="hint (tier 2)")
    ax.text(5.5, 5.3, "Main loop runs at camera FPS; MP latency stays "
            "off the hot path", ha="center", fontsize=9, style="italic",
            color="#444")
    save(fig, "threading.png")


def flowchart():
    fig, ax = plt.subplots(figsize=(7.8, 7))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 11)
    ax.axis("off")
    ax.set_title("Per-marker 3-tier search", fontsize=12, fontweight="bold")

    # Left column = the miss cascade; right box = the hit terminal.
    box(ax, (0.5, 9.6), 4.6, 0.9, "New frame (HSV)", C["capture"])
    t1 = box(ax, (0.3, 7.8), 5.0, 1.0,
             "Tier 1: HSV in ROI around\nlast centroid", C["tier1"])
    t2 = box(ax, (0.3, 5.8), 5.0, 1.0,
             "Tier 2: HSV in ROI around\nMediaPipe landmark", C["tier2"])
    t3 = box(ax, (0.3, 3.8), 5.0, 1.0,
             "Tier 3: HSV full-frame\nlargest contour", C["tier3"])
    box(ax, (0.7, 1.6), 4.2, 0.9, "Not found →\nmarker lost", C["tier0"])
    box(ax, (6.6, 5.6), 3.0, 1.2, "Found →\nlock centroid", C["hsv"])

    # Miss cascade (vertical).
    arrow(ax, (2.8, 9.6), (2.8, 8.8))
    arrow(ax, (2.8, 7.8), (2.8, 6.8), label="miss")
    arrow(ax, (2.8, 5.8), (2.8, 4.8), label="miss")
    arrow(ax, (2.8, 3.8), (2.8, 2.5), label="miss")

    # Hit branches (right edge of each tier → Found).
    for (x, y, w, h) in (t1, t2, t3):
        arrow(ax, (x + w, y + h / 2), (6.6, 6.2), color=C["hsv"], rad=-0.25)
    ax.text(6.0, 7.2, "hit (any tier)", color=C["hsv"], fontsize=9)
    save(fig, "search_flowchart.png")


def main():
    architecture()
    threading()
    flowchart()


if __name__ == "__main__":
    main()
