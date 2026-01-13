"""
Lightweight audio player for Raspberry Pi.
Plays raw PCM bytes with low latency, no file I/O.
"""

import numpy as np
import sounddevice as sd
import threading


class AudioPlayer:
    """
    Audio player for raw PCM bytes (16-bit, mono, 16kHz).

    Usage:
        player = AudioPlayer()
        player.start()
        player.play(pcm_bytes)
        player.stop()
    """

    def __init__(self, sample_rate=16000, channels=1, dtype="int16", device=None):
        """
        Initialize audio player.

        Args:
            sample_rate: Sample rate in Hz (default: 16000)
            channels: Number of audio channels (default: 1 for mono)
            dtype: Data type of PCM bytes (default: 'int16' for 16-bit)
            device: Device index or None for default (from audio.device module)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.device = device
        self._stream = None
        self._lock = threading.Lock()
        self._is_playing = False

    def start(self):
        """Initialize the audio output stream."""
        if self._stream is None:
            # Low latency settings for immediate playback
            self._stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                device=self.device,
                blocksize=1024,  # Small buffer for low latency
                latency="low",
            )
            self._stream.start()

    def play(self, pcm_bytes):
        """
        Play raw PCM bytes immediately.
        Interrupts any currently playing audio.

        Args:
            pcm_bytes: Raw PCM audio data as bytes (16-bit, mono, 16kHz)
        """
        if self._stream is None:
            raise RuntimeError("AudioPlayer not started. Call start() first.")

        with self._lock:
            # Stop any currently playing audio
            if self._is_playing:
                self._stream.stop()
                self._stream.start()

            # Convert bytes to numpy array
            audio_data = np.frombuffer(pcm_bytes, dtype=np.int16)

            # Write to stream (blocking, but fast)
            self._is_playing = True
            self._stream.write(audio_data)
            self._is_playing = False

    def stop(self):
        """Stop playback and close the audio stream."""
        with self._lock:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None
                self._is_playing = False

    def __enter__(self):
        """Context manager support."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support."""
        self.stop()
