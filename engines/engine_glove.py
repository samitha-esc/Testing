import cv2
import numpy as np
import math
from engines.base_engine import BaseEngine


class GloveEngine(BaseEngine):
    """
    Pure-OpenCV glove tracker. Detects three colored markers
    (wrist=yellow, thumb=red, index=blue) and derives gestures from
    their centroids. MediaPipe is intentionally kept OUT of this hot
    path (it is only used at calibration) to keep latency minimal.

    Emits a gesture dict consumed by utils.mapping_engine.MappingEngine:
        FIST, OPEN_PALM            (bool)
        HAND_X, HAND_Y, PINCH      (float 0..1)
        TILT                       (float -1..1)
        HAND_DELTA_X, HAND_DELTA_Y (float, per-frame)
        INDEX_DELTA_X, INDEX_DELTA_Y
        OUT_OF_BOUNDS              (bool)
    Plus a private '_markers' entry (pixel centroids) for the debug overlay.
    """

    # Internal processing resolution. Tracking is resolution-independent
    # (we normalize to 0..1), so we run the masks on a small frame for speed.
    PROC_W = 320
    PROC_H = 240

    # Fraction of the frame edge treated as "out of bounds" margin.
    OOB_MARGIN = 0.06

    def __init__(self, calibrated_colors: dict = None):
        # Default fallback HSV ranges (OpenCV H: 0-179).
        self.default_colors = {
            'wrist': (np.array([20, 100, 100]), np.array([35, 255, 255])),   # yellow
            'thumb': (np.array([0, 100, 100]),  np.array([15, 255, 255])),   # red
            'index': (np.array([100, 100, 100]), np.array([130, 255, 255])),  # blue
        }

        self.colors = dict(self.default_colors)
        if calibrated_colors:
            self.update_colors(calibrated_colors, quiet=True)

        # Exponential smoothing factor for positions (0..1, lower = smoother).
        self.alpha = 0.3

        # Smoothed normalized state from the previous frame.
        self.prev_state = {'x': None, 'y': None, 'tilt': None, 'pinch': None}
        # Previous index position (for INDEX_DELTA).
        self.prev_index = {'x': None, 'y': None}

        # Reusable morphology kernel.
        self._kernel = np.ones((3, 3), np.uint8)

    # ------------------------------------------------------------------ #
    # Calibration hook
    # ------------------------------------------------------------------ #
    def update_colors(self, calibrated_colors: dict, quiet: bool = False):
        """Apply HSV ranges from a calibration dict (after recalibration)."""
        new_colors = {}
        for marker, ranges in calibrated_colors.items():
            new_colors[marker] = (
                np.array(ranges['lower'], dtype=np.uint8),
                np.array(ranges['upper'], dtype=np.uint8),
            )
        # Keep any marker the calibration didn't provide.
        for marker, rng in self.default_colors.items():
            new_colors.setdefault(marker, rng)
        self.colors = new_colors
        if not quiet:
            print("🎨 Glove colors updated!")

    # ------------------------------------------------------------------ #
    # Main processing
    # ------------------------------------------------------------------ #
    def process(self, frame):
        small = cv2.resize(frame, (self.PROC_W, self.PROC_H),
                           interpolation=cv2.INTER_NEAREST)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)

        wrist = self._get_centroid(hsv, self.colors['wrist'], min_area=120)
        thumb = self._get_centroid(hsv, self.colors['thumb'], min_area=40)
        index = self._get_centroid(hsv, self.colors['index'], min_area=40)

        gestures = {
            '_markers': {
                'wrist': self._to_px(wrist, frame),
                'thumb': self._to_px(thumb, frame),
                'index': self._to_px(index, frame),
            }
        }

        # No wrist => treat as "no hand" => fist / stop.
        if wrist is None:
            gestures['FIST'] = True
            gestures['OPEN_PALM'] = False
            gestures['OUT_OF_BOUNDS'] = False
            self.prev_state = {'x': None, 'y': None, 'tilt': None, 'pinch': None}
            self.prev_index = {'x': None, 'y': None}
            return gestures

        wx, wy = wrist  # normalized 0..1

        # --- Hand open/closed from fingertip-marker presence ---------- #
        if thumb is not None and index is not None:
            gestures['OPEN_PALM'] = True
            gestures['FIST'] = False
        elif thumb is None and index is None:
            gestures['OPEN_PALM'] = False
            gestures['FIST'] = True
        else:
            gestures['OPEN_PALM'] = False
            gestures['FIST'] = False

        # --- Absolute hand position (Y inverted so "up" = 1.0) -------- #
        hand_x = self._smooth('x', wx)
        hand_y = self._smooth('y', 1.0 - wy)
        gestures['HAND_X'] = hand_x
        gestures['HAND_Y'] = hand_y

        # --- Out-of-bounds alert -------------------------------------- #
        m = self.OOB_MARGIN
        gestures['OUT_OF_BOUNDS'] = (
            wx < m or wx > 1 - m or wy < m or wy > 1 - m
        )

        # --- Pinch + tilt (need both fingertip markers) --------------- #
        if thumb is not None and index is not None:
            tx, ty = thumb
            ix, iy = index
            dist = math.hypot(ix - tx, iy - ty)
            # Normalized distance; ~0 touching, ~0.35 wide spread.
            pinch = max(0.0, min(1.0, dist / 0.35))
            gestures['PINCH'] = self._smooth('pinch', pinch)

            # Tilt: angle of wrist->index vector from vertical, mapped -1..1.
            angle = math.atan2(ix - wx, (1.0 - iy) - (1.0 - wy))
            gestures['TILT'] = self._smooth('tilt',
                                            max(-1.0, min(1.0, angle / (math.pi / 2))))

        # --- Per-frame deltas (relative control) ---------------------- #
        if self.prev_state['x'] is not None:
            gestures['HAND_DELTA_X'] = hand_x - self.prev_state['x']
            gestures['HAND_DELTA_Y'] = hand_y - self.prev_state['y']
        if index is not None and self.prev_index['x'] is not None:
            gestures['INDEX_DELTA_X'] = index[0] - self.prev_index['x']
            # Screen-y delta (down = positive); invert to "up = positive".
            gestures['INDEX_DELTA_Y'] = self.prev_index['y'] - index[1]

        # Stash current smoothed/raw positions for next frame.
        self.prev_state['x'] = hand_x
        self.prev_state['y'] = hand_y
        if index is not None:
            self.prev_index = {'x': index[0], 'y': index[1]}
        else:
            self.prev_index = {'x': None, 'y': None}

        return gestures

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_centroid(self, hsv, color_range, min_area):
        """Return (cx, cy) normalized to 0..1, or None. Handles red hue wrap."""
        lower, upper = color_range
        if lower[0] > upper[0]:
            # Hue wraps past 179 (red): OR the two sub-ranges.
            lo1 = np.array([0, lower[1], lower[2]], dtype=np.uint8)
            hi1 = np.array([upper[0], upper[1], upper[2]], dtype=np.uint8)
            lo2 = np.array([lower[0], lower[1], lower[2]], dtype=np.uint8)
            hi2 = np.array([179, upper[1], upper[2]], dtype=np.uint8)
            mask = cv2.bitwise_or(cv2.inRange(hsv, lo1, hi1),
                                  cv2.inRange(hsv, lo2, hi2))
        else:
            mask = cv2.inRange(hsv, lower, upper)

        mask = cv2.erode(mask, self._kernel, iterations=1)
        mask = cv2.dilate(mask, self._kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) < min_area:
            return None
        M = cv2.moments(c)
        if M["m00"] == 0:
            return None
        cx = (M["m10"] / M["m00"]) / self.PROC_W
        cy = (M["m01"] / M["m00"]) / self.PROC_H
        return (cx, cy)

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
    # Debug overlay (so gestures can be tested visually)
    # ------------------------------------------------------------------ #
    def draw_overlay(self, frame, gestures, mode="", fps=0.0):
        """Draw markers, links and live gesture values onto a copy of frame."""
        out = frame.copy()
        markers = gestures.get('_markers', {})
        colors = {'wrist': (0, 255, 255), 'thumb': (0, 0, 255),
                  'index': (255, 0, 0)}

        w_pt = markers.get('wrist')
        i_pt = markers.get('index')
        t_pt = markers.get('thumb')

        # Connect markers to visualize the hand "skeleton".
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

        # HUD text.
        lines = [f"MODE: {mode}    FPS: {fps:4.1f}"]
        state = "OPEN_PALM" if gestures.get('OPEN_PALM') else \
                ("FIST" if gestures.get('FIST') else "...")
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
        pass
