import cv2

class BaseEngine:
    """Base class for all gesture tracking engines."""
    
    def init(self):
        """Initialize the engine (load models, set variables)."""
        pass

    def process(self, frame):
        """
        Process a frame and return it along with gesture data.
        Returns:
            tuple: (processed_frame_for_display, gesture_data_dict)
        """
        return frame, {}

    def close(self):
        """Clean up resources (release models, etc.)."""
        pass