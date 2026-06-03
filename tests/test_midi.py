import mido
import time

def test_midi():
    print("--- MIDI Port Test ---")
    
    # List all available MIDI ports
    out_ports = mido.get_output_names()
    print("Available MIDI Output Ports:")
    for i, port in enumerate(out_ports):
        print(f"  {i}: {port}")
        
    # Try to find the Pi's gadget port
    pi_port = None
    for port in out_ports:
        if 'MIDI' in port or 'USB' in port or 'g1' in port or 'Linux' in port:
            pi_port = port
            break
            
    if not pi_port:
        print("\n⚠️  Could not automatically find the Pi USB MIDI port.")
        print("Please look at the list above and type the exact name of the Pi port:")
        pi_port = input("> ").strip()
        
    if not pi_port:
        print("No port selected. Exiting.")
        return

    print(f"\n✅ Connecting to: {pi_port}")
    
    try:
        with mido.open_output(pi_port) as outport:
            print("Sending MIDI Note: Middle C (C4) - Velocity 100")
            
            # Send Note On
            msg_on = mido.Message('note_on', note=60, velocity=100)
            outport.send(msg_on)
            print("🎵 Note On sent!")
            
            time.sleep(0.5) # Hold note for half a second
            
            # Send Note Off
            msg_off = mido.Message('note_off', note=60, velocity=100)
            outport.send(msg_off)
            print("🔇 Note Off sent!")
            
            print("\n✅ MIDI Test Complete!")
            
    except Exception as e:
        print(f"❌ Error opening port: {e}")

if __name__ == "__main__":
    test_midi()