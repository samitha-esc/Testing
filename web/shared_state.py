import threading


class SharedState:
    """
    Thread-safe bridge between the tracking loop (producer) and the web
    server threads (consumers).

    - Frame: latest annotated JPEG bytes for the MJPEG stream. A Condition
      lets stream handlers block until a new frame arrives (no busy-wait).
    - Status: latest snapshot dict (mode, fps, controls, oob, ...) polled
      by the browser.
    - Commands: a queue the UI pushes to (switch mode, recalibrate, quit);
      the tracking loop drains it each iteration so camera/engine work
      stays on the main thread.
    """

    def __init__(self):
        self._frame = None
        self._frame_cond = threading.Condition()
        self._frame_seq = 0

        self._status = {}
        self._status_lock = threading.Lock()

        self._commands = []
        self._cmd_lock = threading.Lock()

    # --- frame (MJPEG) ------------------------------------------------- #
    def set_frame(self, jpeg_bytes):
        with self._frame_cond:
            self._frame = jpeg_bytes
            self._frame_seq += 1
            self._frame_cond.notify_all()

    def get_frame(self):
        with self._frame_cond:
            return self._frame

    def wait_frame(self, last_seq, timeout=1.0):
        """Block until a frame newer than last_seq is available.
        Returns (jpeg_bytes, seq) or (None, last_seq) on timeout."""
        with self._frame_cond:
            if self._frame_seq == last_seq:
                self._frame_cond.wait(timeout)
            if self._frame_seq != last_seq:
                return self._frame, self._frame_seq
            return None, last_seq

    # --- status (polled) ----------------------------------------------- #
    def set_status(self, status):
        with self._status_lock:
            self._status = status

    def get_status(self):
        with self._status_lock:
            return dict(self._status)

    # --- commands (UI -> loop) ----------------------------------------- #
    def push_command(self, cmd_type, payload=None):
        with self._cmd_lock:
            self._commands.append((cmd_type, payload))

    def drain_commands(self):
        with self._cmd_lock:
            cmds = self._commands
            self._commands = []
            return cmds
