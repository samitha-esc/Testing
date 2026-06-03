import cv2
import time
import sys
import os

# Add root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.engine_color import ColorEngine

def test_color_tracking():
    print("🎨 Starting Color Tracking Test...")
    print("Make sure you have a colored object (green recommended) in view")
    print("Press 'q' to quit\n")
    
    # Initialize engine (change color if needed: 'red', 'blue', 'orange', 'yellow')
    engine = ColorEngine(color='green')
    engine.init()
    
    # Initialize camera
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    
    if not cap.isOpened():
        print("❌ Error: Could not open camera")
        return
    
    frames = 0
    start_time = time.time()
    
    print("Tracking started...\n")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to capture frame")
            break
        
        # Process frame through engine
        display_frame, data = engine.process(frame)
        
        frames += 1
        
        # Calculate FPS every second
        elapsed = time.time() - start_time
        if elapsed >= 1.0:
            fps = frames / elapsed
            status = f"DETECTED (X:{data['x']} Y:{data['y']})" if data['detected'] else "NOT DETECTED"
            print(f"FPS: {fps:.2f} | {status}", end='\r')
            frames = 0
            start_time = time.time()
        
        # Show result
        cv2.imshow('Color Tracking Test', display_frame)
        
        # Exit on 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    engine.close()
    print("\n✅ Test complete!")

if __name__ == "__main__":
    test_color_tracking()