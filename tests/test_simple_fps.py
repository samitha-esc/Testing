import cv2
import time

def test_simple_fps():
    print("🎥 Starting Simple FPS Test...")
    print("Press 'q' to quit\n")
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    
    frames = 0
    start_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to capture frame")
            break
        
        frames += 1
        
        # Calculate FPS every second
        elapsed = time.time() - start_time
        if elapsed >= 1.0:
            fps = frames / elapsed
            print(f"FPS: {fps:.2f}", end='\r')
            frames = 0
            start_time = time.time()
        
        # Show frame
        cv2.imshow('Simple FPS Test', frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    print("\n✅ Test complete!")

if __name__ == "__main__":
    test_simple_fps()