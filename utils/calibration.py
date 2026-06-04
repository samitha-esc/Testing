import cv2
import numpy as np
import mediapipe as mp
import json
import os
from picamera2 import Picamera2
import time

class GloveCalibrator:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.picam2 = Picamera2()
        
    def calibrate(self) -> dict:
        """
        Run auto-calibration. Returns dict with HSV ranges for each marker.
        """
        print("📍 CALIBRATION MODE")
        print("1. Put on your glove with colored markers")
        print("2. Hold your hand OPEN, palm facing camera")
        print("3. Keep still for 3 seconds...")
        time.sleep(3)
        
        # Start camera
        config = self.picam2.create_video_configuration(
            main={"size": (640, 480), "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()
        
        print("⏳ Detecting hand...")
        samples = {
            'wrist': [],
            'thumb': [],
            'index': []
        }
        
        start_time = time.time()
        sample_count = 0
        max_samples = 30
        
        while sample_count < max_samples:
            frame_rgb = self.picam2.capture_array()
            results = self.hands.process(frame_rgb)
            
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    # Extract key points
                    landmarks = hand_landmarks.landmark
                    wrist = landmarks[0]
                    thumb_tip = landmarks[4]
                    index_tip = landmarks[8]
                    
                    # Convert to pixel coordinates
                    h, w, _ = frame_rgb.shape
                    wrist_px = (int(wrist.x * w), int(wrist.y * h))
                    thumb_px = (int(thumb_tip.x * w), int(thumb_tip.y * h))
                    index_px = (int(index_tip.x * w), int(index_tip.y * h))
                    
                    # Sample colors at these locations (3x3 area)
                    samples['wrist'].extend(self._sample_color(frame_rgb, wrist_px))
                    samples['thumb'].extend(self._sample_color(frame_rgb, thumb_px))
                    samples['index'].extend(self._sample_color(frame_rgb, index_px))
                    
                    sample_count += 1
                    
                    # Progress indicator
                    if sample_count % 5 == 0:
                        print(f"  Sampling... {sample_count}/{max_samples}")
            
            time.sleep(0.033)  # ~30fps
        
        self.picam2.stop()
        self.hands.close()
        
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
        
        # Create safe ranges (mean ± 2*std, with bounds)
        lower = np.clip(mean_hsv - 2 * std_hsv, [0, 40, 40], [179, 255, 255])
        upper = np.clip(mean_hsv + 2 * std_hsv, [0, 40, 40], [179, 255, 255])
        
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