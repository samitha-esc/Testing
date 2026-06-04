import cv2
import numpy as np
import threading
import time
import logging

logger = logging.getLogger(__name__)

_MAX_CONSECUTIVE_FAILURES = 30
_RETRY_SLEEP_S = 0.05

class _CaptureThread(threading.Thread):
    """Background thread that continuously reads frames."""
    def __init__(self, cap: cv2.VideoCapture, thread_name: str, width: int, height: int) -> None:
        super().__init__(name=thread_name, daemon=True)
        self._cap = cap
        self._width = width
        self._height = height
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._healthy = False

    def get_frame(self) -> np.ndarray | None:
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        consecutive_failures = 0
        logger.info(f"[{self.name}] Capture thread started")
        expected_size = self._width * self._height * 3

        while not self._stop_event.is_set():
            grabbed, frame = self._cap.read()

            if grabbed and frame is not None:
                # Fix libcamera flat buffer bug (the reshape error you were seeing!)
                if frame.ndim == 2 and frame.shape[0] == 1 and frame.size == expected_size:
                    frame = frame.reshape((self._height, self._width, 3))

                if frame.ndim >= 2 and frame.shape[0] > 1 and frame.shape[1] > 1:
                    with self._lock:
                        self._frame = frame
                    self._healthy = True
                    consecutive_failures = 0
                    continue
            else:
                consecutive_failures += 1
                if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                    logger.error(f"[{self.name}] Camera unresponsive after {consecutive_failures} failures")
                    break
                time.sleep(_RETRY_SLEEP_S)

class Camera:
    """Main camera interface using background threading."""
    def __init__(self, device_id=0, width=640, height=480, fps=30):
        self._width = width
        self._height = height
        self._fps = fps
        self._cap = None
        self._thread = None

    def start(self):
        print(f" Opening camera {self._width}x{self._height} @ {self._fps}fps...")
        self._cap = cv2.VideoCapture(0, cv2.CAP_V4L2)

        # CRITICAL: Force MJPEG format (prevents libcamera issues)
        mjpeg_fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
        self._cap.set(cv2.CAP_PROP_FOURCC, mjpeg_fourcc)
        
        # Force single-frame buffer (eliminates lag)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._cap.set(cv2.CAP_PROP_FPS, self._fps)

        if not self._cap.isOpened():
            raise RuntimeError("Failed to open camera. Check if camera is connected.")

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"✅ Camera opened: {actual_w}x{actual_h}")

        self._thread = _CaptureThread(self._cap, "raspi-capture", actual_w, actual_h)
        self._thread.start()
        print("⏳ Warming up camera...")
        time.sleep(1.5)
        print("✅ Camera started (background threading mode)")

    def get_frame(self):
        if self._thread is None:
            return False, None
        frame = self._thread.get_frame()
        if frame is None:
            return False, None
        return True, frame

    def release(self):
        if self._thread is not None:
            self._thread.stop()
            self._thread.join(timeout=5.0)
        if self._cap is not None:
            self._cap.release()
        print(" Camera released.")