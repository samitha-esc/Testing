"""Mediapipe-based engine (stub)."""
from .base_engine import BaseEngine


class MediPipeEngine(BaseEngine):
    def start(self):
        super().start()
        # Implementation will initialize mediapipe graphs

    def stop(self):
        super().stop()

    def process_frame(self, frame):
        super().process_frame(frame)
        # Placeholder: perform mediapipe processing
        return {"debug": "mediapipe-stub"}
