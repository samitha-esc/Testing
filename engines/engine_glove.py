import cv2
import numpy as np
import math
import threading
import queue
from engines.base_engine import BaseEngine


class GloveEngine(BaseEngine):
    """
    Hybrid glove tracker: OpenCV HSV every frame (fast path) guided by
    MediaPipe landmarks (background thread, every 5th frame).

    Detection priority per marker, each frame:
      1. HSV search in small ROI around last-found centroid  (position continuity)
      2. HSV search in ROI around latest MediaPipe landmark  (MP fallback)
      3. HSV search across the full frame                    (cold-start / lost)

    This means:
      - Once a marker is locked on, it stays locked via step 1 regardless of
        what else in the scene shares the same hue.
      - After a complete loss (fist, OOB), step 2 guides the re-lock so the
        arm/background is never picked over the actual fingertip.
      - MediaPipe overhead (~30ms) is fully off the hot path; the main loop
        always runs at camera FPS.
    """

    PROC_W = 320
    PROC_H = 240
    OOB_MARGIN = 0.06
    MP_EVERY_N = 5      # run MediaPipe once every N frames
    ROI_RADIUS  = 70    # pixels at PROC resolution for continuity/MP hint search

    def __init__(self, calibrated_colors: dict = None):
        self.default_colors = {
            'wrist': (np.array([20, 100, 100]), np.array([35, 255, 255])),
            'thumb': (np.array([0,  120, 100]), np.array([15, 255, 255])),
            'index': (np.array([100, 100, 100]), np.array([130, 255, 255])),
        }
        self.colors = dict(self.default_colors)
        if calibrated_colors:
            self.update_colors(calibrated_colors, quiet=True)

        self.alpha = 0.3
        self.prev_state  = {'x': None, 'y': None, 'tilt': None, 'pinch': None}
        self.prev_index  = {'x': None, 'y': None}

        # Last successfully found centroid (normalized 0..1) per marker.
        # Used to build the position-continuity ROI each frame.
        self._last_centroid = {'wrist': None, 'thumb': None, 'index': None}

        self._kernel = np.ones((3, 3), np.uint8)
        self._frame_count = 0

        # --- MediaPipe background worker -----------------------------------
        # Stores the latest normalized landmark positions from MP.
        self._mp_landmarks = None   # {'wrist':(x,y), 'thumb':(x,y), 'index':(x,y)}
        self._mp_lock = threading.Lock()
        self._mp_queue = queue.Queue(maxsize=1)  # drop frames if worker is busy
        self._mp_thread = threading.Thread(target=self._mp_worker, daemon=True)
        self._mp_thread.start()

    # ------------------------------------------------------------------ #
    # MediaPipe background worker
    # ------------------------------------------------------------------ #
    def _mp_worker(self):
        import mediapipe as mp
        hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        while True:
            frame_bgr = self._mp_queue.get()
            if frame_bgr is None:
                break
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)
            if result.multi_hand_landmarks:
                lm = result.multi_hand_landmarks[0].landmark
                lms = {
                    'wrist': (lm[0].x, lm[0].y),
                    'thumb': (lm[4].x, lm[4].y),
                    'index': (lm[8].x, lm[8].y),
                }
            else:
                lms = None
            with self._mp_lock:
                self._mp_landmarks = lms

    # ------------------------------------------------------------------ #
    # Calibration hook
    # ------------------------------------------------------------------ #
    def update_colors(self, calibrated_colors: dict, quiet: bool = False):
        new_colors = {}
        for marker, ranges in calibrated_colors.items():
            new_colors[marker] = (
                np.array(ranges['lower'], dtype=np.uint8),
                np.array(ranges['upper'], dtype=np.uint8),
            )
        for marker, rng in self.default_colors.items():
            new_colors.setdefault(marker, rng)
        self.colors = new_colors
        # Reset last-known centroids so the engine doesn't carry stale positions.
        self._last_centroid = {'wrist': None, 'thumb': None, 'index': None}
        if not quiet:
            print("Glove colors updated!")

    # ------------------------------------------------------------------ #
    # Main processing
    # ------------------------------------------------------------------ #
    def process(self, frame):
        self._frame_count += 1

        # Feed the MP worker every N frames (non-blocking — drop if busy).
        if self._frame_count % self.MP_EVERY_N == 0:
            if not self._mp_queue.full():
                # Resize to proc resolution before sending to reduce MP latency.
                self._mp_queue.put_nowait(
                    cv2.resize(frame, (self.PROC_W, self.PROC_H),
                               interpolation=cv2.INTER_NEAREST))

        small = cv2.resize(frame, (self.PROC_W, self.PROC_H),
                           interpolation=cv2.INTER_NEAREST)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)

        # Snapshot of latest MP landmarks (may be None).
        with self._mp_lock:
            mp_lms = self._mp_landmarks

        wrist = self._find_marker(hsv, 'wrist', mp_lms, min_area=80)
        thumb = self._find_marker(hsv, 'thumb', mp_lms, min_area=25)
        index = self._find_marker(hsv, 'index', mp_lms, min_area=25)

        gestures = {
            '_markers': {
                'wrist': self._to_px(wrist, frame),
                'thumb': self._to_px(thumb, frame),
                'index': self._to_px(index, frame),
            }
        }

        if wrist is None:
            gestures['FIST'] = True
            gestures['OPEN_PALM'] = False
            gestures['OUT_OF_BOUNDS'] = False
            self.prev_state = {'x': None, 'y': None, 'tilt': None, 'pinch': None}
            self.prev_index = {'x': None, 'y': None}
            return gestures

        wx, wy = wrist

        if thumb is not None and index is not None:
            gestures['OPEN_PALM'] = True
            gestures['FIST'] = False
        elif thumb is None and index is None:
            gestures['OPEN_PALM'] = False
            gestures['FIST'] = True
        else:
            gestures['OPEN_PALM'] = False
            gestures['FIST'] = False

        hand_x = self._smooth('x', wx)
        hand_y = self._smooth('y', 1.0 - wy)
        gestures['HAND_X'] = hand_x
        gestures['HAND_Y'] = hand_y

        m = self.OOB_MARGIN
        gestures['OUT_OF_BOUNDS'] = (
            wx < m or wx > 1 - m or wy < m or wy > 1 - m
        )

        if thumb is not None and index is not None:
            tx, ty = thumb
            ix, iy = index
            dist = math.hypot(ix - tx, iy - ty)
            gestures['PINCH'] = self._smooth('pinch',
                                             max(0.0, min(1.0, dist / 0.35)))
            angle = math.atan2(ix - wx, (1.0 - iy) - (1.0 - wy))
            gestures['TILT'] = self._smooth('tilt',
                                            max(-1.0, min(1.0, angle / (math.pi / 2))))

        if self.prev_state['x'] is not None:
            gestures['HAND_DELTA_X'] = hand_x - self.prev_state['x']
            gestures['HAND_DELTA_Y'] = hand_y - self.prev_state['y']
        if index is not None and self.prev_index['x'] is not None:
            gestures['INDEX_DELTA_X'] = index[0] - self.prev_index['x']
            gestures['INDEX_DELTA_Y'] = self.prev_index['y'] - index[1]

        self.prev_state['x'] = hand_x
        self.prev_state['y'] = hand_y
        self.prev_index = {'x': index[0], 'y': index[1]} if index else {'x': None, 'y': None}

        return gestures

    # ------------------------------------------------------------------ #
    # Layered marker search
    # ------------------------------------------------------------------ #
    def _find_marker(self, hsv, marker, mp_lms, min_area):
        """Three-tier search: continuity ROI → MP hint ROI → full frame."""
        color = self.colors[marker]

        # 1. Position-continuity ROI (last found position).
        last = self._last_centroid[marker]
        if last is not None:
            cx = int(last[0] * self.PROC_W)
            cy = int(last[1] * self.PROC_H)
            result = self._get_centroid(hsv, color, min_area,
                                        roi_center=(cx, cy),
                                        roi_radius=self.ROI_RADIUS)
            if result is not None:
                self._last_centroid[marker] = result
                return result

        # 2. MediaPipe landmark hint.
        if mp_lms and marker in mp_lms:
            mx, my = mp_lms[marker]
            cx = int(mx * self.PROC_W)
            cy = int(my * self.PROC_H)
            result = self._get_centroid(hsv, color, min_area,
                                        roi_center=(cx, cy),
                                        roi_radius=self.ROI_RADIUS)
            if result is not None:
                self._last_centroid[marker] = result
                return result

        # 3. Full-frame fallback (cold-start or complete loss).
        result = self._get_centroid(hsv, color, min_area)
        self._last_centroid[marker] = result
        return result

    # ------------------------------------------------------------------ #
    # Core HSV centroid detector
    # ------------------------------------------------------------------ #
    def _get_centroid(self, hsv, color_range, min_area,
                      roi_center=None, roi_radius=None):
        """
        Return (cx, cy) normalized to 0..1, or None.

        If roi_center + roi_radius are given, the color mask is AND-ed with
        a rectangular ROI mask so only blobs in that region are considered.
        Handles red hue wrap (lower H > upper H).
        """
        lower, upper = color_range
        if lower[0] > upper[0]:
            lo1 = np.array([0,         lower[1], lower[2]], dtype=np.uint8)
            hi1 = np.array([upper[0],  upper[1], upper[2]], dtype=np.uint8)
            lo2 = np.array([lower[0],  lower[1], lower[2]], dtype=np.uint8)
            hi2 = np.array([179,       upper[1], upper[2]], dtype=np.uint8)
            mask = cv2.bitwise_or(cv2.inRange(hsv, lo1, hi1),
                                  cv2.inRange(hsv, lo2, hi2))
        else:
            mask = cv2.inRange(hsv, lower, upper)

        mask = cv2.erode(mask,  self._kernel, iterations=1)
        mask = cv2.dilate(mask, self._kernel, iterations=2)

        # Apply ROI if provided.
        if roi_center is not None and roi_radius is not None:
            cx, cy = roi_center
            r = roi_radius
            roi_mask = np.zeros(mask.shape, dtype=np.uint8)
            x1, y1 = max(0, cx - r), max(0, cy - r)
            x2, y2 = min(self.PROC_W, cx + r), min(self.PROC_H, cy + r)
            roi_mask[y1:y2, x1:x2] = 255
            mask = cv2.bitwise_and(mask, roi_mask)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        best = max(contours, key=cv2.contourArea)
        if cv2.contourArea(best) < min_area:
            return None
        M = cv2.moments(best)
        if M["m00"] == 0:
            return None
        return (M["m10"] / M["m00"] / self.PROC_W,
                M["m01"] / M["m00"] / self.PROC_H)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _smooth(self, key, value):
        prev = self.prev_state.get(key)
        if prev is None:
            self.prev_state[key] = value
            return value
        sm = self.alpha * value + (1 - self.alpha) * prev
        self.prev_state[key] = sm
        return sm

    @staticmethod
    def _to_px(norm_pt, frame):
        if norm_pt is None:
            return None
        h, w = frame.shape[:2]
        return (int(norm_pt[0] * w), int(norm_pt[1] * h))

    # ------------------------------------------------------------------ #
    # Debug overlay
    # ------------------------------------------------------------------ #
    def draw_overlay(self, frame, gestures, mode="", fps=0.0):
        out = frame.copy()
        markers = gestures.get('_markers', {})
        colors = {'wrist': (0, 255, 255), 'thumb': (0, 0, 255), 'index': (255, 0, 0)}

        w_pt = markers.get('wrist')
        i_pt = markers.get('index')
        t_pt = markers.get('thumb')

        if w_pt and i_pt:
            cv2.line(out, w_pt, i_pt, (200, 200, 200), 2)
        if t_pt and i_pt:
            cv2.line(out, t_pt, i_pt, (200, 200, 200), 2)

        for name, pt in markers.items():
            if pt is not None:
                cv2.circle(out, pt, 10, colors[name], -1)
                cv2.circle(out, pt, 10, (0, 0, 0), 2)
                cv2.putText(out, name, (pt[0] + 12, pt[1]),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, colors[name], 1)

        lines = [f"MODE: {mode}    FPS: {fps:4.1f}"]
        state = ("OPEN_PALM" if gestures.get('OPEN_PALM')
                 else ("FIST" if gestures.get('FIST') else "..."))
        lines.append(f"HAND: {state}")
        for k in ('HAND_X', 'HAND_Y', 'PINCH', 'TILT'):
            if k in gestures:
                lines.append(f"{k}: {gestures[k]:+.2f}")

        y = 24
        for ln in lines:
            cv2.putText(out, ln, (10, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 0, 0), 3)
            cv2.putText(out, ln, (10, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 255, 0), 1)
            y += 24

        if gestures.get('OUT_OF_BOUNDS'):
            h, w = out.shape[:2]
            cv2.rectangle(out, (0, 0), (w - 1, h - 1), (0, 0, 255), 6)
            cv2.putText(out, "HAND OUT OF BOUNDS", (w // 2 - 150, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        return out

    def release(self):
        self._mp_queue.put(None)   # signal worker to exit
        self._mp_thread.join(timeout=3.0)
