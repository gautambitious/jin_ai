#!/usr/bin/env python3
"""
Test script for AudioPlayer.
Generates and plays a simple test tone.
"""

import numpy as np
from audio import AudioPlayer


def generate_test_tone(frequency=440, duration=1.0, sample_rate=16000):
    """
    Generate a sine wave test tone.

    Args:
        frequency: Frequency in Hz (default: 440Hz, A4 note)
        duration: Duration in seconds
        sample_rate: Sample rate in Hz

    Returns:
        bytes: Raw PCM audio data
    """
    # Generate time array
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

    # Generate sine wave
    amplitude = 0.3  # Keep volume moderate
    audio = amplitude * np.sin(2 * np.pi * frequency * t)

    # Convert to 16-bit PCM
    audio_int16 = (audio * 32767).astype(np.int16)

    return audio_int16.tobytes()


def main():
    """Run audio player test."""
    print("Testing AudioPlayer...")

    # Create player
    player = AudioPlayer()

    try:
        # Start the audio stream
        print("Starting audio stream...")
        player.start()

        # Generate and play test tone
        print("Playing 440Hz test tone for 1 second...")
        test_tone = generate_test_tone(frequency=440, duration=1.0)
        player.play(test_tone)

        print("Playing 880Hz test tone for 0.5 seconds...")
        test_tone_high = generate_test_tone(frequency=880, duration=0.5)
        player.play(test_tone_high)

        print("Test complete!")

    finally:
        # Clean up
        player.stop()
        print("Audio player stopped.")


if __name__ == "__main__":
    main()
