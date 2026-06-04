import cv2
import time

class Camera:
    def __init__(self, device_id=0, width=640, height=480, fps=30):
        self.device_id = device_id
        self.width = width
        self.height = height
        
        # Try to open the camera
        self.cap = cv2.VideoCapture(device_id, cv2.CAP_V4L2)
        
        if not self.cap.isOpened():
            # Fallback: try without V4L2 flag
            self.cap = cv2.VideoCapture(device_id)
        
        # Set camera properties (these might be ignored by Pi Camera, which is okay)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        
        # Try to set MJPG codec (may not work with Pi Camera, that's okay)
        try:
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        except:
            pass
        
        # Give camera time to warm up
        print("Warming up camera...")
        time.sleep(2)

    def start(self):
        if not self.cap.isOpened():
            raise IOError("Cannot open camera. Check if camera is connected.")
        print("✅ Camera started.")

    def get_frame(self):
        ret, frame = self.cap.read()
        
        # If frame read failed or frame is empty
        if not ret or frame is None or frame.size == 0:
            print("⚠️ Failed to grab frame. Retrying...")
            return False, None
        
        # Verify frame has correct dimensions
        if frame.shape[0] == 0 or frame.shape[1] == 0:
            print("⚠️ Empty frame received.")
            return False, None
            
        return ret, frame

    def release(self):
        if self.cap.isOpened():
            self.cap.release()
            print("📷 Camera released.")