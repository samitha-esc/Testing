from picamera2 import Picamera2
import cv2
import time

class Camera:
    def __init__(self, width=640, height=480, fps=30):
        # Initialize the official Pi Camera library
        self.picam2 = Picamera2()
        
        # Create a video configuration
        # We ask for RGB888 format because it's the fastest for the Pi's GPU
        config = self.picam2.create_video_configuration(
            main={"size": (width, height), "format": "RGB888"},
            controls={"FrameDurationLimits": (int(1000000/fps), int(1000000/fps))}
        )
        
        self.picam2.configure(config)
        self.width = width
        self.height = height
        self.fps = fps

    def start(self):
        """Starts the camera stream."""
        self.picam2.start()
        # Give the camera a second to auto-expose and stabilize
        print("Warming up Pi Camera...")
        time.sleep(1.5) 
        print("✅ Pi Camera started via libcamera.")

    def get_frame(self):
        """Captures a frame and converts it to OpenCV BGR format."""
        # capture_array() returns a NumPy array directly! No V4L2 needed.
        frame_rgb = self.picam2.capture_array()
        
        # OpenCV and our color engines expect BGR, so we convert it here
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        
        return True, frame_bgr

    def release(self):
        """Stops the camera safely."""
        self.picam2.stop()
        print("📷 Camera released.")