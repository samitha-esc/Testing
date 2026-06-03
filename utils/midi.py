import mido
import time

class MidiManager:
    def __init__(self):
        self.port = None
        # Smoothing factor (0.0 to 1.0). Lower = smoother/slower, Higher = snappier.
        # 0.2 feels like a physical knob.
        self.smoothing = 0.2 
        
    def connect(self):
        try:
            # Automatically finds the Raspberry Pi USB MIDI gadget
            self.port = mido.open_output()
            print(f"✅ Connected to MIDI: {self.port.name}")
            return True
        except Exception as e:
            print(f"❌ MIDI Error: {e}")
            return False

    def smooth_value(self, current_val, target_val):
        """Interpolates between the current MIDI value and the new target to prevent jumps."""
        return int(current_val + (target_val - current_val) * self.smoothing)

    def send_cc(self, control, target_value, current_value):
        """Sends a Control Change message with smoothing."""
        # Calculate the smoothed value
        smoothed_val = self.smooth_value(current_value, target_value)
        
        # Round to valid MIDI range (0-127)
        smoothed_val = max(0, min(127, smoothed_val))
        
        # Only send if it actually changed
        if smoothed_val != current_value:
            msg = mido.Message('control_change', control=control, value=smoothed_val)
            self.port.send(msg)
            return smoothed_val # Return the new current value
            
        return current_value

    def send_note(self, note, velocity=100, duration=0.5):
        """Sends a Note On and Note Off."""
        if self.port:
            self.port.send(mido.Message('note_on', note=note, velocity=velocity))
            time.sleep(duration)
            self.port.send(mido.Message('note_off', note=note, velocity=velocity))

    def disconnect(self):
        if self.port:
            self.port.close()
            print("🔌 MIDI Disconnected.")