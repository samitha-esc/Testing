import cv2
import time
import argparse
import sys
import os

# Add the root directory to the path so we can import engines
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_fps_test(engine_class, engine_name):
    print(f"--- Starting FPS Test: {engine_name} ---")
    print("Loading engine...")
    
    engine = engine_class()
    engine.init()

    # Initialize Camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Error: Could not open camera.")
        return
    
    # Lower resolution for faster FPS testing
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

    frames = 0
    start_time = time.time()

    print("Tracking started. Press 'q' to quit.\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to capture frame.")
            break

        # Process frame through the engine
        display_frame, data = engine.process(frame)

        frames += 1
        
        # Calculate FPS every 1 second
        elapsed = time.time() - start_time
        if elapsed >= 1.0:
            fps = frames / elapsed
            # Print on the same line using \r
            print(f"Current FPS: {fps:.2f} | Data: {data}", end='\r')
            frames = 0
            start_time = time.time()

        # Show the result
        cv2.imshow(f'FPS Test: {engine_name}', display_frame)

        # Exit on 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    engine.close()
    print("\n✅ Test finished.")

if __name__ == "__main__":
    # This will be updated as we add real engines
    print("No engine selected. Modify this script to test specific engines.")