import cv2
import numpy as np
import mediapipe as mp
import json
import os
import time

from utils.camera import Camera

class GloveCalibrator:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )

    def calibrate(self, camera: Camera = None) -> dict:
        """
        Run auto-calibration. Returns dict with HSV ranges for each marker.

        Uses the same cv2.VideoCapture (V4L2) source as the runtime engine
        so calibrated HSV values match what the tracker actually sees.

        If `camera` is provided (already started), it is reused — important
        for the in-app 'r' recalibration, since /dev/video0 cannot be opened
        twice. If None, a temporary camera is opened and released here.
        """
        print("📍 CALIBRATION MODE")
        print("1. Put on your glove with colored markers")
        print("2. Hold your hand OPEN, palm facing camera")
        print("3. Keep still for 3 seconds...")
        time.sleep(3)

        owns_camera = camera is None
        if owns_camera:
            camera = Camera(device_id=0, width=640, height=480)
            camera.start()

        print("⏳ Detecting hand — keep all three markers in frame...")
        print("   You will see colored dots on the camera feed showing")
        print("   exactly where each marker color is being sampled.")

        NEEDED = 20
        # Dot colors drawn on the preview (BGR): wrist=yellow, thumb=red, index=blue
        DOT_COLORS = {'wrist': (0, 255, 255), 'thumb': (0, 0, 255), 'index': (255, 0, 0)}
        MARKER_LM  = {'wrist': 0, 'thumb': 4, 'index': 8}

        samples = {'wrist': [], 'thumb': [], 'index': []}
        attempts = 0
        max_attempts = NEEDED * 80
        last_print = 0.0
        has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or os.name == "nt")

        while attempts < max_attempts:
            counts = {m: len(s) for m, s in samples.items()}
            if all(c >= NEEDED for c in counts.values()):
                break

            attempts += 1
            ret, frame_bgr = camera.get_frame()
            if not ret or frame_bgr is None:
                time.sleep(0.01)
                continue

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            results = self.hands.process(frame_rgb)

            if results.multi_hand_landmarks:
                h, w, _ = frame_rgb.shape
                landmarks = results.multi_hand_landmarks[0].landmark
                lm_px = {
                    m: (int(landmarks[idx].x * w), int(landmarks[idx].y * h))
                    for m, idx in MARKER_LM.items()
                }

                for marker, px in lm_px.items():
                    margin = 10
                    if margin < px[0] < w - margin and margin < px[1] < h - margin:
                        if len(samples[marker]) < NEEDED:
                            got = self._sample_color(frame_rgb, px)
                            if got:
                                samples[marker].extend(got)

                # Show live preview with sample-point dots if display is available.
                if has_display:
                    preview = frame_bgr.copy()
                    counts_now = {m: len(s) for m, s in samples.items()}
                    for marker, px in lm_px.items():
                        done = min(counts_now[marker], NEEDED)
                        filled = done >= NEEDED
                        radius = 12 if filled else 8
                        cv2.circle(preview, px, radius, DOT_COLORS[marker], -1 if filled else 2)
                        cv2.putText(preview, f"{marker} {done}/{NEEDED}",
                                    (px[0] + 14, px[1]),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                    DOT_COLORS[marker], 1)
                    cv2.putText(preview, "CALIBRATING — hold hand open, still",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (0, 255, 0), 2)
                    cv2.imshow("Calibration", preview)
                    cv2.waitKey(1)

            now = time.time()
            if now - last_print >= 1.0:
                counts = {m: len(s) for m, s in samples.items()}
                parts = [f"{m}: {min(len(samples[m]), NEEDED)}/{NEEDED}" for m in samples]
                missing = [m for m in samples if len(samples[m]) < NEEDED]
                hint = f" — bring '{', '.join(missing)}' into frame" if missing else ""
                print(f"  {' | '.join(parts)}{hint}")
                last_print = now

            time.sleep(0.033)

        if has_display:
            cv2.destroyWindow("Calibration")

        if owns_camera:
            camera.release()

        counts = {m: len(s) for m, s in samples.items()}
        missing = [m for m in counts if counts[m] < NEEDED]
        if missing:
            print(f"⚠️  Markers with too few samples: {missing}. "
                  "Those will use default colors.")
        else:
            print("✅ All markers sampled. Processing...")

        print("✅ Calibration complete! Processing samples...")
        
        # Calculate HSV ranges
        calibrated_colors = {}
        for marker_name, color_samples in samples.items():
            if len(color_samples) > 0:
                hsv_ranges = self._calculate_hsv_ranges(color_samples)
                calibrated_colors[marker_name] = hsv_ranges
                print(f"  {marker_name.upper()}: HSV range calculated from {len(color_samples)} samples")
        
        return calibrated_colors
    
    def _sample_color(self, frame_rgb, center_px, radius=3) -> list:
        """Sample RGB colors in a small area around the point."""
        x, y = center_px
        h, w, _ = frame_rgb.shape
        
        samples = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                px, py = x + dx, y + dy
                if 0 <= px < w and 0 <= py < h:
                    samples.append(frame_rgb[py, px])
        
        return samples
    
    def _calculate_hsv_ranges(self, rgb_samples: list) -> dict:
        """Convert RGB samples to HSV and calculate detection ranges."""
        hsv_samples = []
        for rgb in rgb_samples:
            # Use uint8 input, NOT float. Float input makes cv2 return H in
            # [0,360]; uint8 returns H in [0,179]. The original code used float
            # then multiplied by 179, giving e.g. yellow H=60 → 60*179=10740
            # which clips to 179 — every color ended up as H=179 (magenta).
            rgb_px = np.uint8([[rgb]])
            hsv = cv2.cvtColor(rgb_px, cv2.COLOR_RGB2HSV)[0][0]
            hsv_samples.append(hsv.astype(float))

        hsv_array = np.array(hsv_samples)
        mean_hsv  = np.mean(hsv_array, axis=0)
        std_hsv   = np.std(hsv_array,  axis=0)

        # Hue: mean ± 3σ (wider coverage; ROI constrains position anyway).
        # Saturation/Value lower bounds: the mean-kσ estimate COLLAPSES to ~mean
        # when the marker is sampled under bright, even light (tiny std). That
        # produces floors so high (e.g. V>=232) the marker drops out of the mask
        # the moment the light dims — which is why detection needed very bright
        # light. Cap the floors so a calibrated marker is still matched in dimmer
        # / less-saturated conditions:
        #   - S floor never above 150  → still rejects washed-out gray/skin,
        #     but no longer demands near-max saturation.
        #   - V floor never above 110  → V is the brightness axis, so a low cap
        #     gives wide lighting tolerance. Upper S/V stay 255, so brighter is
        #     always fine.
        h_lo = float(np.clip(mean_hsv[0] - 3 * std_hsv[0], 0, 179))
        h_hi = float(np.clip(mean_hsv[0] + 3 * std_hsv[0], 0, 179))
        s_lo = float(np.clip(mean_hsv[1] - 3 * std_hsv[1], 30, 150))
        v_lo = float(np.clip(mean_hsv[2] - 5 * std_hsv[2], 20, 110))

        lower = [int(h_lo), int(s_lo), int(v_lo)]
        upper = [int(h_hi), 255, 255]

        # Human-readable diagnostic so you can verify calibration makes sense.
        h, s, v = mean_hsv
        if   s < 50:        colour = "gray/white"
        elif h < 10 or h > 170: colour = "red"
        elif h < 25:        colour = "orange"
        elif h < 35:        colour = "yellow"
        elif h < 85:        colour = "green"
        elif h < 130:       colour = "blue"
        elif h < 155:       colour = "purple"
        else:               colour = "pink/red"
        print(f"    mean HSV: H={h:.0f} S={s:.0f} V={v:.0f}  → {colour}")
        print(f"    range:    H=[{lower[0]}-{upper[0]}]  S=[{lower[1]}-255]  V=[{lower[2]}-255]")

        return {
            'lower': lower,
            'upper': upper,
            'mean':  [int(h), int(s), int(v)],
        }
    
    def save_calibration(self, colors: dict, filepath: str = "config/glove_colors.json"):
        """Save calibration to JSON file."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        data = {
            'calibrated_colors': colors,
            'timestamp': time.time()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Calibration saved to {filepath}")
    
    def load_calibration(self, filepath: str = "config/glove_colors.json") -> dict:
        """Load calibration from JSON file."""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
            print(f"✅ Loaded calibration from {filepath}")
            return data['calibrated_colors']
        else:
            print("⚠️ No calibration file found. Run calibration first.")
            return None

    def release(self):
        """Close the MediaPipe Hands graph. Call once at shutdown."""
        try:
            self.hands.close()
        except Exception:
            pass