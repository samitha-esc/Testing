import cv2
import time
import sys

from utils.camera import Camera
from utils.mode_manager import ModeManager
from utils.midi_mapper import MidiMapper
from utils.mapping_engine import MappingEngine

# Import the engines
from engines.engine_glove import GloveEngine
# from engines.engine_medipipe import MediapipeEngine
# from engines.engine_color_modes import ColorModesEngine

def main():
    print(" Initializing Gesture MIDI Controller v3.0 (Glove Mode)...")
    
    # 1. Initialize MIDI
    midi = MidiMapper()
    if not midi.connect():
        sys.exit(1)
        
    # 2. Initialize Mode Manager and Mapping Engine
    mode_manager = ModeManager()
    mapping_engine = MappingEngine(midi, mode_manager)
    
    # 3. Initialize Camera
    # Note: 640x480 is good for glove tracking, but 320x240 is faster if needed
    cam = Camera(device_id=0, width=640, height=480)
    cam.start()
    
    # 4. Choose your Engine
    # Currently using the 3-Marker Glove for low latency
    engine = GloveEngine()
    
    print(f" Starting in {mode_manager.current_mode} MODE")
    print("🧤 Glove Engine Active: Yellow (Wrist), Red (Thumb), Blue (Index)")
    print("⌨️ Press '1' for PLAY mode, '2' for EXPRESSION, '3' for DJ mode")
    print("⌨️ Press 'q' to quit")
    
    try:
        while True:
            ret, frame = cam.get_frame()
            if not ret:
                print("️ Failed to grab frame")
                break
            
            # Process frame through the chosen engine
            # GloveEngine.process() returns only the gestures dictionary
            gestures = engine.process(frame)
            
            # Map gestures to MIDI
            if gestures:
                mapping_engine.process_gestures(gestures)
            
            # Keyboard shortcuts for mode switching
            # (Crucial since the glove can't easily do the 'OK sign' gesture)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('1'):
                mode_manager.handle_ui_switch("PLAY")
            elif key == ord('2'):
                mode_manager.handle_ui_switch("EXPRESSION")
            elif key == ord('3'):
                mode_manager.handle_ui_switch("DJ")
            elif key == ord('q'):
                break
            
            # Update mode manager cooldowns
            mode_manager.tick()
            
            # Optional: Show debug window (if you have monitor connected)
            # cv2.imshow('Gesture Control', frame)
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        cam.release()
        engine.release()
        midi.disconnect()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()