"""
Fake audio generator utility for testing.

Generates raw PCM16 audio bytes without any WebSocket or Django dependencies.
"""

# cSpell:ignore tobytes
import numpy as np
from typing import Optional


def generate_tone(
    frequency: float = 440.0,
    duration: float = 1.0,
    sample_rate: int = 16000,
    amplitude: float = 0.5,
) -> bytes:
    """
    Generate a sine wave tone as raw PCM16 audio bytes.

    Args:
        frequency: Tone frequency in Hz (default: 440.0 - A4 note)
        duration: Duration in seconds (default: 1.0)
        sample_rate: Sample rate in Hz (default: 16000)
        amplitude: Amplitude multiplier 0.0-1.0 (default: 0.5)

    Returns:
        Raw PCM16 bytes (16-bit signed integer, mono, little-endian)

    Example:
        >>> audio_bytes = generate_tone(440, 1.0, 16000)
        >>> len(audio_bytes)
        32000  # 16000 samples * 2 bytes per sample
    """
    if not 0.0 < amplitude <= 1.0:
        raise ValueError("Amplitude must be between 0.0 and 1.0")

    if frequency <= 0:
        raise ValueError("Frequency must be positive")

    if duration <= 0:
        raise ValueError("Duration must be positive")

    if sample_rate <= 0:
        raise ValueError("Sample rate must be positive")

    # Calculate number of samples
    num_samples = int(duration * sample_rate)

    # Generate time array
    t = np.linspace(0, duration, num_samples, endpoint=False, dtype=np.float32)

    # Generate sine wave
    tone = np.sin(2 * np.pi * frequency * t, dtype=np.float32)

    # Apply amplitude and convert to 16-bit PCM
    # Scale to use the full range of int16 with given amplitude
    audio_data = (tone * amplitude * 32767).astype(np.int16)

    return audio_data.tobytes()


def generate_silence(duration: float = 1.0, sample_rate: int = 16000) -> bytes:
    """
    Generate silence as raw PCM16 audio bytes.

    Args:
        duration: Duration in seconds (default: 1.0)
        sample_rate: Sample rate in Hz (default: 16000)

    Returns:
        Raw PCM16 bytes of silence (all zeros)

    Example:
        >>> silence = generate_silence(0.5, 16000)
        >>> len(silence)
        16000  # 8000 samples * 2 bytes per sample
    """
    if duration <= 0:
        raise ValueError("Duration must be positive")

    if sample_rate <= 0:
        raise ValueError("Sample rate must be positive")

    num_samples = int(duration * sample_rate)
    audio_data = np.zeros(num_samples, dtype=np.int16)
    return audio_data.tobytes()


def generate_tone_sequence(
    frequencies: list[float],
    duration_per_tone: float = 1.0,
    gap_duration: float = 0.0,
    sample_rate: int = 16000,
    amplitude: float = 0.5,
) -> bytes:
    """
    Generate a sequence of tones with optional gaps between them.

    Args:
        frequencies: List of frequencies in Hz
        duration_per_tone: Duration of each tone in seconds (default: 1.0)
        gap_duration: Duration of silence between tones in seconds (default: 0.0)
        sample_rate: Sample rate in Hz (default: 16000)
        amplitude: Amplitude multiplier 0.0-1.0 (default: 0.5)

    Returns:
        Raw PCM16 bytes containing all tones concatenated

    Example:
        >>> # Generate C major chord notes in sequence
        >>> audio = generate_tone_sequence([261.63, 329.63, 392.00], 0.5, 0.1)
    """
    if not frequencies:
        raise ValueError("Frequencies list cannot be empty")

    audio_chunks = []

    for i, freq in enumerate(frequencies):
        # Generate tone
        tone_bytes = generate_tone(freq, duration_per_tone, sample_rate, amplitude)
        audio_chunks.append(tone_bytes)

        # Add gap between tones (except after the last one)
        if gap_duration > 0 and i < len(frequencies) - 1:
            gap_bytes = generate_silence(gap_duration, sample_rate)
            audio_chunks.append(gap_bytes)

    return b"".join(audio_chunks)


def calculate_audio_duration(audio_bytes: bytes, sample_rate: int = 16000) -> float:
    """
    Calculate the duration of PCM16 audio in seconds.

    Args:
        audio_bytes: Raw PCM16 audio bytes
        sample_rate: Sample rate in Hz (default: 16000)

    Returns:
        Duration in seconds

    Example:
        >>> audio = generate_tone(440, 2.5, 16000)
        >>> calculate_audio_duration(audio, 16000)
        2.5
    """
    bytes_per_sample = 2  # 16-bit = 2 bytes
    num_samples = len(audio_bytes) // bytes_per_sample
    return num_samples / sample_rate


# Predefined musical notes (A4=440Hz standard tuning)
NOTES = {
    "C4": 261.63,
    "D4": 293.66,
    "E4": 329.63,
    "F4": 349.23,
    "G4": 392.00,
    "A4": 440.00,
    "B4": 493.88,
    "C5": 523.25,
    "D5": 587.33,
    "E5": 659.25,
    "F5": 698.46,
    "G5": 783.99,
}
