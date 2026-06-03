import cv2
import numpy as np
import math
from engines.base_engine import BaseEngine

class GloveEngine(BaseEngine):
    def __init__(self):
        # 1. Define HSV ranges for the 3 markers
        # Tweak these if your specific tape/markers look slightly different
        self.colors = {
            'wrist':  ([20, 100, 100], [35, 255, 255]),   # Yellow (Anchor)
            'thumb':  ([0, 100, 100],  [15, 255, 255]),   # Red 
            'index':  ([100, 100, 100],[130, 255, 255])   # Blue
        }
        
        # 2. Smoothing factor (0.0 to 1.0). 
        # 0.2 = very smooth/analog feel, 0.9 = instant/snappy feel
        self.alpha = 0.3 
        
        # 3. State variables for Deltas and Smoothing
        self.prev_state = {
            'x': None, 'y': None, 
            'tilt': None, 'pinch': None
        }

    def process(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, w, _ = frame.shape
        
        # Find the centroids of the 3 markers
        wrist = self._get_centroid(frame, hsv, self.colors['wrist'], min_area=200)
        thumb = self._get_centroid(frame, hsv, self.colors['thumb'], min_area=50)
        index = self._get_centroid(frame, hsv, self.colors['index'], min_area=50)
        
        gestures = {}

        # If the wrist (anchor) is lost, the hand is out of frame. 
        # Send a "FIST" to stop audio/trigger safety.
        if not wrist:
            gestures['FIST'] = True
            gestures['OPEN_PALM'] = False
            self.prev_state = {'x': None, 'y': None, 'tilt': None, 'pinch': None}
            return gestures

        # --- PHASE 2: KINEMATIC MATH ---
        
        # Absolute Position (Normalized 0.0 - 1.0)
        raw_x = wrist[0] / w
        raw_y = wrist[1] / h
        
        # Tilt Angle (Angle between Wrist and Index finger)
        # We invert Y because in image space, Y goes DOWN, but in math, Y goes UP
        dx = index[0] - wrist[0] if index else 0
        dy = -(index[1] - wrist[1]) if index else 0 
        angle_rad = math.atan2(dy, dx) # Returns -pi to pi
        
        # Normalize angle so straight UP is 0.5, LEFT is 0.0, RIGHT is 1.0
        raw_tilt = (angle_rad / math.pi + 1) / 2
        
        # Pinch Distance (Distance between Thumb and Index)
        if thumb and index:
            dist = math.hypot(thumb[0] - index[0], thumb[1] - index[1])
            # Normalize distance. Assuming max natural stretch is ~200 pixels on a 640x480 cam
            raw_pinch = max(0.0, min(1.0, dist / 200.0)) 
        else:
            raw_pinch = 0.0 # Default to closed if we can't see both fingers

        # --- PHASE 3: STATE CLASSIFICATION ---
        
        if raw_pinch < 0.15: # Fingers are touching
            gestures['FIST'] = True
            gestures['OPEN_PALM'] = False
        elif raw_pinch > 0.40: # Fingers are spread apart
            gestures['FIST'] = False
            gestures['OPEN_PALM'] = True
        else:
            # In the middle (e.g., pinching or pointing)
            gestures['FIST'] = False
            gestures['OPEN_PALM'] = False

        # --- PHASE 4: DELTA & SMOOTHING ---
        
        # Apply Exponential Moving Average (Low Pass Filter)
        p = self.prev_state
        smooth_x =  p['x']    + self.alpha * (raw_x - p['x'])    if p['x']    else raw_x
        smooth_y =  p['y']    + self.alpha * (raw_y - p['y'])    if p['y']    else raw_y
        smooth_tilt = p['tilt'] + self.alpha * (raw_tilt - p['tilt']) if p['tilt'] else raw_tilt
        smooth_pinch= p['pinch']+ self.alpha * (raw_pinch - p['pinch']) if p['pinch'] else raw_pinch

        # Update state for next frame
        self.prev_state = {
            'x': smooth_x, 'y': smooth_y, 
            'tilt': smooth_tilt, 'pinch': smooth_pinch
        }

        # Calculate Deltas (Change since last frame)
        # Only calculate if we have a previous frame to compare to
        if p['x'] is not None:
            gestures['HAND_X'] = smooth_x
            gestures['HAND_Y'] = smooth_y
            gestures['HAND_DELTA_X'] = smooth_x - p['x']
            gestures['HAND_DELTA_Y'] = smooth_y - p['y']
            
            gestures['TILT'] = smooth_tilt
            gestures['TILT_DELTA'] = smooth_tilt - p['tilt']
            
            gestures['PINCH'] = smooth_pinch
        else:
            # First frame after reset, just send absolute values
            gestures['HAND_X'] = smooth_x
            gestures['TILT'] = smooth_tilt
            gestures['PINCH'] = smooth_pinch

        return gestures

    def _get_centroid(self, frame, hsv, color_range, min_area=100):
        """Isolates a specific color and returns its (x, y) center."""
        lower, upper = color_range
        mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
        
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # Get the largest blob of this color to ignore background noise
            largest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest) > min_area:
                M = cv2.moments(largest)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    return (cx, cy)
        return None

    def release(self):
        pass