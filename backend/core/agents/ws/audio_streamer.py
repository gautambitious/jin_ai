"""
AudioStreamer class for streaming audio over WebSocket connections.

Handles sending audio control messages and PCM audio chunks.
Async-only implementation with no Django model logic.
"""

import asyncio
import logging
from typing import Optional, AsyncIterator

from agents.ws.protocol import audio_start, audio_end, stop_playback
from agents.constants import AudioFormat

logger = logging.getLogger(__name__)


class AudioStreamer:
    """
    Manages audio streaming over a WebSocket connection.

    Handles sending:
    - audio_start control message (JSON text frame)
    - PCM audio chunks (binary frames)
    - audio_end control message (JSON text frame)
    - stop_playback control message (JSON text frame)

    Async-only, no blocking operations.
    """

    def __init__(
        self,
        websocket,
        stream_id: str,
        sample_rate: int = AudioFormat.DEFAULT_SAMPLE_RATE,
        channels: int = 1,
    ):
        """
        Initialize AudioStreamer.

        Args:
            websocket: WebSocket connection (must have async send() method)
            stream_id: Unique identifier for this audio stream
            sample_rate: Audio sample rate in Hz (default: 24000)
            channels: Number of audio channels (default: 1)
        """
        self.websocket = websocket
        self.stream_id = stream_id
        self.sample_rate = sample_rate
        self.channels = channels
        self._is_streaming = False
        self._stop_requested = False

    async def send_audio_start(self) -> None:
        """
        Send audio_start control message.

        Marks the beginning of an audio stream.
        Should be called before sending any audio chunks.
        """
        message = audio_start(self.stream_id, self.sample_rate, self.channels)
        await self.websocket.send(text_data=message)
        self._is_streaming = True
        logger.info(
            f"Sent audio_start: stream_id={self.stream_id}, "
            f"sample_rate={self.sample_rate}, channels={self.channels}"
        )

    async def send_audio_chunk(self, chunk: bytes) -> None:
        """
        Send a single PCM audio chunk as binary WebSocket frame.

        Args:
            chunk: Raw PCM audio bytes
        """
        if not chunk:
            logger.warning("Attempted to send empty audio chunk")
            return

        await self.websocket.send(bytes_data=chunk)
        logger.debug(f"Sent audio chunk: {len(chunk)} bytes")

    async def send_audio_end(self) -> None:
        """
        Send audio_end control message.

        Marks the end of an audio stream.
        Should be called after all audio chunks have been sent.
        """
        message = audio_end(self.stream_id)
        await self.websocket.send(text_data=message)
        self._is_streaming = False
        logger.info(f"Sent audio_end: stream_id={self.stream_id}")

    async def send_stop_playback(self) -> None:
        """
        Send stop_playback control message.

        Immediately stops audio playback on the client.
        Can be called at any time during streaming.
        """
        message = stop_playback()
        await self.websocket.send(text_data=message)
        self._stop_requested = True
        self._is_streaming = False
        logger.info("Sent stop_playback")

    async def stream_audio(
        self,
        audio_chunks: AsyncIterator[bytes],
        send_start: bool = True,
        send_end: bool = True,
    ) -> None:
        """
        Stream audio chunks with automatic start/end messages.

        Args:
            audio_chunks: Async iterator yielding PCM audio chunks
            send_start: Whether to send audio_start message (default: True)
            send_end: Whether to send audio_end message (default: True)

        Example:
            >>> async def generate_chunks():
            ...     yield chunk1
            ...     yield chunk2
            >>> await streamer.stream_audio(generate_chunks())
        """
        try:
            if send_start:
                await self.send_audio_start()

            self._stop_requested = False

            async for chunk in audio_chunks:
                if self._stop_requested:
                    logger.info("Streaming stopped by stop request")
                    break

                await self.send_audio_chunk(chunk)

            if send_end and not self._stop_requested:
                await self.send_audio_end()

        except Exception as e:
            logger.error(f"Error during audio streaming: {e}")
            self._is_streaming = False
            raise

    async def stream_audio_bytes(
        self,
        audio_bytes: bytes,
        chunk_iterator,
        send_start: bool = True,
        send_end: bool = True,
    ) -> None:
        """
        Stream complete audio bytes using a chunker.

        Args:
            audio_bytes: Complete raw PCM audio bytes
            chunk_iterator: Function that takes audio_bytes and returns iterator
            send_start: Whether to send audio_start message (default: True)
            send_end: Whether to send audio_end message (default: True)

        Example:
            >>> from agents.ws.audio_chunker import chunk_audio
            >>> audio = generate_tone(440, 1.0)
            >>> chunker = lambda data: chunk_audio(data, 16000, 20)
            >>> await streamer.stream_audio_bytes(audio, chunker)
        """
        try:
            if send_start:
                await self.send_audio_start()

            self._stop_requested = False

            for chunk in chunk_iterator(audio_bytes):
                if self._stop_requested:
                    logger.info("Streaming stopped by stop request")
                    break

                await self.send_audio_chunk(chunk)
                # Yield control to event loop
                await asyncio.sleep(0)

            if send_end and not self._stop_requested:
                await self.send_audio_end()

        except Exception as e:
            logger.error(f"Error during audio streaming: {e}")
            self._is_streaming = False
            raise

    @property
    def is_streaming(self) -> bool:
        """Check if currently streaming audio."""
        return self._is_streaming

    @property
    def stop_requested(self) -> bool:
        """Check if stop was requested."""
        return self._stop_requested

    def request_stop(self) -> None:
        """
        Request streaming to stop.

        Sets internal flag that will be checked during streaming.
        Does not send stop_playback message - use send_stop_playback() for that.
        """
        self._stop_requested = True
        logger.info("Stop requested for audio stream")
