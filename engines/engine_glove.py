import cv2
import numpy as np
import math
from engines.base_engine import BaseEngine

class GloveEngine(BaseEngine):
    def __init__(self, calibrated_colors: dict = None):
        # Default fallback colors
        self.default_colors = {
            'wrist': ([20, 100, 100], [35, 255, 255]),
            'thumb': ([0, 100, 100], [15, 255, 255]),
            'index': ([100, 100, 100], [130, 255, 255])
        }
        
        # Use calibrated colors if provided
        if calibrated_colors:
            self.colors = {}
            for marker, ranges in calibrated_colors.items():
                self.colors[marker] = (np.array(ranges['lower']), np.array(ranges['upper']))
        else:
            self.colors = self.default_colors
            
        self.alpha = 0.3
        self.prev_state = {'x': None, 'y': None, 'tilt': None, 'pinch': None}

    def update_colors(self, calibrated_colors: dict):
        """Update colors after recalibration."""
        self.colors = {}
        for marker, ranges in calibrated_colors.items():
            self.colors[marker] = (np.array(ranges['lower']), np.array(ranges['upper']))
        print("🎨 Glove colors updated!")

    def process(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, w, _ = frame.shape
        
        wrist = self._get_centroid(hsv, self.colors.get('wrist', self.default_colors['wrist']), min_area=200)
        thumb = self._get_centroid(hsv, self.colors.get('thumb', self.default_colors['thumb']), min_area=50)
        index = self._get_centroid(hsv, self.colors.get('index', self.default_colors['index']), min_area=50)
        
        gestures = {}

        if not wrist:
            gestures['FIST'] = True
            gestures['OPEN_PALM'] = False
            self.prev_state = {'x': None, 'y': None, 'tilt': None, 'pinch': None}
            return