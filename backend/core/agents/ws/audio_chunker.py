"""
Audio chunker utility for splitting PCM audio into time-based chunks.

No delays or WebSocket logic - pure data chunking.
"""

from typing import Iterator
from agents.constants import AudioFormat


def chunk_audio(
    audio_bytes: bytes,
    sample_rate: int = AudioFormat.DEFAULT_SAMPLE_RATE,
    chunk_duration_ms: int = 20,
    bytes_per_sample: int = 2,
) -> Iterator[bytes]:
    """
    Split raw PCM audio bytes into time-based chunks.

    Args:
        audio_bytes: Raw PCM audio bytes
        sample_rate: Sample rate in Hz (default: 24000)
        chunk_duration_ms: Chunk duration in milliseconds (default: 20ms)
        bytes_per_sample: Bytes per sample - 2 for PCM16 (default: 2)

    Yields:
        Chunks of audio bytes, each representing chunk_duration_ms of audio
        (last chunk may be smaller)

    Example:
        >>> audio = b'\\x00' * 48000  # 1 second at 24kHz
        >>> chunks = list(chunk_audio(audio, 24000, 20))
        >>> len(chunks)
        50  # 1000ms / 20ms = 50 chunks
        >>> len(chunks[0])
        960  # 24000 * 0.02 * 2 bytes = 960 bytes
    """
    if not audio_bytes:
        return

    if sample_rate <= 0:
        raise ValueError("Sample rate must be positive")

    if chunk_duration_ms <= 0:
        raise ValueError("Chunk duration must be positive")

    if bytes_per_sample <= 0:
        raise ValueError("Bytes per sample must be positive")

    # Calculate samples per chunk
    samples_per_chunk = int((sample_rate * chunk_duration_ms) / 1000)

    # Calculate bytes per chunk
    chunk_size = samples_per_chunk * bytes_per_sample

    # Yield chunks
    offset = 0
    while offset < len(audio_bytes):
        chunk = audio_bytes[offset : offset + chunk_size]
        yield chunk
        offset += chunk_size


def chunk_audio_fixed_size(
    audio_bytes: bytes,
    chunk_size: int = 640,
) -> Iterator[bytes]:
    """
    Split raw PCM audio bytes into fixed-size chunks.

    Args:
        audio_bytes: Raw PCM audio bytes
        chunk_size: Size of each chunk in bytes (default: 640 - 20ms at 16kHz)

    Yields:
        Chunks of audio bytes, each of chunk_size bytes
        (last chunk may be smaller)

    Example:
        >>> audio = b'\\x00' * 1000
        >>> chunks = list(chunk_audio_fixed_size(audio, 100))
        >>> len(chunks)
        10
        >>> len(chunks[0])
        100
    """
    if not audio_bytes:
        return

    if chunk_size <= 0:
        raise ValueError("Chunk size must be positive")

    offset = 0
    while offset < len(audio_bytes):
        chunk = audio_bytes[offset : offset + chunk_size]
        yield chunk
        offset += chunk_size


def calculate_chunk_size(
    sample_rate: int = AudioFormat.DEFAULT_SAMPLE_RATE,
    chunk_duration_ms: int = 20,
    bytes_per_sample: int = 2,
) -> int:
    """
    Calculate the chunk size in bytes for a given duration.

    Args:
        sample_rate: Sample rate in Hz (default: 24000)
        chunk_duration_ms: Chunk duration in milliseconds (default: 20ms)
        bytes_per_sample: Bytes per sample - 2 for PCM16 (default: 2)

    Returns:
        Chunk size in bytes

    Example:
        >>> calculate_chunk_size(16000, 20, 2)
        640
        >>> calculate_chunk_size(24000, 30, 2)
        1440
    """
    if sample_rate <= 0:
        raise ValueError("Sample rate must be positive")

    if chunk_duration_ms <= 0:
        raise ValueError("Chunk duration must be positive")

    if bytes_per_sample <= 0:
        raise ValueError("Bytes per sample must be positive")

    samples_per_chunk = int((sample_rate * chunk_duration_ms) / 1000)
    return samples_per_chunk * bytes_per_sample


def calculate_chunk_count(
    audio_bytes: bytes,
    sample_rate: int = AudioFormat.DEFAULT_SAMPLE_RATE,
    chunk_duration_ms: int = 20,
    bytes_per_sample: int = 2,
) -> int:
    """
    Calculate the number of chunks for given audio bytes.

    Args:
        audio_bytes: Raw PCM audio bytes
        sample_rate: Sample rate in Hz (default: 24000)
        chunk_duration_ms: Chunk duration in milliseconds (default: 20ms)
        bytes_per_sample: Bytes per sample - 2 for PCM16 (default: 2)

    Returns:
        Total number of chunks (including partial last chunk)

    Example:
        >>> audio = b'\\x00' * 32000  # 1 second at 16kHz
        >>> calculate_chunk_count(audio, 16000, 20)
        50
    """
    if not audio_bytes:
        return 0

    chunk_size = calculate_chunk_size(sample_rate, chunk_duration_ms, bytes_per_sample)

    # Calculate total chunks (ceiling division)
    return (len(audio_bytes) + chunk_size - 1) // chunk_size


# Common chunk sizes for different configurations
CHUNK_CONFIGS = {
    "20ms_16k": calculate_chunk_size(16000, 20, 2),  # 640 bytes
    "30ms_16k": calculate_chunk_size(16000, 30, 2),  # 960 bytes
    "40ms_16k": calculate_chunk_size(16000, 40, 2),  # 1280 bytes
    "20ms_24k": calculate_chunk_size(24000, 20, 2),  # 960 bytes
    "20ms_48k": calculate_chunk_size(48000, 20, 2),  # 1920 bytes
}
