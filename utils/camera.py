import cv2

class Camera:
    def __init__(self, device_id=0, width=320, height=240, fps=30):
        # Force V4L2 backend for Linux/Pi USB cameras
        self.cap = cv2.VideoCapture(device_id, cv2.CAP_V4L2)
        
        # Crucial settings for USB webcams
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)

    def start(self):
        if not self.cap.isOpened():
            raise IOError(f"Cannot open camera {self.device_id}")
        print("Camera started.")

    def get_frame(self):
        return self.cap.read()

    def release(self):
        if self.cap.isOpened():
            self.cap.release()
            print("Camera released.")