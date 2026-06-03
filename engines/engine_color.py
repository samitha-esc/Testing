"""Color-thresholding engine (stub)."""
from .base_engine import BaseEngine


class ColorEngine(BaseEngine):
    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def process_frame(self, frame):
        super().process_frame(frame)
        # Placeholder: detect colored markers
        return {"debug": "color-stub"}
