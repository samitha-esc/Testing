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
        # Track per-marker samples separately. The loop only finishes when
        # every marker has enough samples, not just a shared total. This
        # prevents wrist saturating the count while fingertips are off-screen.
        NEEDED = 20
        samples = {'wrist': [], 'thumb': [], 'index': []}
        attempts = 0
        max_attempts = NEEDED * 80   # bail-out (~53 seconds at 30fps)
        last_print = 0.0

        while attempts < max_attempts:
            # Check if all markers are done.
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
                    'wrist': (int(landmarks[0].x * w), int(landmarks[0].y * h)),
                    'thumb': (int(landmarks[4].x * w), int(landmarks[4].y * h)),
                    'index': (int(landmarks[8].x * w), int(landmarks[8].y * h)),
                }

                for marker, px in lm_px.items():
                    # Only sample if the landmark is well inside the frame
                    # (not near edges where samples would be clipped to nothing).
                    margin = 10
                    if margin < px[0] < w - margin and margin < px[1] < h - margin:
                        got = self._sample_color(frame_rgb, px)
                        if got:
                            samples[marker].extend(got)

            # Print progress at most once per second so the terminal is readable.
            now = time.time()
            if now - last_print >= 1.0:
                counts = {m: len(s) for m, s in samples.items()}
                parts = [f"{m}: {min(c, NEEDED)}/{NEEDED}" for m, c in counts.items()]
                missing = [m for m, c in counts.items() if c < NEEDED]
                hint = f" — move '{', '.join(missing)}' into frame" if missing else ""
                print(f"  {' | '.join(parts)}{hint}")
                last_print = now

            time.sleep(0.033)

        if owns_camera:
            camera.release()

        counts = {m: len(s) for m, s in samples.items()}
        missing = [m for m, c in counts.items() if c < NEEDED]
        if missing:
            print(f"⚠️  Markers with too few samples: {missing}. "
                  "Those will use default colors. Re-run calibration with "
                  "all markers clearly visible.")
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
        """Convert RGB samples to HSV and calculate optimal ranges."""
        # Convert to HSV
        hsv_samples = []
        for rgb in rgb_samples:
            # Normalize to 0-1
            rgb_norm = np.array([[rgb / 255.0]], dtype=np.float32)
            hsv = cv2.cvtColor(rgb_norm, cv2.COLOR_RGB2HSV)[0][0]
            # Scale to OpenCV ranges (H: 0-179, S: 0-255, V: 0-255)
            hsv_samples.append([hsv[0] * 179, hsv[1] * 255, hsv[2] * 255])
        
        hsv_array = np.array(hsv_samples)
        
        # Calculate mean and std dev
        mean_hsv = np.mean(hsv_array, axis=0)
        std_hsv = np.std(hsv_array, axis=0)
        
        # Create safe ranges (mean ± 2*std, with bounds).
        # Saturation floor is 100 (not 40) — skin tones have S < 100 under
        # most lighting, so this prevents calibrated ranges from covering skin.
        lower = np.clip(mean_hsv - 2 * std_hsv, [0, 100, 60], [179, 255, 255])
        upper = np.clip(mean_hsv + 2 * std_hsv, [0, 100, 60], [179, 255, 255])
        
        return {
            'lower': lower.astype(int).tolist(),
            'upper': upper.astype(int).tolist(),
            'mean': mean_hsv.astype(int).tolist()
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