import cv2
import numpy as np
from engines.base_engine import BaseEngine

class ColorEngine(BaseEngine):
    """OpenCV Color Tracking Engine - Fast and lightweight"""
    
    def __init__(self, color='green'):
        self.color = color
        self.lower_bound = None
        self.upper_bound = None
        self.setup_color_bounds()
    
    def setup_color_bounds(self):
        """Set HSV color bounds for tracking"""
        # HSV ranges for different colors
        color_bounds = {
            'green': ([40, 100, 100], [70, 255, 255]),
            'blue': ([100, 100, 100], [130, 255, 255]),
            'red': ([0, 100, 100], [10, 255, 255]),
            'orange': ([10, 100, 100], [25, 255, 255]),
            'yellow': ([20, 100, 100], [35, 255, 255]),
        }
        
        if self.color in color_bounds:
            self.lower_bound = np.array(color_bounds[self.color][0])
            self.upper_bound = np.array(color_bounds[self.color][1])
        else:
            # Default to green
            self.lower_bound = np.array([40, 100, 100])
            self.upper_bound = np.array([70, 255, 255])
    
    def init(self):
        """Initialize the engine"""
        print(f"✅ Color engine initialized for: {self.color}")
    
    def process(self, frame):
        """
        Process frame and track colored object
        Returns: (display_frame, gesture_data)
        """
        # Convert to HSV color space
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Create mask for the color
        mask = cv2.inRange(hsv, self.lower_bound, self.upper_bound)
        
        # Apply morphological operations to reduce noise
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        gesture_data = {
            'detected': False,
            'x': 0,
            'y': 0,
            'area': 0
        }
        
        # Find largest contour
        if contours:
            c = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(c)
            
            if area > 100:  # Filter small noise
                # Calculate centroid
                M = cv2.moments(c)
                if M["m00"] > 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    
                    gesture_data = {
                        'detected': True,
                        'x': cX,
                        'y': cY,
                        'area': area
                    }
                    
                    # Draw contour and centroid on frame
                    cv2.drawContours(frame, [c], -1, (0, 255, 0), 2)
                    cv2.circle(frame, (cX, cY), 20, (255, 255, 255), -1)
                    
                    # Add text showing position
                    cv2.putText(frame, f"X: {cX} Y: {cY}", (cX - 50, cY - 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # Show mask in a small window (optional, for debugging)
        # cv2.imshow('Mask', mask)
        
        return frame, gesture_data
    
    def close(self):
        """Clean up"""
        print("🔴 Color engine closed")