#!/usr/bin/env python3
"""
Test script for audio device selection.
"""

from audio import (
    list_output_devices,
    get_default_device,
    select_device,
    print_devices,
    AudioPlayer,
)
import numpy as np


def generate_beep(duration=0.3, sample_rate=16000):
    """Generate a short beep tone."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    audio = 0.3 * np.sin(2 * np.pi * 600 * t)
    return (audio * 32767).astype(np.int16).tobytes()


def main():
    """Test device selection."""
    print("=== Audio Device Test ===\n")

    # Print all available devices
    print_devices()
    print()

    # Get default device config
    default = get_default_device()
    print(f"Using default device: {default['name']}")
    print(f"  Sample rate: {default['sample_rate']} Hz")
    print(f"  Channels: {default['channels']}")
    print()

    # Create player with default device
    player = AudioPlayer(device=default["device"])

    try:
        player.start()
        print("Playing test beep on default device...")
        player.play(generate_beep())
        print("Test complete!")

    finally:
        player.stop()

    print("\nTo use a specific device:")
    print("  config = select_device(index=1)")
    print("  player = AudioPlayer(device=config['device'])")


if __name__ == "__main__":
    main()
