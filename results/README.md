# Research results — figures, data & formulas

Everything here supports the paper: measured performance data, the scripts
that turn it into publication figures, the formula set, and the diagrams.

```
results/
├── scripts/        Python (matplotlib) figure generators
├── data/           raw inputs: profile.csv (from Pi), glove_colors.json
├── figures/        generated PNGs (300 dpi)
├── formulas.tex    LaTeX equation blocks for the methodology section
└── README.md       this file
```

## 1. Collecting the data (on the Raspberry Pi)

The controller has a built-in profiler (`--profile`). It logs, per frame:
capture time, HSV pre-processing time, 3-tier search time, mapping+MIDI time,
loop FPS, the search tier that resolved each marker, and how many markers were
found.

Run it on the Pi for ~2000 frames. **Wave the gloved hand in and out of frame
during the capture** — that exercises all three search tiers (locked vs
re-acquisition vs lost) and makes the tier/FPS figures far richer:

```bash
ssh samitha@midi-controller.local
cd ~/Testing
libcamerify ./venv311/bin/python main.py --headless --no-midi \
    --profile /tmp/profile.csv --profile-frames 2000
```

Notes:
- `--no-midi` avoids the USB-gadget re-enumeration that drops SSH; MIDI send
  time (`t_map`) is negligible anyway.
- `--headless` keeps it light (no web stream contending for CPU).
- The run stops itself after `--profile-frames`.

Then pull the data to this folder (from your PC):

```bash
scp samitha@midi-controller.local:/tmp/profile.csv results/data/profile.csv
scp samitha@midi-controller.local:~/Testing/config/glove_colors.json results/data/glove_colors.json
```

## 2. Generating the figures (on your PC)

Requires only `numpy` + `matplotlib`.

```bash
python results/scripts/run_all.py        # all figures
# or individually:
python results/scripts/plot_latency.py
python results/scripts/plot_fps.py
python results/scripts/plot_tiers.py
```

Diagram / transfer-function / HSV figures need **no** data and always run.

## 3. What each figure shows

| Figure | Script | Needs data? | Paper use |
|--------|--------|:-----------:|-----------|
| `latency_breakdown.png` | plot_latency | yes | stage contribution to per-frame latency |
| `latency_box.png` | plot_latency | yes | per-stage latency distribution |
| `latency_cdf.png` | plot_latency | yes | p50/p95/p99 real-time bound |
| `fps_hist.png` | plot_fps | yes | throughput distribution |
| `fps_timeseries.png` | plot_fps | yes | fps vs tracking state over time |
| `fps_vs_tracking.png` | plot_fps | yes | fast-path vs full-frame benefit |
| `tier_usage.png` | plot_tiers | yes | share of frames per search tier |
| `tier_timeline.png` | plot_tiers | yes | tier transitions over time |
| `tf_pinch.png` | plot_transfer_functions | no | PINCH → CC mapping |
| `tf_ema_step.png` | plot_transfer_functions | no | smoothing latency/response |
| `tf_relative.png` | plot_transfer_functions | no | relative CC accumulation |
| `tf_absolute_quant.png` | plot_transfer_functions | no | 7-bit quantization |
| `hsv_clusters.png` | plot_hsv_clusters | optional | marker colour separation |
| `architecture.png` | make_diagrams | no | system block diagram |
| `threading.png` | make_diagrams | no | concurrency model |
| `search_flowchart.png` | make_diagrams | no | 3-tier search logic |

## 4. Formula ↔ figure ↔ code map

| Eq. (`formulas.tex`) | Concept | Source | Figure |
|------|---------|--------|--------|
| 1 | HSV segmentation | `engine_glove._get_centroid` | hsv_clusters |
| 2 | Calibration bounds | `utils/calibration.py` | hsv_clusters |
| 3 | Centroid (moments) | `engine_glove._get_centroid` | — |
| 4 | EMA smoothing | `engine_glove._smooth` | tf_ema_step |
| 5 | Pinch | `engine_glove.process` | tf_pinch |
| 6 | Tilt | `engine_glove.process` | — |
| 7 | Abs/rel mapping | `mapping_engine._apply` | tf_absolute_quant, tf_relative |
| 8 | Latency model | `main.py` (profiler) | latency_*, fps_* |
| 9 | MediaPipe duty cycle | `engine_glove` worker | threading, tier_usage |
