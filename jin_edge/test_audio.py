#!/usr/bin/env python3
"""
Test script for AudioPlayer with AudioBuffer.
Tests rapid play() calls to verify old audio stops immediately.
"""

import asyncio
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


async def test_rapid_play_switch():
    """
    Test rapid play() calls.
    Audio 1 (low 220Hz) should stop immediately when Audio 2 (high 880Hz) starts.
    """
    print("\n=== Test: Rapid play() Switch ===")
    print("You should hear:")
    print("  1. Low tone (220Hz) starts")
    print("  2. IMMEDIATELY switches to high tone (880Hz)")
    print("  3. No overlap or continuation of low tone\n")

    # Create two very different tones for clear audible distinction
    # Audio 1: Low tone (220Hz, 3 seconds) - should be cut off
    low_tone = generate_test_tone(frequency=220, duration=3.0)

    # Audio 2: High tone (880Hz, 2 seconds) - should play completely
    high_tone = generate_test_tone(frequency=880, duration=2.0)

    async with AudioPlayer() as player:
        # Start playing low tone
        print("▶ Playing LOW tone (220Hz, 3s)...")
        await player.play(low_tone)

        # Wait just 0.5 seconds, then rapidly switch
        await asyncio.sleep(0.5)

        # Rapidly call play() again - should STOP low tone and START high tone
        print("▶ SWITCHING to HIGH tone (880Hz, 2s)...")
        await player.play(high_tone)

        # Wait for high tone to finish
        await asyncio.sleep(2.2)

        print("✓ Test complete!")


async def test_immediate_stop():
    """
    Test that stop() immediately halts playback.
    """
    print("\n=== Test: Immediate Stop ===")
    print("You should hear:")
    print("  1. Tone starts (440Hz)")
    print("  2. STOPS abruptly after 0.8 seconds")
    print("  3. No fade or continuation\n")

    # Generate a 3-second tone that will be stopped early
    tone = generate_test_tone(frequency=440, duration=3.0)

    async with AudioPlayer() as player:
        print("▶ Playing tone (440Hz, 3s)...")
        await player.play(tone)

        # Let it play for only 0.8 seconds
        await asyncio.sleep(0.8)

        # Stop immediately
        print("■ STOPPING playback...")
        await player.stop()

        print("✓ Test complete!")


async def test_multiple_rapid_switches():
    """
    Test multiple rapid play() calls in quick succession.
    """
    print("\n=== Test: Multiple Rapid Switches ===")
    print("You should hear:")
    print("  1. Low tone (200Hz)")
    print("  2. Quickly switches to mid tone (440Hz)")
    print("  3. Quickly switches to high tone (880Hz)")
    print("  4. Each switch should be immediate and clean\n")

    # Create three distinct tones
    tone_1 = generate_test_tone(frequency=200, duration=2.0)  # Low
    tone_2 = generate_test_tone(frequency=440, duration=2.0)  # Mid
    tone_3 = generate_test_tone(frequency=880, duration=2.0)  # High

    async with AudioPlayer() as player:
        print("▶ Playing LOW tone (200Hz)...")
        await player.play(tone_1)
        await asyncio.sleep(0.4)

        print("▶ Switching to MID tone (440Hz)...")
        await player.play(tone_2)
        await asyncio.sleep(0.4)

        print("▶ Switching to HIGH tone (880Hz)...")
        await player.play(tone_3)
        await asyncio.sleep(2.2)

        print("✓ Test complete!")


async def main():
    """Run all audio player tests."""
    print("=" * 50)
    print("AudioPlayer Buffer Test Suite")
    print("=" * 50)

    try:
        # Test 1: Rapid switch
        await test_rapid_play_switch()
        await asyncio.sleep(1)

        # Test 2: Immediate stop
        await test_immediate_stop()
        await asyncio.sleep(1)

        # Test 3: Multiple switches
        await test_multiple_rapid_switches()

        print("\n" + "=" * 50)
        print("All tests complete!")
        print("=" * 50)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
