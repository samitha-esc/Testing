import cv2
import numpy as np
import threading
import time
from typing import Optional

class _CaptureThread(threading.Thread):
    """Background thread that continuously reads frames."""
    
    def __init__(self, cap: cv2.VideoCapture, width: int, height: int) -> None:
        super().__init__(name="camera-capture", daemon=True)
        self._cap = cap
        self._width = width
        self._height = height
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._healthy = False

    def get_frame(self) -> Optional[np.ndarray]:
        """Thread-safe access to latest frame."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        consecutive_failures = 0
        max_failures = 30
        expected_size = self._width * self._height * 3
        
        print(" Camera capture thread started")
        
        while not self._stop_event.is_set():
            grabbed, frame = self._cap.read()
            
            if grabbed and frame is not None:
                # Fix libcamera flat buffer bug (the reshape error you're seeing!)
                if (frame.ndim == 2 and frame.shape[0] == 1 and frame.size == expected_size):
                    frame = frame.reshape((self._height, self._width, 3))
                
                # Validate frame
                if frame.ndim >= 2 and frame.shape[0] > 1 and frame.shape[1] > 1:
                    with self._lock:
                        self._frame = frame
                    self._healthy = True
                    consecutive_failures = 0
                    continue
                
            else:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    print(f"❌ Camera unresponsive after {consecutive_failures} failures")
                    break
                time.sleep(0.05)
        
        print("🎥 Camera capture thread stopped")

class Camera:
    """Camera with background threading for low latency."""
    
    def __init__(self, device_id=0, width=640, height=480, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        
        # Open camera with V4L2
        self._cap = cv2.VideoCapture(device_id, cv2.CAP_V4L2)
        
        if not self._cap.isOpened():
            raise RuntimeError("Failed to open camera. Check if camera is connected.")
        
        # CRITICAL: Force MJPEG format (prevents libcamera issues)
        mjpeg_fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
        self._cap.set(cv2.CAP_PROP_FOURCC, mjpeg_fourcc)
        
        # Force single-frame buffer (eliminates lag)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS, fps)
        
        # Lock exposure
        self._cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        self._cap.set(cv2.CAP_PROP_EXPOSURE, -7)
        
        self._thread: Optional[_CaptureThread] = None

    def start(self):
        """Start background capture thread."""
        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"📷 Camera opened: {actual_w}x{actual_h} @ {self.fps}fps")
        
        self._thread = _CaptureThread(self._cap, actual_w, actual_h)
        self._thread.start()
        
        print("⏳ Warming up camera...")
        time.sleep(1.5)
        print("✅ Camera started (background threading mode)")

    def get_frame(self):
        """Get latest frame from background thread."""
        if self._thread is None:
            return False, None
        
        frame = self._thread.get_frame()
        if frame is None:
            return False, None
        
        return True, frame

    def release(self):
        """Stop camera and thread."""
        if self._thread is not None:
            self._thread.stop()
            self._thread.join(timeout=5.0)
        
        if self._cap.isOpened():
            self._cap.release()
        
        print("📷 Camera released")