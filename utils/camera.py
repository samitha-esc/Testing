"""Camera selection helper.

Provides a thin wrapper that chooses between a CV2 VideoCapture (USB) and a
PiCamera-based capture when running on Raspberry Pi. This is a lightweight
placeholder so the rest of the scaffold can import `get_camera`.
"""

import os


def get_camera(src=0, use_pi=False):
    """Return a camera-like object.

    - If `use_pi` is True, tries to create a PiCamera wrapper (not implemented).
    - Otherwise returns an object describing a USB camera index.
    """
    if use_pi or os.environ.get('USE_PI_CAMERA') == '1':
        # Real implementation would initialize picamera or libcamera bindings
        raise NotImplementedError("PiCamera support not implemented in scaffold")
    else:
        # For now, return the OpenCV index value — callers can wrap with cv2.VideoCapture
        return src
