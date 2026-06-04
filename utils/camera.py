from picamera2 import Picamera2
import cv2
import time

class Camera:
    def __init__(self, device_id=0, width=640, height=480, fps=30):
        self.picam2 = Picamera2()
        
        config = self.picam2.create_video_configuration(
            main={"size": (width, height), "format": "RGB888"},
            controls={"FrameDurationLimits": (int(1000000/fps), int(1000000/fps))}
        )
        self.picam2.configure(config)
        self.width = width
        self.height = height

    def start(self):
        self.picam2.start()
        print("⏳ Warming up camera...")
        time.sleep(1.5)
        print("✅ Camera started (using picamera2).")

    def get_frame(self):
        frame_rgb = self.picam2.capture_array()
        # Convert RGB to BGR for OpenCV
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        return True, frame_bgr

    def release(self):
        self.picam2.stop()
        print("📷 Camera released.")