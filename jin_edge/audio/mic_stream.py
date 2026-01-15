"""
Lightweight microphone capture module for Raspberry Pi.
Captures audio from default input device and yields raw PCM bytes.
Optimized for low CPU usage and minimal buffer copying.
"""

import asyncio
import sounddevice as sd
import numpy as np
import logging
from typing import Any, Generator, Optional, Callable

logger = logging.getLogger(__name__)


class MicStream:
    """
    Microphone audio capture stream.
    Captures 16-bit PCM, mono, 16kHz audio in small chunks.

    Usage:
        mic = MicStream()
        for chunk in mic.stream():
            # Process raw PCM bytes
            process(chunk)
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        dtype: str = "int16",
        chunk_duration_ms: int = 30,
        device: Optional[int] = None,
    ):
        """
        Initialize microphone stream.

        Args:
            sample_rate: Sample rate in Hz (default: 16000)
            channels: Number of audio channels (default: 1 for mono)
            dtype: Data type of PCM bytes (default: 'int16' for 16-bit)
            chunk_duration_ms: Chunk duration in milliseconds (default: 30ms)
            device: Input device index or None for default
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.device = device

        # Calculate chunk size in frames
        self.chunk_duration_ms = chunk_duration_ms
        self.chunk_frames = int(sample_rate * chunk_duration_ms / 1000)

        self._stream = None
        self._is_running = False

    def stream(self) -> Generator[bytes, None, None]:
        """
        Start capturing audio and yield raw PCM bytes continuously.

        Yields:
            bytes: Raw PCM audio data (16-bit signed integers)

        Example:
            mic = MicStream()
            for chunk in mic.stream():
                print(f"Captured {len(chunk)} bytes")
        """
        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                device=self.device,
                blocksize=self.chunk_frames,
            ) as stream:
                self._stream = stream
                self._is_running = True

                while self._is_running:
                    # Read audio chunk
                    frames, overflowed = stream.read(self.chunk_frames)

                    if overflowed:
                        # Log overflow if needed, but continue
                        pass

                    # Convert numpy array to raw bytes
                    pcm_bytes = frames.tobytes()
                    yield pcm_bytes

        except Exception as e:
            self._is_running = False
            raise RuntimeError(f"Microphone stream error: {e}")
        finally:
            self._stream = None
            self._is_running = False

    def stop(self):
        """
        Stop the microphone stream.
        Call this to break out of the stream() generator loop.
        """
        self._is_running = False


class AsyncMicStream:
    """
    Async microphone audio capture stream.
    Captures 16-bit PCM, mono, 16kHz audio in small chunks.

    Usage:
        mic = AsyncMicStream()
        async for chunk in mic.stream():
            # Process raw PCM bytes
            await process(chunk)
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        dtype: str = "int16",
        chunk_duration_ms: int = 30,
        device: Optional[int] = None,
    ):
        """
        Initialize async microphone stream.

        Args:
            sample_rate: Sample rate in Hz (default: 16000)
            channels: Number of audio channels (default: 1 for mono)
            dtype: Data type of PCM bytes (default: 'int16' for 16-bit)
            chunk_duration_ms: Chunk duration in milliseconds (default: 30ms)
            device: Input device index or None for default
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.device = device

        # Calculate chunk size in frames
        self.chunk_duration_ms = chunk_duration_ms
        self.chunk_frames = int(sample_rate * chunk_duration_ms / 1000)

        self._stream = None
        self._is_running = False

    async def stream(self):
        """
        Start capturing audio and yield raw PCM bytes continuously.

        Yields:
            bytes: Raw PCM audio data (16-bit signed integers)

        Example:
            mic = AsyncMicStream()
            async for chunk in mic.stream():
                print(f"Captured {len(chunk)} bytes")
        """
        import asyncio

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                device=self.device,
                blocksize=self.chunk_frames,
            ) as stream:
                self._stream = stream
                self._is_running = True

                while self._is_running:
                    # Read audio chunk
                    frames, overflowed = stream.read(self.chunk_frames)

                    if overflowed:
                        # Log overflow if needed, but continue
                        pass

                    # Convert numpy array to raw bytes
                    pcm_bytes = frames.tobytes()
                    yield pcm_bytes

                    # Yield control to event loop
                    await asyncio.sleep(0)

        except Exception as e:
            self._is_running = False
            raise RuntimeError(f"Microphone stream error: {e}")
        finally:
            self._stream = None
            self._is_running = False

    def stop(self):
        """
        Stop the microphone stream.
        Call this to break out of the stream() generator loop.
        """
        self._is_running = False


def list_input_devices():
    """
    List all available audio input devices.

    Returns:
        List of device info dictionaries with keys:
        - index: Device index
        - name: Device name
        - channels: Max input channels
        - sample_rate: Default sample rate
    """
    devices = sd.query_devices()
    input_devices = []

    for idx, device in enumerate(devices):
        device_dict: dict[str, Any] = dict(device)  # type: ignore
        if device_dict.get("max_input_channels", 0) > 0:
            input_devices.append(
                {
                    "index": idx,
                    "name": device_dict["name"],
                    "channels": device_dict["max_input_channels"],
                    "sample_rate": int(device_dict["default_samplerate"]),
                }
            )

    return input_devices


def get_default_input_device():
    """
    Get the default audio input device configuration.

    Returns:
        Device configuration dict with:
        - device: Device index or None for system default
        - name: Device name
        - channels: Max input channels
        - sample_rate: Default sample rate
    """
    try:
        default_device: dict[str, Any] = dict(sd.query_devices(kind="input"))  # type: ignore
        return {
            "device": None,  # None means use system default
            "name": default_device["name"],
            "channels": default_device["max_input_channels"],
            "sample_rate": int(default_device["default_samplerate"]),
        }
    except Exception:
        # Fallback if no input device found
        return None
