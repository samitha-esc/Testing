"""MIDI helper stubs.

This provides a small, optional wrapper around `mido`/`python-rtmidi`.
Implementations will be added later.
"""

try:
    import mido
except Exception:
    mido = None


class MidiController:
    def __init__(self, port_name=None):
        self.port_name = port_name
        self.outport = None

    def open(self):
        if mido is None:
            raise RuntimeError("mido not available; install requirements first")
        self.outport = mido.open_output(self.port_name) if self.port_name else mido.open_output()

    def close(self):
        if self.outport:
            self.outport.close()
            self.outport = None

    def send_note_on(self, note=60, velocity=64, channel=0):
        if not self.outport:
            raise RuntimeError("MIDI port not open")
        msg = mido.Message('note_on', note=note, velocity=velocity, channel=channel)
        self.outport.send(msg)

    def send_note_off(self, note=60, velocity=0, channel=0):
        if not self.outport:
            raise RuntimeError("MIDI port not open")
        msg = mido.Message('note_off', note=note, velocity=velocity, channel=channel)
        self.outport.send(msg)
