from picamera2 import Picamera2
import cv2
import numpy as np

def mouse_callback(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        # param is the RGB frame from picamera2
        hsv_frame = cv2.cvtColor(param, cv2.COLOR_RGB2HSV)
        h, s, v = hsv_frame[y, x]
        
        print(f"Clicked at ({x}, {y}) -> HSV: [{h}, {s}, {v}]")
        
        # Calculate a safe range around that color
        lower = [max(0, h-10), max(0, s-40), max(0, v-40)]
        upper = [min(179, h+10), 255, 255]
        print(f"--> Copy this to engine_glove.py: Lower={lower}, Upper={upper}\n")

# Initialize Pi Camera
picam2 = Picamera2()
config = picam2.create_video_configuration(main={"size": (640, 480), "format": "RGB888"})
picam2.configure(config)
picam2.start()

print("Color Picker Ready!")
print("1. Point camera at your glove.")
print("2. Click on the Yellow, Red, and Blue tape.")
print("3. Copy the printed ranges into engine_glove.py.")
print("4. Press 'q' to quit.")

cv2.namedWindow("Color Picker")

while True:
    frame_rgb = picam2.capture_array()
    # OpenCV needs BGR to display correctly on screen
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    
    cv2.setMouseCallback("Color Picker", mouse_callback, frame_rgb)
    cv2.imshow("Color Picker", frame_bgr)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

picam2.stop()
cv2.destroyAllWindows()