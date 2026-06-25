#!/bin/bash
# Create the USB MIDI gadget (f_midi) so the Pi appears as a USB-MIDI device
# to the host laptop. Must run as root (writes configfs). Idempotent.
set -e
GADGET=/sys/kernel/config/usb_gadget/midi_gadget

# Cleanup if a previous instance exists.
if [ -d "$GADGET" ]; then
    echo "" > "$GADGET/UDC" 2>/dev/null || true
    rm -rf "$GADGET"
fi

mkdir -p "$GADGET"
echo 0x1d6b > "$GADGET/idVendor"      # Linux Foundation
echo 0x0104 > "$GADGET/idProduct"     # Multifunction Composite Gadget
echo 0x0100 > "$GADGET/bcdDevice"
echo 0x0200 > "$GADGET/bcdUSB"

mkdir -p "$GADGET/strings/0x409"
echo "123456789"            > "$GADGET/strings/0x409/serialnumber"
echo "Raspberry Pi"         > "$GADGET/strings/0x409/manufacturer"
echo "Pi4 MIDI Controller"  > "$GADGET/strings/0x409/product"

mkdir -p "$GADGET/configs/c.1/strings/0x409"
echo "Config 1" > "$GADGET/configs/c.1/strings/0x409/configuration"
echo 250        > "$GADGET/configs/c.1/MaxPower"

# MIDI function -> creates the ALSA f_midi port.
mkdir -p "$GADGET/functions/midi.usb0"
ln -s "$GADGET/functions/midi.usb0" "$GADGET/configs/c.1/"

# Activate: bind to the first available USB Device Controller.
# (Original script pointed at a non-existent path; this reads the real UDC.)
ls /sys/class/udc > "$GADGET/UDC"

echo "MIDI Gadget Active (bound to $(cat "$GADGET/UDC"))."
