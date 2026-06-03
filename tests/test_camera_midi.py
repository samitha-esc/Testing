import cv2
import mido
import time
import numpy as np

def run_test():
    print("Initializing Camera and MIDI...")
    
    # 1. Open the default MIDI output (The USB Gadget we built!)
    try:
        outport = mido.open_output()
        print("✅ MIDI Port Opened.")
    except Exception as e:
        print(f"❌ MIDI Error: {e}")
        return

    # 2. Open the Camera
    cap = cv2.VideoCapture(1, cv2.CAP_V4L2)
    # Lower resolution for better performance on Pi
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    
    if not cap.isOpened():
        print("❌ Could not open camera.")
        return

    print(" Tracking GREEN objects. Hold a green object in front of the camera!")
    print("Press 'q' in the terminal to quit.")

    prev_x_midi = -1
    prev_y_midi = -1

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Convert to HSV color space (better for color tracking)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Define range for GREEN color
        lower_green = np.array([35, 100, 100])
        upper_green = np.array([85, 255, 255])
        
        # Create a mask and find the green object
        mask = cv2.inRange(hsv, lower_green, upper_green)
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        if len(contours) > 0:
            # Get the largest green object
            c = max(contours, key=cv2.contourArea)
            M = cv2.moments(c)
            
            if M["m00"] != 0:
                # Calculate center coordinates (X and Y)
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # Map coordinates to MIDI values (0 to 127)
                # X position (0-320) -> MIDI Control Change 74 (Filter Cutoff)
                x_midi = int((cx / 320) * 127)
                # Y position (0-240) -> MIDI Control Change 11 (Expression)
                y_midi = int((cy / 240) * 127)
                
                # Only send MIDI if the position changed (prevents spamming the cable)
                if x_midi != prev_x_midi:
                    outport.send(mido.Message('control_change', control=74, value=x_midi))
                    prev_x_midi = x_midi
                    
                if y_midi != prev_y_midi:
                    outport.send(mido.Message('control_change', control=11, value=y_midi))
                    prev_y_midi = y_midi
                    
                print(f"X: {x_midi} (CC 74) | Y: {y_midi} (CC 11)")

        # Simple way to stop the loop (we will use Ctrl+C in terminal)
        time.sleep(0.05)

    cap.release()
    print("Test finished.")

if __name__ == "__main__":
    run_test()