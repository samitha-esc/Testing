import mido


class MidiMapper:
    def __init__(self):
        self.port = None
        self.relative_values = {
            'fader': 64,
            'scratch': 64,
            'crossfader': 64
        }

    def connect(self, port_name=None):
        available = mido.get_output_names()
        print(f"  Available MIDI ports: {available}")

        if port_name:
            if port_name not in available:
                print(f"❌ Requested port '{port_name}' not found.")
                return False
            target = port_name
        else:
            # Prefer any port that isn't the kernel loopback.
            real = [p for p in available
                    if 'through' not in p.lower() and 'loopback' not in p.lower()]
            if real:
                target = real[0]
            elif available:
                print("⚠️  Only 'Midi Through' found — USB-C not connected to host yet.")
                print("   Connect the cable and run with --midi-port to pick the right port.")
                target = available[0]
            else:
                print("❌ No MIDI ports available at all.")
                return False

        try:
            self.port = mido.open_output(target)
            print(f"✅ MIDI connected: {self.port.name}")
            return True
        except Exception as e:
            print(f"❌ MIDI Error opening '{target}': {e}")
            return False

    def send_absolute(self, cc, normalized_value):
        if not self.port:
            return
        midi_val = max(0, min(127, int(normalized_value * 127)))
        self.port.send(mido.Message('control_change', control=cc, value=midi_val))

    def send_relative(self, control_name, cc, delta_value):
        if not self.port:
            return
        step = int(delta_value * 127 * 2)
        current = self.relative_values.get(control_name, 64)
        new_val = max(0, min(127, current + step))
        self.relative_values[control_name] = new_val
        if new_val != current:
            self.port.send(mido.Message('control_change', control=cc, value=new_val))

    def disconnect(self):
        if self.port:
            self.port.close()
            self.port = None
