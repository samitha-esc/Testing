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
    if os.name == "nt":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def main():
    parser = argparse.ArgumentParser(description="Gesture MIDI Controller")
    parser.add_argument("--web", action="store_true",
                        help="Serve the browser UI (camera, live controls, "
                             "mode switch, mapping editor) over the network.")
    parser.add_argument("--port", type=int, default=8080,
                        help="Web UI port (default 8080).")
    parser.add_argument("--headless", action="store_true",
                        help="No GUI window; print gesture values to console.")
    parser.add_argument("--mode", default=None,
                        choices=["PLAY", "EXPRESSION", "DJ"],
                        help="Start in this mode.")
    parser.add_argument("--no-midi", action="store_true",
                        help="Skip MIDI (track + visualize only).")
    args = parser.parse_args()

    # In --web mode the browser is the display; never open a local cv2 window.
    headless = args.web or args.headless or not _has_display()

    print("🚀 Initializing Gesture MIDI Controller v5.0...")

    # 1. Camera once (reused for calibration + tracking).
    cam = Camera(device_id=0, width=640, height=480)
    cam.start()

    # 2. Calibration.
    calibrator = GloveCalibrator()
    calibrated_colors = calibrator.load_calibration()
    if calibrated_colors is None:
        print("\n⚠️  No calibration found! Starting calibration...")
        calibrated_colors = calibrator.calibrate(camera=cam)
        calibrator.save_calibration(calibrated_colors)
    else:
        print("✅ Using existing calibration.\n")

    # 3. MIDI (optional) — mapping engine exists either way so the UI works.
    midi = None
    mode_manager = ModeManager()
    if args.mode:
        mode_manager.handle_ui_switch(args.mode)

    if not args.no_midi:
        midi = MidiMapper()
        if not midi.connect():
            print("⚠️  MIDI unavailable — continuing in track-only mode.")
            midi = None

    mapping_engine = MappingEngine(midi, mode_manager)
    engine = GloveEngine(calibrated_colors=calibrated_colors)

    # 4. Web server (optional).
    shared_state = None
    server = None
    if args.web:
        from web.shared_state import SharedState
        from web.server import start_server
        shared_state = SharedState()
        server, _, url = start_server(shared_state, mapping_engine, port=args.port)
        print(f"\n🌐 Web UI running at:  {url}")
        print("   Open that on any device on the same network.\n")

    print(f"Starting in {mode_manager.current_mode} MODE")
    if not args.web and not headless:
        print("⌨️ '1' PLAY  '2' EXPRESSION  '3' DJ  |  'r' recalibrate  |  'q' quit")
    elif not args.web:
        print("⌨️ Ctrl+C to quit.")

    win = "Gesture MIDI Controller"
    fps = 0.0
    last_t = time.time()
    last_print = 0.0
    running = True

    try:
        while running:
            ret, frame = cam.get_frame()
            if not ret or frame is None:
                time.sleep(0.05)
                continue

            # --- handle UI commands (web) ---------------------------------
            if shared_state is not None:
                for cmd, payload in shared_state.drain_commands():
                    if cmd == "mode" and payload:
                        mode_manager.handle_ui_switch(payload)
                    elif cmd == "quit":
                        running = False
                    elif cmd == "recalibrate":
                        _push_status(shared_state, mode_manager, fps, midi,
                                     {}, {"controls": []}, calibrating=True)
                        print("\n🔄 Recalibrating (web request)...")
                        new_colors = calibrator.calibrate(camera=cam)
                        calibrator.save_calibration(new_colors)
                        engine.update_colors(new_colors)
                        print("✅ Recalibration complete!\n")

            gestures = engine.process(frame)
            mapout = mapping_engine.process_gestures(gestures)

            now = time.time()
            dt = now - last_t
            last_t = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            # --- output ---------------------------------------------------
            if shared_state is not None:
                overlay = engine.draw_overlay(
                    frame, gestures, mode=mode_manager.current_mode, fps=fps)
                ok, jpg = cv2.imencode(".jpg", overlay,
                                       [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ok:
                    shared_state.set_frame(jpg.tobytes())
                _push_status(shared_state, mode_manager, fps, midi,
                             gestures, mapout)

            elif headless:
                if now - last_print >= 0.2:
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
                    print("\n🔄 Recalibrating...")
                    new_colors = calibrator.calibrate(camera=cam)
                    calibrator.save_calibration(new_colors)
                    engine.update_colors(new_colors)
                    print("✅ Done!\n")
                elif key == ord('q'):
                    running = False

            mode_manager.tick()

    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        if server is not None:
            server.shutdown()
        cam.release()
        engine.release()
        calibrator.release()
        if midi is not None:
            midi.disconnect()
        if not headless:
            cv2.destroyAllWindows()


def _marker_bools(gestures):
    mk = gestures.get('_markers', {}) if gestures else {}
    return {name: (mk.get(name) is not None) for name in ("wrist", "thumb", "index")}


def _push_status(shared_state, mode_manager, fps, midi, gestures, mapout,
                 calibrating=False):
    hand = ("OPEN" if gestures.get('OPEN_PALM')
            else ("FIST" if gestures.get('FIST') else "—")) if gestures else "—"
    shared_state.set_status({
        "mode": mode_manager.current_mode,
        "fps": round(fps, 1),
        "hand": hand,
        "oob": bool(gestures.get('OUT_OF_BOUNDS')) if gestures else False,
        "markers": _marker_bools(gestures),
        "midi": (midi.port.name if (midi and midi.port) else None),
        "calibrating": calibrating,
        "controls": mapout.get("controls", []),
    })


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
