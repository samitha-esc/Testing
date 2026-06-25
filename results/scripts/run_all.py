"""Generate every paper figure in one go.

    python results/scripts/run_all.py

Data-driven figures (latency, fps, tiers) require results/data/profile.csv;
they are skipped with a notice if it's missing. Diagram, transfer-function,
and HSV-cluster figures always run.
"""
import importlib
import traceback

ALWAYS = ["make_diagrams", "plot_transfer_functions", "plot_hsv_clusters"]
DATA_DRIVEN = ["plot_latency", "plot_fps", "plot_tiers"]


def run(mod_name):
    print(f"\n=== {mod_name} ===")
    try:
        mod = importlib.import_module(mod_name)
        mod.main()
    except SystemExit as e:
        print(f"  skipped: {e}")
    except Exception:
        print(f"  ERROR in {mod_name}:")
        traceback.print_exc()


def main():
    for m in ALWAYS + DATA_DRIVEN:
        run(m)
    print("\nDone. Figures are in results/figures/")


if __name__ == "__main__":
    main()
