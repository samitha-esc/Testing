# Gesture MIDI Controller

A lightweight Python project to map hand gestures to MIDI messages for live control.

Structure

- README.md: Project documentation
- requirements.txt: Python dependencies
- setup_pi.sh: Installer script for Raspberry Pi
- main.py: Main controller loop (placeholder)

- engines/: Gesture-detection engines (base template + stubs)
- tests/: FPS and engine unit tests
- utils/: Camera and MIDI helper utilities

Getting started

1. On a Raspberry Pi, run:

```bash
bash setup_pi.sh
```

2. Run tests:

```bash
python -m pytest -q
```

This repository is a scaffold — engine implementations come later.
