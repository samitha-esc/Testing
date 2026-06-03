import mido

class MidiMapper:
    def __init__(self):
        self.port = None
        self.relative_values = {
            'fader': 64,
            'scratch': 64,
            'crossfader': 64
        }

    def connect(self):
        try:
            self.port = mido.open_output()
            print(f"✅ Connected to MIDI: {self.port.name}")
            return True
        except Exception as e:
            print(f"❌ MIDI Error: {e}")
            return False

    def send_absolute(self, cc, normalized_value):
        midi_val = int(normalized_value * 127)
        midi_val = max(0, min(127, midi_val))
        msg = mido.Message('control_change', control=cc, value=midi_val)
        self.port.send(msg)

    def send_relative(self, control_name, cc, delta_value):
        step = int(delta_value * 127 * 2)
        current = self.relative_values.get(control_name, 64)
        new_val = current + step
        new_val = max(0, min(127, new_val))
        self.relative_values[control_name] = new_val
        
        if new_val != current:
            msg = mido.Message('control_change', control=cc, value=new_val)
            self.port.send(msg)

    def disconnect(self):
        if self.port:
            self.port.close()