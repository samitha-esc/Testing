import json
import os
import copy
import threading


DEFAULT_CONFIG = {
    "PLAY": [
        {"id": "transport", "label": "Play / Stop", "type": "trigger",
         "cc": 64, "channel": 1, "on_gesture": "OPEN_PALM",
         "off_gesture": "FIST", "on_value": 127, "off_value": 0},
    ],
    "EXPRESSION": [
        {"id": "filter", "label": "Filter Cutoff", "type": "absolute",
         "source": "PINCH", "cc": 74, "channel": 1},
        {"id": "expression", "label": "Expression", "type": "absolute",
         "source": "HAND_Y", "cc": 11, "channel": 1},
    ],
    "DJ": [
        {"id": "crossfader", "label": "Crossfader", "type": "relative",
         "source": "HAND_DELTA_X", "cc": 7, "channel": 1},
        {"id": "scratch", "label": "Scratch", "type": "relative",
         "source": "INDEX_DELTA_Y", "cc": 56, "channel": 1},
    ],
}

# Gesture sources the UI can offer when editing mappings.
ABSOLUTE_SOURCES = ["PINCH", "HAND_X", "HAND_Y", "TILT"]
RELATIVE_SOURCES = ["HAND_DELTA_X", "HAND_DELTA_Y", "INDEX_DELTA_X", "INDEX_DELTA_Y"]
TRIGGER_GESTURES = ["FIST", "OPEN_PALM"]


class MappingEngine:
    """
    Config-driven gesture -> MIDI mapper.

    Each mode owns a list of bindings. process_gestures() evaluates every
    binding for the current mode, sends MIDI on change (if a port exists),
    and returns the live value of each control so the UI can render bars.

    The config is hot-reloadable and thread-safe: the web server can call
    set_config()/get_config() while the tracking loop calls process_gestures().
    """

    def __init__(self, midi_mapper, mode_manager,
                 config_path="config/midi_mappings.json"):
        self.midi = midi_mapper          # may be None (track/visualize only)
        self.mode = mode_manager
        self.config_path = config_path

        self._lock = threading.Lock()
        self._relative_state = {}        # binding id -> current 0..127
        self._last_value = {}            # binding id -> last computed 0..127
        self._last_sent = {}             # binding id -> last value sent to MIDI

        self.config = self._load_or_default()

    # ------------------------------------------------------------------ #
    # Config management
    # ------------------------------------------------------------------ #
    def _load_or_default(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    cfg = json.load(f)
                # Ensure all three modes exist.
                for m in ("PLAY", "EXPRESSION", "DJ"):
                    cfg.setdefault(m, [])
                return cfg
            except Exception as e:
                print(f"⚠️  Could not read {self.config_path} ({e}); using defaults.")
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        self._write(cfg)
        return cfg

    def _write(self, cfg):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(cfg, f, indent=2)

    def get_config(self):
        with self._lock:
            return copy.deepcopy(self.config)

    def set_config(self, new_config):
        """Validate, persist, and apply a new mapping config (from the UI)."""
        cleaned = self._validate(new_config)
        with self._lock:
            self.config = cleaned
            self._relative_state.clear()
            self._last_value.clear()
            self._last_sent.clear()
        self._write(cleaned)
        return cleaned

    def _validate(self, cfg):
        out = {}
        for mode in ("PLAY", "EXPRESSION", "DJ"):
            out[mode] = []
            for b in cfg.get(mode, []):
                try:
                    binding = {
                        "id": str(b["id"]),
                        "label": str(b.get("label", b["id"])),
                        "type": b.get("type", "absolute"),
                        "cc": int(b["cc"]),
                        "channel": int(b.get("channel", 1)),
                    }
                    if binding["type"] in ("absolute", "relative"):
                        binding["source"] = str(b["source"])
                    elif binding["type"] == "trigger":
                        binding["on_gesture"] = str(b.get("on_gesture", "OPEN_PALM"))
                        binding["off_gesture"] = str(b.get("off_gesture", "FIST"))
                        binding["on_value"] = int(b.get("on_value", 127))
                        binding["off_value"] = int(b.get("off_value", 0))
                    binding["cc"] = max(0, min(127, binding["cc"]))
                    binding["channel"] = max(1, min(16, binding["channel"]))
                    out[mode].append(binding)
                except (KeyError, ValueError, TypeError):
                    continue  # skip malformed binding
        return out

    # ------------------------------------------------------------------ #
    # Per-frame evaluation
    # ------------------------------------------------------------------ #
    def process_gestures(self, gestures):
        """Evaluate current mode's bindings. Returns dict for the UI:
           {"mode": str, "controls": [ {id,label,cc,channel,value,active}, ... ]}"""
        mode = self.mode.current_mode
        with self._lock:
            bindings = list(self.config.get(mode, []))

        controls = []
        for b in bindings:
            controls.append(self._apply(b, gestures))
        return {"mode": mode, "controls": controls}

    def _apply(self, b, gestures):
        bid = b["id"]
        cc = b["cc"]
        ch = b["channel"] - 1
        btype = b["type"]
        active = False
        value = self._last_value.get(bid, 0)

        if btype == "absolute":
            src = b.get("source")
            if src in gestures:
                value = max(0, min(127, int(gestures[src] * 127)))
                active = True

        elif btype == "relative":
            src = b.get("source")
            cur = self._relative_state.get(bid, 64)
            if src in gestures:
                cur = max(0, min(127, cur + int(gestures[src] * 127 * 2)))
                active = True
            self._relative_state[bid] = cur
            value = cur

        elif btype == "trigger":
            if gestures.get(b.get("on_gesture")):
                value = b.get("on_value", 127)
                active = True
            elif gestures.get(b.get("off_gesture")):
                value = b.get("off_value", 0)
                active = True

        self._last_value[bid] = value

        # Send only when the value actually changed (avoid flooding MIDI).
        if self.midi is not None and self._last_sent.get(bid) != value:
            self.midi.send_cc(cc, value, channel=ch)
            self._last_sent[bid] = value

        return {"id": bid, "label": b["label"], "cc": cc,
                "channel": b["channel"], "value": value, "active": active,
                "type": btype}
