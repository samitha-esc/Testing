"""Contour-based engine (stub)."""
from .base_engine import BaseEngine


class ContoursEngine(BaseEngine):
    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def process_frame(self, frame):
        super().process_frame(frame)
        # Placeholder: find contours and derive gestures
        return {"debug": "contours-stub"}
