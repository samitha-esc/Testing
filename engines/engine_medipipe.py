import cv2
import mediapipe as mp
from engines.base_engine import BaseEngine

class MediapipeEngine(BaseEngine):
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False, max_num_hands=1,
            min_detection_confidence=0.5, min_tracking_confidence=0.5
        )
        
    def process(self, frame):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # 8 is the Index Finger Tip
                index_tip = hand_landmarks.landmark[8]
                h, w, _ = frame.shape
                
                return {
                    'x_midi': int(index_tip.x * 127), 
                    'y_midi': int(index_tip.y * 127)
                }
        return None

    def release(self):
        self.hands.close()