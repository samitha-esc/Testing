import cv2

class Camera:
    def __init__(self, device_id=0, width=640, height=480, fps=30):
        # Force V4L2 backend. libcamerify will intercept this and route it to the Pi Camera.
        self.cap = cv2.VideoCapture(device_id, cv2.CAP_V4L2)
        
        # Standard settings
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        
        # Lock exposure so the camera doesn't adjust brightness when you move your glove
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25) # 0.25 turns off auto-exposure
        self.cap.set(cv2.CAP_PROP_EXPOSURE, -7)        # Manual exposure level

    def start(self):
        if not self.cap.isOpened():
            raise IOError("Cannot open camera.")
        print("✅ Camera started.")

    def get_frame(self):
        return self.cap.read()

    def release(self):
        if self.cap.isOpened():
            self.cap.release()
            print("📷 Camera released.")