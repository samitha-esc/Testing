# Hardware Controller (C++)

Drives the wired peripherals of the Gesture MIDI Controller on a Raspberry Pi 4B:
12 keys → MIDI notes, 2 mode buttons + 2 PWM LEDs, and a 16×2 I²C LCD.

## Dependencies

```bash
sudo apt install -y pigpio libpigpio-dev libasound2-dev
```

> pigpio gives direct GPIO + **hardware PWM** + I²C from one API. It works on
> the Pi 4B but **not** the Pi 5.

## Build & run

```bash
make            # builds ./keyboard_controller
sudo ./keyboard_controller     # pigpio needs root
# or:  make run
```

## Wiring

All keys and buttons are **active-low**: wire each one between its GPIO pin and
**GND**. The firmware enables internal pull-ups, so no external resistors are
needed for the inputs.

| Peripheral | GPIO (BCM) | Header pin |
|-----------|-----------|-----------|
| Key 1–12  | 4, 22, 23, 24, 25, 8, 5, 6, 16, 26, 20, 21 | 7,15,16,18,22,24,29,31,36,37,38,40 |
| Button 1  | 17 | 11 |
| Button 2  | 27 | 13 |
| LED 1 (PWM0) | 18 | 12 |
| LED 2 (PWM1) | 13 | 33 |
| LCD SDA   | 2  | 3 |
| LCD SCL   | 3  | 5 |
| LCD VCC   | 5V/3V3 | 2/4 or 1 |
| LCD GND   | GND | 6 (etc.) |

LEDs: anode → GPIO (through a current-limiting resistor, ~220–330 Ω), cathode → GND.

### Enable I²C

```bash
sudo raspi-config        # Interface Options → I2C → Enable
sudo i2cdetect -y 1      # confirm the LCD shows up (usually 0x27 or 0x3F)
```

If the LCD address isn't `0x27`, change `LCD_ADDR` near the top of
`keyboard_controller.cpp`.

## What it does

- **Keys** send MIDI note-on/off (one chromatic octave from middle C / note 60)
  on an ALSA port named **PiKeyboard**, auto-connected to the `f_midi` USB
  gadget. If the gadget isn't up yet, connect later with
  `aconnect PiKeyboard f_midi`.
- **Buttons** each toggle a mode; the matching **LED** lights when active.
- **LCD** shows the current gesture effect + intensity.

## Integration with the Python gesture system (file bridge)

The C++ and Python sides stay decoupled through two small files in `/tmp`:

| File | Direction | Format |
|------|-----------|--------|
| `/tmp/pi_to_hw_lcd` | Python → C++ | up to 2 lines; line 1 = effect name, line 2 = intensity. Shown on the LCD. |
| `/tmp/hw_buttons`   | C++ → Python | `b1=<0\|1> b2=<0\|1>` — written whenever a button toggles. |

Example: the Python controller can write the active control to the LCD each frame:

```python
with open("/tmp/pi_to_hw_lcd", "w") as f:
    f.write("Filter Cutoff\nIntensity: 87")
```

If `/tmp/pi_to_hw_lcd` is absent, the LCD falls back to showing the local
button/mode state.

## Run both together

Run this controller and the gesture app side by side (they share the same MIDI
gadget — keys and gestures both flow to the host):

```bash
sudo ./keyboard_controller &
cd ~/Testing && libcamerify ~/Testing/venv311/bin/python main.py --web
```
