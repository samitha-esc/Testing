"""Shared style, paths, and data loaders for the paper figure scripts.

Every plotting script imports from here so figures share one consistent,
publication-ready look. No third-party deps beyond numpy + matplotlib.
"""
import os
import csv
import numpy as np
import matplotlib

matplotlib.use("Agg")  # headless: write PNGs without a display
import matplotlib.pyplot as plt  # noqa: E402

# --- Paths ----------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.dirname(HERE)                 # .../results
DATA = os.path.join(RESULTS, "data")
FIGS = os.path.join(RESULTS, "figures")
os.makedirs(DATA, exist_ok=True)
os.makedirs(FIGS, exist_ok=True)

# --- Publication style ----------------------------------------------------
plt.rcParams.update({
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "font.size": 11,
    "font.family": "serif",
    "mathtext.fontset": "dejavuserif",
    "axes.grid": True,
    "grid.alpha": 0.30,
    "grid.linestyle": "--",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "legend.frameon": False,
})

# Colour-blind-safe palette (Wong 2011) keyed by pipeline stage / marker.
C = {
    "capture": "#0072B2",   # blue
    "hsv":     "#009E73",   # green
    "search":  "#D55E00",   # vermillion
    "map":     "#CC79A7",   # purple
    "total":   "#333333",
    "wrist":   "#E69F00",   # orange  (yellow loop marker)
    "thumb":   "#D55E00",   # vermillion (red marker)
    "index":   "#0072B2",   # blue marker
    "tier1":   "#009E73",   # continuity ROI  -> cheap
    "tier2":   "#E69F00",   # MP hint ROI
    "tier3":   "#D55E00",   # full-frame      -> expensive
    "tier0":   "#999999",   # lost
}


def save(fig, name):
    """Save a figure into results/figures/ and close it."""
    path = os.path.join(FIGS, name)
    fig.savefig(path)
    plt.close(fig)
    print(f"  wrote {os.path.relpath(path, RESULTS)}")
    return path


def load_profile(path=None):
    """Load the per-frame profiling CSV into a dict of numpy arrays."""
    path = path or os.path.join(DATA, "profile.csv")
    if not os.path.exists(path):
        raise SystemExit(
            f"\nMissing data file: {path}\n"
            "Collect it on the Pi first — see results/README.md "
            "(section 'Collecting the data').\n")
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    if not rows:
        raise SystemExit(f"{path} is empty.")
    cols = {k: np.array([float(r[k]) for r in rows]) for k in rows[0]}
    return cols


def stats_line(name, arr, unit="ms"):
    """Return a one-line summary string for a metric (handy for captions)."""
    return (f"{name}: mean={arr.mean():.3f} "
            f"median={np.median(arr):.3f} "
            f"p95={np.percentile(arr, 95):.3f} "
            f"max={arr.max():.3f} {unit}")
