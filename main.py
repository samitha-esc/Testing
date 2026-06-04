import cv2
import time
import sys

from utils.camera import Camera
from utils.mode_manager import ModeManager
from utils.midi_mapper import MidiMapper
from utils.mapping_engine import MappingEngine
from utils.calibration import GloveCalibrator

from engines.engine_glove import GloveEngine

def main():
    print("🚀 Initializing Gesture MIDI Controller v4.0 (Auto-Calibrating)...")
    
    # 1. CALIBRATION CHECK
    calibrator = GloveCalibrator()
    calibrated_colors = calibrator.load_calibration()
    
    if calibrated_colors is None:
        print("\n⚠️  No calibration found! Starting calibration...")
        calibrated_colors = calibrator.calibrate()
        calibrator.save_calibration(calibrated_colors)
        print("✅ Calibration saved. Starting tracking...\n")
    else:
        print("✅ Using existing calibration from config/glove_colors.json\n")
    
    # 2. Initialize MIDI
    midi = MidiMapper()
    if not midi.connect():
        sys.exit(1)
        
    mode_manager = ModeManager()
    mapping_engine = MappingEngine(midi, mode_manager)
    
    cam = Camera(device_id=0, width=640, height=480)
    cam.start()
    
    engine = GloveEngine(calibrated_colors=calibrated_colors)
    
    print(f" Starting in {mode_manager.current_mode} MODE")
    print("🧤 Glove Engine Active (Auto-Calibrated)")
    print("⌨️ Press '1' for PLAY, '2' for EXPRESSION, '3' for DJ")
    print("⌨️ Press 'r' to recalibrate colors, 'q' to quit")
    
    try:
        while True:
            ret, frame = cam.get_frame()
            if not ret or frame is None:
                print("⚠️ Failed to grab frame")
                time.sleep(0.1)
                continue
            
            gestures = engine.process(frame)
            
            if gestures:
                mapping_engine.process_gestures(gestures)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('1'):
                mode_manager.handle_ui_switch("PLAY")
            elif key == ord('2'):
                mode_manager.handle_ui_switch("EXPRESSION")
            elif key == ord('3'):
                mode_manager.handle_ui_switch("DJ")
            elif key == ord('r'):
                print("\n🔄 Starting recalibration...")
                new_colors = calibrator.calibrate()
                calibrator.save_calibration(new_colors)
                engine.update_colors(new_colors)
                print("✅ Recalibration complete!\n")
            elif key == ord('q'):
                break
            
            mode_manager.tick()
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        cam.release()
        engine.release()
        midi.disconnect()

if __name__ == "__main__":
    main()