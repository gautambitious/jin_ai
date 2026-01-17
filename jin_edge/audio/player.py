"""
Lightweight audio player for Raspberry Pi.
Plays raw PCM bytes with low latency, no file I/O.

Supports persistent stream playback with fade-in/fade-out to eliminate clicks.
"""

import asyncio
import numpy as np
import sounddevice as sd
from enum import Enum
from collections import deque
from typing import Optional
from .buffer import AudioBuffer


class PlaybackState(Enum):
    """Playback state machine."""
    IDLE = "idle"
    BUFFERING = "buffering"
    PLAYING = "playing"


def apply_fade_in(pcm_data: np.ndarray, fade_samples: int) -> np.ndarray:
    """
    Apply linear fade-in to PCM data.
    
    Args:
        pcm_data: Audio data as numpy array
        fade_samples: Number of samples to fade (typically 80-128 for 5-8ms at 16kHz)
    
    Returns:
        Faded audio data
    """
    if len(pcm_data) == 0 or fade_samples == 0:
        return pcm_data
    
    fade_len = min(fade_samples, len(pcm_data))
    fade_curve = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
    pcm_data[:fade_len] = (pcm_data[:fade_len].astype(np.float32) * fade_curve).astype(np.int16)
    return pcm_data


def apply_fade_out(pcm_data: np.ndarray, fade_samples: int) -> np.ndarray:
    """
    Apply linear fade-out to PCM data.
    
    Args:
        pcm_data: Audio data as numpy array
        fade_samples: Number of samples to fade (typically 80-128 for 5-8ms at 16kHz)
    
    Returns:
        Faded audio data
    """
    if len(pcm_data) == 0 or fade_samples == 0:
        return pcm_data
    
    fade_len = min(fade_samples, len(pcm_data))
    fade_curve = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
    pcm_data[-fade_len:] = (pcm_data[-fade_len:].astype(np.float32) * fade_curve).astype(np.int16)
    return pcm_data


class AudioPlayer:
    """
    Audio player for raw PCM bytes (16-bit, mono, 16kHz).
    
    Features:
    - Persistent output stream per playback session
    - One-time buffering with fade-in at start
    - Continuous playback without reopening device
    - Fade-out on end or interrupt
    - Small jitter buffer for network resilience

    Usage:
        player = AudioPlayer()
        await player.start()
        
        # Start a playback session
        await player.begin_session()
        await player.feed(pcm_bytes)  # Feed chunks as they arrive
        await player.feed(more_pcm_bytes)
        await player.end_session()  # Fade out and close
        
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
        buffering_chunks=2,  # Number of chunks to buffer before starting playback
        fade_samples=100,  # 6.25ms at 16kHz
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
            buffering_chunks: Number of chunks to buffer before starting playback (default: 2)
            fade_samples: Number of samples for fade-in/fade-out (default: 100 = ~6ms)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.device = device
        self.chunk_size = chunk_size
        self.buffering_chunks = buffering_chunks
        self.fade_samples = fade_samples

        self._buffer = AudioBuffer(max_size=buffer_size)
        self._output_stream = None
        self._playback_task = None
        self._stop_event = asyncio.Event()
        
        # Session state
        self._state = PlaybackState.IDLE
        self._session_active = False
        self._first_chunk = True

    async def start(self):
        """Initialize the audio playback system (does NOT open output stream)."""
        if self._playback_task is not None:
            return
            
        # Start background playback loop
        self._stop_event.clear()
        self._playback_task = asyncio.create_task(self._playback_loop())

    async def begin_session(self):
        """
        Begin a new playback session.
        Must be called before feeding audio chunks.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if self._session_active:
            logger.warning("Session already active, ending previous session")
            await self.end_session()
        
        # Reset state
        await self._buffer.clear()
        self._state = PlaybackState.IDLE
        self._session_active = True
        self._first_chunk = True
        logger.info("🎵 Playback session started")

    async def feed(self, pcm_bytes: bytes) -> bool:
        """
        Feed audio chunk to the playback buffer.
        
        Args:
            pcm_bytes: Raw PCM audio data (must be aligned to int16, len % 2 == 0)
        
        Returns:
            True if accepted, False if buffer full
        """
        if not self._session_active:
            return False
        
        if not pcm_bytes or len(pcm_bytes) == 0:
            return True
        
        # Validate alignment
        if len(pcm_bytes) % 2 != 0:
            import logging
            logging.getLogger(__name__).warning(f"PCM data not aligned to int16: {len(pcm_bytes)} bytes")
            pcm_bytes = pcm_bytes[:-1]  # Trim last byte
        
        return await self._buffer.push(pcm_bytes)

    async def end_session(self):
        """
        End the current playback session.
        Waits for buffer to drain, applies fade-out, closes stream.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if not self._session_active:
            return
        
        self._session_active = False
        
        # Wait for buffer to mostly drain (allow up to 2 seconds)
        for _ in range(20):
            size = await self._buffer.size()
            if size < self.chunk_size * 2:
                break
            await asyncio.sleep(0.1)
        
        # Transition to IDLE will trigger fade-out and stream close
        self._state = PlaybackState.IDLE
        logger.info("🎵 Playback session ended")

    async def interrupt(self):
        """
        Immediately interrupt playback (e.g., on wake word detection).
        Clears buffer, applies quick fade-out, closes stream.
        """
        import logging
        logging.getLogger(__name__).info("⚡ Playback interrupted")
        
        self._session_active = False
        await self._buffer.clear()
        self._state = PlaybackState.IDLE

    async def _playback_loop(self):
        """
        Main playback loop.
        
        State machine:
        - IDLE: No output stream, waiting for session
        - BUFFERING: Accumulating initial chunks, no playback yet
        - PLAYING: Continuous playback from buffer
        
        BUFFERING only happens once per session at the start.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        while not self._stop_event.is_set():
            if self._state == PlaybackState.IDLE:
                # No active session, close stream if open
                if self._output_stream is not None:
                    self._output_stream.stop()
                    self._output_stream.close()
                    self._output_stream = None
                    logger.debug("Output stream closed")
                
                await asyncio.sleep(0.05)
                
                # Check if new session started
                if self._session_active:
                    self._state = PlaybackState.BUFFERING
                    logger.info("🎵 State: BUFFERING")
                
                continue
            
            elif self._state == PlaybackState.BUFFERING:
                # Wait for enough chunks before starting playback
                chunk_count = await self._buffer.peek_chunk_count()
                
                if chunk_count >= self.buffering_chunks:
                    # Open output stream
                    if self._output_stream is None:
                        self._output_stream = sd.OutputStream(
                            samplerate=self.sample_rate,
                            channels=self.channels,
                            dtype=self.dtype,
                            device=self.device,
                            blocksize=1024,
                            latency="low",
                        )
                        self._output_stream.start()
                        logger.info("🔊 Output stream opened")
                    
                    self._state = PlaybackState.PLAYING
                    logger.info(f"🎵 State: PLAYING (buffered {chunk_count} chunks)")
                else:
                    # Not enough data yet, wait briefly
                    await self._buffer.wait_for_data(timeout=0.01)
                
                continue
            
            elif self._state == PlaybackState.PLAYING:
                # Check if session ended
                if not self._session_active:
                    # Drain remaining buffer with fade-out on last chunk
                    await self._drain_buffer_with_fadeout()
                    self._state = PlaybackState.IDLE
                    logger.info("🎵 State: IDLE (session ended)")
                    continue
                
                # Pop next chunk from buffer
                chunk = await self._buffer.pop_chunk()
                
                if chunk is None:
                    # Buffer temporarily empty, wait for data
                    has_data = await self._buffer.wait_for_data(timeout=0.005)
                    if not has_data:
                        # Still no data after waiting, check again
                        logger.debug("Jitter: buffer empty, waiting...")
                    continue
                
                # Convert to numpy array
                audio_data = np.frombuffer(chunk, dtype=np.int16).copy()
                
                # Apply fade-in only to the very first chunk of the session
                if self._first_chunk:
                    audio_data = apply_fade_in(audio_data, self.fade_samples)
                    self._first_chunk = False
                    logger.debug(f"Applied fade-in ({self.fade_samples} samples)")
                
                # Write to output stream
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._output_stream.write, audio_data
                    )
                except Exception as e:
                    logger.error(f"Error writing to output stream: {e}")
                    self._state = PlaybackState.IDLE

    async def _drain_buffer_with_fadeout(self):
        """Drain remaining buffer and apply fade-out to last chunk."""
        import logging
        logger = logging.getLogger(__name__)
        
        if self._output_stream is None:
            return
        
        last_chunk = None
        while True:
            chunk = await self._buffer.pop_chunk()
            if chunk is None:
                break
            
            if last_chunk is not None:
                # Play previous chunk without fade
                audio_data = np.frombuffer(last_chunk, dtype=np.int16)
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._output_stream.write, audio_data
                    )
                except Exception as e:
                    logger.error(f"Error during drain: {e}")
                    break
            
            last_chunk = chunk
        
        # Apply fade-out to last chunk
        if last_chunk is not None:
            audio_data = np.frombuffer(last_chunk, dtype=np.int16).copy()
            audio_data = apply_fade_out(audio_data, self.fade_samples)
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._output_stream.write, audio_data
                )
                logger.debug(f"Applied fade-out to last chunk ({self.fade_samples} samples)")
            except Exception as e:
                logger.error(f"Error writing fade-out: {e}")

    async def stop(self):
        """Stop playback system and close resources."""
        # Signal playback loop to stop
        self._stop_event.set()
        self._session_active = False

        # Wait for playback task to finish
        if self._playback_task:
            await self._playback_task
            self._playback_task = None

        # Close stream
        if self._output_stream is not None:
            self._output_stream.stop()
            self._output_stream.close()
            self._output_stream = None

        # Clear buffer
        await self._buffer.clear()

    # Legacy compatibility methods
    
    async def play(self, pcm_bytes):
        """
        Legacy method for compatibility.
        Starts a session, plays audio, and ends session.
        
        For new code, use begin_session() + feed() + end_session().
        """
        await self.begin_session()
        await self.feed(pcm_bytes)
        await self.end_session()

    async def is_playing(self):
        """Check if audio is currently playing."""
        return self._state == PlaybackState.PLAYING

    async def buffer_size(self):
        """Get current buffer size in bytes."""
        return await self._buffer.size()
    
    @property
    def state(self) -> PlaybackState:
        """Get current playback state."""
        return self._state
    
    @property
    def is_session_active(self) -> bool:
        """Check if a playback session is active."""
        return self._session_active

    async def __aenter__(self):
        """Async context manager support."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager support."""
        await self.stop()
