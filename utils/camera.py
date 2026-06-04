import cv2
import time
import numpy as np

class Camera:
    def __init__(self, device_id=0, width=640, height=480, fps=30):
        self.device_id = device_id
        self.width = width
        self.height = height
        
        # Open camera with V4L2 backend
        self.cap = cv2.VideoCapture(device_id, cv2.CAP_V4L2)
        
        if not self.cap.isOpened():
            raise IOError(f"Cannot open camera {device_id}")
        
        # Set properties
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        
        # Warm up
        print("Warming up camera...")
        time.sleep(2)
        print("✅ Camera started.")

    def start(self):
        pass  # Already started in __init__

    def get_frame(self):
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                ret, frame = self.cap.read()
                
                if not ret:
                    print(f"⚠️ Frame read failed (attempt {attempt + 1}/{max_retries})")
                    time.sleep(0.1)
                    continue
                
                # Validate frame
                if frame is None or frame.size == 0:
                    print(f"⚠️ Empty frame (attempt {attempt + 1}/{max_retries})")
                    time.sleep(0.1)
                    continue
                
                # Check frame shape
                if len(frame.shape) != 3 or frame.shape[0] == 0 or frame.shape[1] == 0:
                    print(f"⚠️ Invalid frame shape: {frame.shape} (attempt {attempt + 1}/{max_retries})")
                    time.sleep(0.1)
                    continue
                
                # Ensure frame is in BGR format (3 channels)
                if len(frame.shape) == 2:
                    frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                elif frame.shape[2] == 4:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                
                return True, frame
                
            except Exception as e:
                print(f"⚠️ Error reading frame: {e} (attempt {attempt + 1}/{max_retries})")
                time.sleep(0.1)
                continue
        
        print("❌ Failed to grab valid frame after multiple attempts")
        return False, None

    def release(self):
        if self.cap.isOpened():
            self.cap.release()
            print("📷 Camera released.")