"""
Lightweight microphone capture module for Raspberry Pi.
Captures audio from default input device and yields raw PCM bytes.
Optimized for low CPU usage and minimal buffer copying.
"""

import asyncio
import sounddevice as sd
import numpy as np
import logging
from typing import Any, Generator, Optional, Callable, Tuple

try:
    from scipy import signal

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

logger = logging.getLogger(__name__)


def check_sample_rate_support(
    device: Optional[int] = None, target_rate: int = 16000
) -> Tuple[bool, int]:
    """
    Check if device supports target sample rate, return native rate if not.

    Args:
        device: Device index or None for default
        target_rate: Desired sample rate (default: 16000)

    Returns:
        Tuple of (is_supported, native_rate_to_use)
        - If supported: (True, target_rate)
        - If not supported: (False, best_alternative_rate)
    """
    try:
        # Try to check if the device supports the target rate
        sd.check_input_settings(device=device, samplerate=target_rate)
        return True, target_rate
    except Exception as e:
        # Device doesn't support target rate, find what it does support
        logger.warning(f"Device doesn't support {target_rate}Hz: {e}")

        # Try common sample rates
        common_rates = [44100, 48000, 22050, 32000, 8000]
        for rate in common_rates:
            try:
                sd.check_input_settings(device=device, samplerate=rate)
                logger.info(f"Using {rate}Hz with resampling to {target_rate}Hz")
                return False, rate
            except:
                continue

        # Fallback to device default
        try:
            device_info: dict = dict(sd.query_devices(device, kind="input"))  # type: ignore
            default_rate = int(device_info["default_samplerate"])
            logger.info(
                f"Using device default {default_rate}Hz with resampling to {target_rate}Hz"
            )
            return False, default_rate
        except:
            # Last resort - just try 44100
            logger.warning(f"Falling back to 44100Hz")
            return False, 44100


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
        self.target_rate = sample_rate  # What we want to output
        self.channels = channels
        self.dtype = dtype
        self.device = device
        self.chunk_duration_ms = chunk_duration_ms

        # Check if device supports target rate
        self.rate_supported, self.capture_rate = check_sample_rate_support(
            device, sample_rate
        )
        self.needs_resampling = not self.rate_supported

        if self.needs_resampling:
            if not HAS_SCIPY:
                raise RuntimeError(
                    f"Device doesn't support {sample_rate}Hz and scipy is not installed. "
                    f"Install scipy for automatic resampling: pip install scipy"
                )
            # Calculate resampling ratio
            from math import gcd

            g = gcd(self.capture_rate, self.target_rate)
            self.resample_up = self.target_rate // g
            self.resample_down = self.capture_rate // g
            logger.info(
                f"Resampling enabled: {self.capture_rate}Hz → {self.target_rate}Hz (ratio {self.resample_up}/{self.resample_down})"
            )

            # Buffer for resampling (to handle partial frames)
            self.resample_buffer = np.array([], dtype=np.int16)

        # Use capture rate for device, target rate for output chunks
        self.sample_rate = self.capture_rate
        self.chunk_frames = int(self.capture_rate * chunk_duration_ms / 1000)
        self.target_chunk_frames = int(self.target_rate * chunk_duration_ms / 1000)

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

                    # Apply resampling if needed
                    if self.needs_resampling:
                        frames = self._resample_chunk(frames)
                        if frames is None:
                            continue  # Not enough data yet

                    # Convert numpy array to raw bytes
                    pcm_bytes = frames.tobytes()
                    yield pcm_bytes

        except Exception as e:
            self._is_running = False
            raise RuntimeError(f"Microphone stream error: {e}")
        finally:
            self._stream = None
            self._is_running = False

    def _resample_chunk(self, frames: np.ndarray) -> Optional[np.ndarray]:
        """
        Resample audio chunk from capture_rate to target_rate.

        Args:
            frames: Input frames at capture_rate

        Returns:
            Resampled frames at target_rate, or None if not enough data
        """
        # Flatten if stereo (though we expect mono)
        if len(frames.shape) > 1:
            frames = frames.flatten()

        # Add to buffer
        self.resample_buffer = np.concatenate([self.resample_buffer, frames])

        # Calculate how many input samples we need for one output chunk
        input_samples_needed = int(
            self.target_chunk_frames * self.resample_down / self.resample_up
        )

        if len(self.resample_buffer) < input_samples_needed:
            return None  # Not enough data yet

        # Take exactly what we need from buffer
        input_chunk = self.resample_buffer[:input_samples_needed]
        self.resample_buffer = self.resample_buffer[input_samples_needed:]

        # Resample using polyphase filtering (efficient)
        resampled = signal.resample_poly(
            input_chunk, self.resample_up, self.resample_down
        )

        # Convert back to int16
        resampled_int16 = resampled.astype(np.int16)

        return resampled_int16.reshape(-1, 1)  # Return as column vector for consistency

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
