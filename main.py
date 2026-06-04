import cv2
import time
import sys
import os
import argparse

from utils.camera import Camera
from utils.mode_manager import ModeManager
from utils.midi_mapper import MidiMapper
from utils.mapping_engine import MappingEngine
from utils.calibration import GloveCalibrator

from engines.engine_glove import GloveEngine


def _has_display():
    """True if a GUI window can plausibly be shown (X / Wayland present)."""
    if os.name == "nt":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def main():
    parser = argparse.ArgumentParser(description="Gesture MIDI Controller")
    parser.add_argument("--headless", action="store_true",
                        help="No GUI window; print gesture values to console "
                             "(use for SSH). Mode via console is fixed unless "
                             "set with --mode.")
    parser.add_argument("--mode", default=None,
                        choices=["PLAY", "EXPRESSION", "DJ"],
                        help="Start in this mode.")
    parser.add_argument("--no-midi", action="store_true",
                        help="Skip MIDI (track + visualize only).")
    args = parser.parse_args()

    headless = args.headless or not _has_display()

    print("🚀 Initializing Gesture MIDI Controller v4.0 (Auto-Calibrating)...")
    if headless:
        print("🖥️  Headless mode: printing gesture values to console.")

    # 1. Open the camera ONCE — reused for calibration and tracking
    #    (/dev/video0 cannot be opened twice concurrently).
    cam = Camera(device_id=0, width=640, height=480)
    cam.start()

    # 2. CALIBRATION CHECK
    calibrator = GloveCalibrator()
    calibrated_colors = calibrator.load_calibration()

    if calibrated_colors is None:
        print("\n⚠️  No calibration found! Starting calibration...")
        calibrated_colors = calibrator.calibrate(camera=cam)
        calibrator.save_calibration(calibrated_colors)
        print("✅ Calibration saved. Starting tracking...\n")
    else:
        print("✅ Using existing calibration from config/glove_colors.json\n")

    # 3. Initialize MIDI
    midi = None
    mapping_engine = None
    mode_manager = ModeManager()
    if args.mode:
        mode_manager.handle_ui_switch(args.mode)

    if not args.no_midi:
        midi = MidiMapper()
        if not midi.connect():
            print("❌ MIDI unavailable. Re-run with --no-midi to track only.")
            cam.release()
            sys.exit(1)
        mapping_engine = MappingEngine(midi, mode_manager)

    # 4. Engine
    engine = GloveEngine(calibrated_colors=calibrated_colors)

    print(f" Starting in {mode_manager.current_mode} MODE")
    print("🧤 Glove Engine Active (Auto-Calibrated)")
    if headless:
        print("⌨️ Ctrl+C to quit. Use --mode to choose mode in headless.")
    else:
        print("⌨️ '1' PLAY, '2' EXPRESSION, '3' DJ | 'r' recalibrate | 'q' quit")

    win = "Gesture MIDI Controller"
    fps = 0.0
    last_t = time.time()
    last_print = 0.0

    try:
        while True:
            ret, frame = cam.get_frame()
            if not ret or frame is None:
                print("⚠️ Failed to grab frame")
                time.sleep(0.1)
                continue

            gestures = engine.process(frame)

            if gestures and mapping_engine is not None:
                mapping_engine.process_gestures(gestures)

            # FPS (EMA).
            now = time.time()
            dt = now - last_t
            last_t = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            if headless:
                if now - last_print >= 0.2:  # 5 Hz console refresh
                    _print_gesture_line(gestures, mode_manager.current_mode, fps)
                    last_print = now
            else:
                overlay = engine.draw_overlay(
                    frame, gestures, mode=mode_manager.current_mode, fps=fps)
                cv2.imshow(win, overlay)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('1'):
                    mode_manager.handle_ui_switch("PLAY")
                elif key == ord('2'):
                    mode_manager.handle_ui_switch("EXPRESSION")
                elif key == ord('3'):
                    mode_manager.handle_ui_switch("DJ")
                elif key == ord('r'):
                    print("\n🔄 Starting recalibration...")
                    new_colors = calibrator.calibrate(camera=cam)
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
        calibrator.release()
        if midi is not None:
            midi.disconnect()
        if not headless:
            cv2.destroyAllWindows()


def _print_gesture_line(gestures, mode, fps):
    state = "OPEN" if gestures.get('OPEN_PALM') else \
            ("FIST" if gestures.get('FIST') else "....")
    oob = "OOB!" if gestures.get('OUT_OF_BOUNDS') else "   "
    parts = [f"[{mode:10}]", f"{fps:4.1f}fps", state, oob]
    for k in ('HAND_X', 'HAND_Y', 'PINCH', 'TILT'):
        if k in gestures:
            parts.append(f"{k.split('_')[-1]}={gestures[k]:+.2f}")
    print("  ".join(parts) + " " * 8, end="\r", flush=True)


if __name__ == "__main__":
    main()
