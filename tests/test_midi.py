import os
import time

def test_midi_alsa():
    print("--- ALSA MIDI Test ---")
    
    # Find the MIDI device
    midi_devices = []
    for device in os.listdir('/dev/snd/'):
        if 'midi' in device:
            midi_devices.append(f"/dev/snd/{device}")
    
    if not midi_devices:
        print("❌ No MIDI devices found in /dev/snd/")
        return
    
    print(f"Found MIDI devices: {midi_devices}")
    midi_device = midi_devices[0]
    
    print(f"\n✅ Using: {midi_device}")
    print("Sending MIDI Note: Middle C (C4)")
    
    try:
        # Open the MIDI device
        with open(midi_device, 'wb') as midi:
            # MIDI Note On message: 0x90 (Note On), 60 (Middle C), 100 (Velocity)
            note_on = bytes([0x90, 60, 100])
            midi.write(note_on)
            print("🎵 Note On sent!")
            
            time.sleep(0.5)
            
            # MIDI Note Off message: 0x80 (Note Off), 60 (Middle C), 0 (Velocity)
            note_off = bytes([0x80, 60, 0])
            midi.write(note_off)
            print("🔇 Note Off sent!")
            
        print("\n✅ MIDI Test Complete!")
        print("Check your laptop - did you receive the MIDI note?")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_midi_alsa()