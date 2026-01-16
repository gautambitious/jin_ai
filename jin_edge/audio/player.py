"""
Lightweight audio player for Raspberry Pi.
Plays raw PCM bytes with low latency, no file I/O.
"""

import asyncio
import numpy as np
import sounddevice as sd
from .buffer import AudioBuffer


class AudioPlayer:
    """
    Audio player for raw PCM bytes (16-bit, mono, 16kHz).
    Uses AudioBuffer for streaming playback.

    Usage:
        player = AudioPlayer()
        await player.start()
        await player.play(pcm_bytes)
        await player.stop()
    """

    def __init__(
        self,
        sample_rate=16000,
        channels=1,
        dtype="int16",
        device=None,
        buffer_size=1024 * 1024,
        chunk_size=2048,
    ):
        """
        Initialize audio player.

        Args:
            sample_rate: Sample rate in Hz (default: 16000)
            channels: Number of audio channels (default: 1 for mono)
            dtype: Data type of PCM bytes (default: 'int16' for 16-bit)
            device: Device index or None for default (from audio.device module)
            buffer_size: AudioBuffer max size in bytes (default: 1MB)
            chunk_size: Playback chunk size in bytes (default: 2048)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.device = device
        self.chunk_size = chunk_size

        self._buffer = AudioBuffer(max_size=buffer_size)
        self._stream = None
        self._is_playing = False
        self._playback_task = None
        self._stop_event = asyncio.Event()

    async def start(self):
        """Initialize the audio output stream and playback loop."""
        if self._stream is None:
            # Balanced settings for smooth playback with acceptable latency
            self._stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                device=self.device,
                blocksize=2048,  # Larger buffer for smoother playback
                latency="high",  # Prevents clicks and pops on device initialization
            )
            self._stream.start()

            # Start playback loop
            self._stop_event.clear()
            self._playback_task = asyncio.create_task(self._playback_loop())

    async def play(self, pcm_bytes):
        """
        Play raw PCM bytes via buffer.
        Clears buffer and starts new stream.

        Args:
            pcm_bytes: Raw PCM audio data as bytes (16-bit, mono, 16kHz)
        """
        if self._stream is None:
            raise RuntimeError("AudioPlayer not started. Call start() first.")

        # Clear buffer and start fresh
        await self._buffer.clear()

        # Add new audio to buffer
        await self._buffer.push(pcm_bytes)
        self._is_playing = True

    async def feed(self, pcm_bytes):
        """
        Feed additional audio data to buffer without clearing.

        Args:
            pcm_bytes: Raw PCM audio data as bytes

        Returns:
            True if data was added, False if buffer full
        """
        return await self._buffer.push(pcm_bytes)

    async def _playback_loop(self):
        """
        Internal playback loop that pulls from buffer.
        Keeps stream active with silence to prevent clicks.
        """
        import logging

        logger = logging.getLogger(__name__)
        # Pre-generate silence buffer for when no audio is playing
        silence_chunk = np.zeros(self.chunk_size // 2, dtype=np.int16)  # chunk_size/2 samples

        while not self._stop_event.is_set():
            if not self._is_playing:
                # Stream silence to keep audio device active and prevent clicks
                await asyncio.get_event_loop().run_in_executor(
                    None, self._stream.write, silence_chunk
                )
                await asyncio.sleep(0.05)  # 50ms silence chunks
                continue

            # Pull chunk from buffer
            chunk = await self._buffer.pop(self.chunk_size)

            if chunk:
                # Convert bytes to numpy array and play
                audio_data = np.frombuffer(chunk, dtype=np.int16)
                logger.debug(f"Playing {len(chunk)} bytes ({len(audio_data)} samples)")
                await asyncio.get_event_loop().run_in_executor(
                    None, self._stream.write, audio_data
                )
            else:
                # Buffer empty during playback - stream silence to prevent underrun clicks
                logger.debug("Player buffer empty, streaming silence...")
                await asyncio.get_event_loop().run_in_executor(
                    None, self._stream.write, silence_chunk
                )
                await asyncio.sleep(0.005)

    async def stop(self):
        """Stop playback immediately and close the audio stream."""
        # Signal playback loop to stop
        self._stop_event.set()
        self._is_playing = False

        # Wait for playback task to finish
        if self._playback_task:
            await self._playback_task
            self._playback_task = None

        # Close stream
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # Clear buffer
        await self._buffer.clear()

    async def is_playing(self):
        """Check if audio is currently playing."""
        return self._is_playing

    async def buffer_size(self):
        """Get current buffer size in bytes."""
        return await self._buffer.size()

    async def __aenter__(self):
        """Async context manager support."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager support."""
        await self.stop()
