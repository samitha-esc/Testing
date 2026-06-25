"""Figure set: gesture -> MIDI transfer functions (#11).

These are derived directly from the implementation (no measured data needed):
  - tf_pinch.png      : fingertip distance -> normalized pinch -> CC value
  - tf_ema_step.png   : EMA smoothing step response (alpha = 0.3 / 0.4)
  - tf_relative.png    : relative-CC accumulation (DJ crossfader/scratch)
  - tf_absolute_quant.png : normalized gesture -> 7-bit CC quantization

Constants mirror the source:
  PINCH:    p = clamp(dist / 0.35, 0, 1)            engine_glove.process()
  EMA:      s_t = a*x_t + (1-a)*s_{t-1}             engine_glove._smooth()
            a = 0.3 (x/y/pinch/tilt), 0.4 (wrist)
  ABSOLUTE: cc = floor(clamp(g,0,1) * 127)          mapping_engine._apply()
  RELATIVE: v_t = clamp(v_{t-1} + floor(d*254), 0, 127), v_0 = 64
"""
import numpy as np
from common import save, C, plt

PINCH_SCALE = 0.35
ALPHA_MARKER = 0.3
ALPHA_WRIST = 0.4


def fig_pinch():
    dist = np.linspace(0, 0.5, 500)
    p = np.clip(dist / PINCH_SCALE, 0, 1)
    cc = np.floor(p * 127).astype(int)

    fig, ax1 = plt.subplots(figsize=(6.5, 4))
    ax1.plot(dist, p, color=C["search"], linewidth=2, label="normalized pinch $p$")
    ax1.axvline(PINCH_SCALE, color="grey", linestyle=":", alpha=0.7)
    ax1.text(PINCH_SCALE + 0.005, 0.05, "saturation\n$d=0.35$", fontsize=8)
    ax1.set_xlabel("Fingertip distance $d$ (normalized image units)")
    ax1.set_ylabel("Normalized pinch $p$", color=C["search"])
    ax1.set_ylim(-0.03, 1.05)

    ax2 = ax1.twinx()
    ax2.plot(dist, cc, color=C["capture"], linewidth=1.2, alpha=0.7,
             label="MIDI CC")
    ax2.set_ylabel("MIDI CC value (0–127)", color=C["capture"])
    ax2.set_ylim(-3, 130)
    ax2.grid(False)
    ax1.set_title("PINCH transfer function (thumb–index distance → CC 74)")
    save(fig, "tf_pinch.png")


def fig_ema():
    n = np.arange(0, 30)
    fig, ax = plt.subplots(figsize=(6.5, 4))
    x = np.ones_like(n, dtype=float)  # unit step at n=0
    for a, col, name in [(ALPHA_MARKER, C["search"], "α = 0.3 (fingertips)"),
                         (ALPHA_WRIST, C["capture"], "α = 0.4 (wrist)")]:
        s = 1 - (1 - a) ** (n + 1)        # closed-form step response, s_{-1}=0
        ax.plot(n, s, "o-", color=col, markersize=4, label=name)
        # frames to reach 90%
        t90 = int(np.ceil(np.log(0.1) / np.log(1 - a))) - 1
        ax.annotate(f"90% @ {t90} frames", (t90, 0.9), color=col, fontsize=8,
                    xytext=(t90 + 1, 0.9 - (0.12 if a == ALPHA_MARKER else 0.22)),
                    arrowprops=dict(arrowstyle="->", color=col, alpha=0.6))
    ax.axhline(1.0, color="grey", linestyle=":", alpha=0.6)
    ax.axhline(0.9, color="grey", linestyle="--", alpha=0.4)
    ax.set_xlabel("Frames after a unit step input")
    ax.set_ylabel("Smoothed output $s_t$")
    ax.set_title("EMA smoothing step response")
    ax.set_ylim(0, 1.08)
    ax.legend(loc="lower right")
    save(fig, "tf_ema_step.png")


def fig_relative():
    steps = 60
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for delta, col in [(0.02, C["tier1"]), (0.05, C["tier2"]), (0.10, C["tier3"])]:
        v = 64
        traj = [v]
        for _ in range(steps):
            v = int(np.clip(v + int(delta * 127 * 2), 0, 127))
            traj.append(v)
        ax.plot(traj, color=col, linewidth=2,
                label=f"constant Δ = {delta:.2f}/frame")
    ax.axhline(127, color="grey", linestyle=":", alpha=0.6)
    ax.axhline(64, color="grey", linestyle="--", alpha=0.4)
    ax.text(0.5, 66, "start = 64", fontsize=8, color="grey")
    ax.set_xlabel("Frame")
    ax.set_ylabel("Accumulated CC value")
    ax.set_title("Relative-mode accumulation (DJ crossfader / scratch)")
    ax.set_ylim(55, 132)
    ax.legend(loc="lower right")
    save(fig, "tf_relative.png")


def fig_absolute_quant():
    g = np.linspace(0, 1, 1000)
    cc = np.floor(np.clip(g, 0, 1) * 127).astype(int)
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot(g, cc, color=C["map"], linewidth=1.8)
    ax.plot(g, g * 127, color="grey", linestyle=":", alpha=0.6,
            label="ideal (continuous)")
    ax.set_xlabel("Normalized gesture value $g \\in [0,1]$")
    ax.set_ylabel("MIDI CC value (7-bit)")
    ax.set_title("Absolute-mode quantization (gesture → 7-bit CC)")
    ax.legend(loc="upper left")
    save(fig, "tf_absolute_quant.png")


def main():
    fig_pinch()
    fig_ema()
    fig_relative()
    fig_absolute_quant()


if __name__ == "__main__":
    main()
