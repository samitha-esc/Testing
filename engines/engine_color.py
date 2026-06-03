import cv2
import numpy as np
from engines.base_engine import BaseEngine

class ColorEngine(BaseEngine):
    def __init__(self, color="green"):
        self.color = color.lower()
        self.color_ranges = {
            "green": ([35, 100, 100], [85, 255, 255]),
            "red": ([0, 100, 100], [10, 255, 255]),
            "blue": ([100, 100, 100], [130, 255, 255])
        }
        
    def process(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower, upper = self.color_ranges.get(self.color, self.color_ranges["green"])
        mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
        
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) > 0:
            c = max(contours, key=cv2.contourArea)
            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                h, w, _ = frame.shape
                
                return {
                    'x_midi': int((cx / w) * 127), 
                    'y_midi': int((cy / h) * 127)
                }
        return None

    def release(self):
        pass