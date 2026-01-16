"""Simple test client for LED daemon."""

import sys
import time
from led.client import LEDClient

def main():
    """Test LED daemon communication."""
    client = LEDClient()
    
    if len(sys.argv) > 1:
        # Set specific state
        state = sys.argv[1].lower()
        print(f"Setting LED state to: {state}")
        success = client.set_state(state)
        if success:
            print("Success!")
        else:
            print("Failed!")
            sys.exit(1)
    else:
        # Test all states
        states = ["idle", "listening", "thinking", "speaking", "off"]
        
        print("Testing all LED states...")
        print("Make sure the LED daemon is running: sudo systemctl status jin-led")
        print()
        
        for state in states:
            print(f"State: {state}")
            success = client.set_state(state)
            if not success:
                print(f"  ERROR: Failed to set state {state}")
                sys.exit(1)
            print(f"  OK")
            time.sleep(3)
        
        print("\nAll tests passed!")

if __name__ == "__main__":
    main()
