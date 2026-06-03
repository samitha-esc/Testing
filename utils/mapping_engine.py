class MappingEngine:
    def __init__(self, midi_mapper, mode_manager):
        self.midi = midi_mapper
        self.mode = mode_manager

    def process_gestures(self, gestures):
        mode = self.mode.current_mode

        if mode == "PLAY":
            self._handle_play_mode(gestures)
        elif mode == "EXPRESSION":
            self._handle_expression_mode(gestures)
        elif mode == "DJ":
            self._handle_dj_mode(gestures)

    def _handle_play_mode(self, gestures):
        if gestures.get('FIST'):
            self.midi.send_absolute(64, 0.0)  # Stop
        elif gestures.get('OPEN_PALM'):
            self.midi.send_absolute(64, 1.0)  # Play
            
        if gestures.get('OK_SIGN'):
            self.mode.handle_gesture_switch("EXPRESSION")

    def _handle_expression_mode(self, gestures):
        if 'PINCH' in gestures:
            self.midi.send_absolute(74, gestures['PINCH'])
            
        if 'HAND_Y' in gestures:
            self.midi.send_absolute(11, gestures['HAND_Y'])
            
        if gestures.get('OK_SIGN'):
            self.mode.handle_gesture_switch("DJ")

    def _handle_dj_mode(self, gestures):
        if 'HAND_DELTA_X' in gestures:
            self.midi.send_relative('fader', 7, gestures['HAND_DELTA_X'])
            
        if 'INDEX_DELTA_Y' in gestures:
            self.midi.send_relative('scratch', 56, gestures['INDEX_DELTA_Y'])

        if gestures.get('OK_SIGN'):
            self.mode.handle_gesture_switch("PLAY")