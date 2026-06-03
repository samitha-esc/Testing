import cv2
import mediapipe as mp
import math
import numpy as np

class GestureDetector:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        # For calculating relative movement (delta)
        self.prev_landmarks = None
        
    def process_frame(self, frame):
        """
        Main entry point. Takes a camera frame and returns:
        - gestures dict (all detected gestures)
        - frame with visualizations (for debugging)
        """
        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        gestures = {}
        debug_frame = frame.copy()
        
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Draw landmarks for debugging
                self.mp_draw.draw_landmarks(debug_frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                
                # Detect all gestures
                gestures = self._detect_all_gestures(hand_landmarks)
                
                # Calculate delta (relative movement)
                if self.prev_landmarks:
                    gestures.update(self._calculate_delta(hand_landmarks, self.prev_landmarks))
                
                self.prev_landmarks = hand_landmarks
        else:
            self.prev_landmarks = None
            
        return gestures, debug_frame

    def _detect_all_gestures(self, landmarks):
        """Detects all possible gestures from landmarks"""
        gestures = {}
        lm = landmarks.landmark
        
        # 1. Detect which fingers are extended
        fingers = self._get_finger_states(lm)
        
        # 2. Detect specific gestures based on finger states
        gestures.update(self._detect_specific_gestures(lm, fingers))
        
        # 3. Detect absolute positions
        gestures.update(self._detect_absolute_positions(lm))
        
        return gestures

    def _get_finger_states(self, lm):
        """Returns list of booleans: [thumb, index, middle, ring, pinky]"""
        fingers = []
        
        # Thumb (special case - moves sideways)
        if lm[4].x < lm[3].x:  # Thumb tip left of IP joint (right hand)
            fingers.append(True)
        else:
            fingers.append(False)
            
        # Other 4 fingers (tip above PIP joint = extended)
        tip_ids = [8, 12, 16, 20]
        pip_ids = [6, 10, 14, 18]
        
        for tip_id, pip_id in zip(tip_ids, pip_ids):
            if lm[tip_id].y < lm[pip_id].y:
                fingers.append(True)
            else:
                fingers.append(False)
                
        return fingers

    def _detect_specific_gestures(self, lm, fingers):
        """Detects named gestures like FIST, OPEN_PALM, POINT, etc."""
        gestures = {}
        
        # FIST (all fingers down)
        if fingers == [False, False, False, False, False]:
            gestures['FIST'] = True
            
        # OPEN_PALM (all fingers up)
        elif fingers == [True, True, True, True, True]:
            gestures['OPEN_PALM'] = True
            
        # POINT (only index up)
        elif fingers == [False, True, False, False, False]:
            gestures['POINT'] = True
            
        # OK SIGN (thumb and index touching, others down)
        elif fingers == [False, False, True, True, True]:
            # Check if thumb and index tips are close
            dist = math.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y)
            if dist < 0.05:
                gestures['OK_SIGN'] = True
        
        return gestures

    def _detect_absolute_positions(self, lm):
        """Gets absolute positions (0.0 to 1.0) for various hand parts"""
        return {
            'INDEX_X': lm[8].x,
            'INDEX_Y': lm[8].y,
            'HAND_X': lm[0].x,  # Wrist
            'HAND_Y': lm[0].y,
            'PINCH': self._calculate_pinch(lm),
        }

    def _calculate_pinch(self, lm):
        """Returns pinch distance (0.0 = touching, 1.0 = max stretch)"""
        thumb_tip = np.array([lm[4].x, lm[4].y, lm[4].z])
        index_tip = np.array([lm[8].x, lm[8].y, lm[8].z])
        distance = np.linalg.norm(thumb_tip - index_tip)
        # Normalize: typical max pinch is ~0.15
        return max(0.0, min(1.0, distance * 7))

    def _calculate_delta(self, current_lm, prev_lm):
        """Calculates relative movement (delta) between frames"""
        curr = current_lm.landmark
        prev = prev_lm.landmark
        
        # Calculate hand movement
        delta_x = curr[0].x - prev[0].x  # Wrist X movement
        delta_y = curr[0].y - prev[0].y  # Wrist Y movement
        
        # Calculate index finger movement
        index_delta_x = curr[8].x - prev[8].x
        index_delta_y = curr[8].y - prev[8].y
        
        return {
            'HAND_DELTA_X': delta_x,
            'HAND_DELTA_Y': delta_y,
            'INDEX_DELTA_X': index_delta_x,
            'INDEX_DELTA_Y': index_delta_y,
        }

    def release(self):
        self.hands.close()