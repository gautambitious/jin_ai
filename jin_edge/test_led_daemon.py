#!/usr/bin/env python3
"""
Test script for LED daemon.

Run the daemon with: sudo python led/daemon.py
Then run this script without sudo: python test_led_daemon.py
"""

import socket
import time
import sys


class LEDDaemonClient:
    """Client for communicating with LED daemon."""
    
    SOCKET_PATH = "/tmp/jin_led.sock"
    
    def send_command(self, state):
        """Send state command to daemon."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.SOCKET_PATH)
            sock.sendall(state.encode())
            response = sock.recv(1024).decode()
            sock.close()
            return response
        except FileNotFoundError:
            print(f"ERROR: Socket not found at {self.SOCKET_PATH}")
            print("Is the LED daemon running? Start it with: sudo python led/daemon.py")
            return None
        except ConnectionRefusedError:
            print("ERROR: Connection refused")
            print("Is the LED daemon running? Start it with: sudo python led/daemon.py")
            return None
        except Exception as e:
            print(f"ERROR: {e}")
            return None
    
    def test_state(self, state, duration=3):
        """Test a specific LED state."""
        print(f"\nTesting state: {state}")
        response = self.send_command(state)
        if response:
            print(f"Response: {response}")
            if duration > 0:
                print(f"Waiting {duration} seconds...")
                time.sleep(duration)
            return True
        return False
    
    def test_all_states(self):
        """Test all LED states in sequence."""
        print("=" * 50)
        print("LED Daemon Test Suite")
        print("=" * 50)
        
        states = [
            ("off", 1),
            ("idle", 3),
            ("listening", 3),
            ("thinking", 3),
            ("speaking", 3),
            ("off", 1),
        ]
        
        success_count = 0
        for state, duration in states:
            if self.test_state(state, duration):
                success_count += 1
        
        print("\n" + "=" * 50)
        print(f"Test Results: {success_count}/{len(states)} states tested successfully")
        print("=" * 50)
    
    def test_responsiveness(self):
        """Test daemon responsiveness with rapid state changes."""
        print("\n" + "=" * 50)
        print("Responsiveness Test (Rapid State Changes)")
        print("=" * 50)
        
        states = ["listening", "thinking", "speaking", "idle"]
        
        print("\nSending rapid commands (0.2s intervals)...")
        start_time = time.time()
        
        for state in states:
            print(f"-> {state}", end=" ", flush=True)
            response = self.send_command(state)
            if response:
                print(f"[{response}]")
            time.sleep(0.2)  # Very short delay to test non-blocking
        
        elapsed = time.time() - start_time
        print(f"\nCompleted in {elapsed:.2f}s")
        print(f"Average response time: {elapsed/len(states):.3f}s per command")
        
        # Return to off
        self.send_command("off")
        print("\n" + "=" * 50)
    
    def interactive_mode(self):
        """Interactive mode for manual testing."""
        print("\n" + "=" * 50)
        print("Interactive LED Control")
        print("=" * 50)
        print("\nAvailable commands:")
        print("  idle      - Dim blue breathing")
        print("  listening - Spinning blue")
        print("  thinking  - Medium blue breathing")
        print("  speaking  - Bright blue breathing")
        print("  off       - Turn off LEDs")
        print("  quit      - Exit interactive mode")
        print("\nEnter command:")
        
        while True:
            try:
                cmd = input("> ").strip().lower()
                if cmd == "quit":
                    break
                elif cmd in ["idle", "listening", "thinking", "speaking", "off"]:
                    response = self.send_command(cmd)
                    if response:
                        print(f"Response: {response}")
                elif cmd:
                    print(f"Unknown command: {cmd}")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except EOFError:
                break


def main():
    """Main entry point."""
    client = LEDDaemonClient()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "interactive":
            client.interactive_mode()
        elif command == "responsive" or command == "responsiveness":
            client.test_responsiveness()
        elif command in ["idle", "listening", "thinking", "speaking", "off"]:
            client.test_state(command, duration=0)
        else:
            print(f"Usage: {sys.argv[0]} [interactive|responsive|idle|listening|thinking|speaking|off]")
            print(f"       {sys.argv[0]}  # runs all tests")
    else:
        # Run all tests by default
        client.test_all_states()


if __name__ == "__main__":
    main()
