"""
Audio WebSocket Helper Service

This module provides helper functions for streaming audio over WebSocket connections.
It integrates TTS service with WebSocket audio streaming to provide a complete
text-to-audio-over-websocket pipeline.
"""

import asyncio
import logging
import uuid
from typing import Optional, AsyncIterator

from agents.services.tts_service import TTSService, TTSServiceError
from agents.ws.audio_streamer import AudioStreamer
from agents.ws.audio_chunker import chunk_audio
from agents.constants import AudioFormat

logger = logging.getLogger(__name__)


class AudioWebSocketHelper:
    """
    Helper service for streaming audio over WebSocket connections.

    Provides methods to:
    1. Stream pre-generated audio chunks to WebSocket consumers
    2. Generate audio from text using TTS and stream it
    3. Play audio buffers in chunks over WebSocket
    """

    def __init__(
        self,
        websocket,
        sample_rate: int = 16000,
        channels: int = 1,
        tts_service: Optional[TTSService] = None,
    ):
        """
        Initialize AudioWebSocketHelper.

        Args:
            websocket: WebSocket connection (AsyncWebsocketConsumer instance)
            sample_rate: Audio sample rate in Hz (default: 16000)
            channels: Number of audio channels (default: 1)
            tts_service: Optional TTS service instance (creates new one if None)
        """
        self.websocket = websocket
        self.sample_rate = sample_rate
        self.channels = channels
        self.tts_service = tts_service or TTSService()

        logger.info(
            f"AudioWebSocketHelper initialized: "
            f"sample_rate={sample_rate}, channels={channels}"
        )

    async def stream_audio_buffer(
        self,
        audio_buffer: bytes,
        chunk_duration_ms: int = 20,
        stream_id: Optional[str] = None,
    ) -> None:
        """
        Stream an audio buffer in chunks over WebSocket.

        Takes a complete audio buffer and streams it in time-based chunks
        to the WebSocket consumer for playback.

        Args:
            audio_buffer: Complete raw PCM audio bytes
            chunk_duration_ms: Duration of each chunk in milliseconds (default: 20ms)
            stream_id: Optional unique identifier for this stream (auto-generated if None)

        Example:
            >>> helper = AudioWebSocketHelper(websocket)
            >>> audio_data = b'\\x00' * 32000  # Some PCM audio
            >>> await helper.stream_audio_buffer(audio_data)
        """
        if not audio_buffer:
            logger.warning("Attempted to stream empty audio buffer")
            return

        stream_id = stream_id or f"audio_buffer_{uuid.uuid4()}"

        logger.info(
            f"Streaming audio buffer: stream_id={stream_id}, "
            f"size={len(audio_buffer)} bytes, chunk_duration={chunk_duration_ms}ms"
        )

        try:
            # Create audio streamer
            streamer = AudioStreamer(
                websocket=self.websocket,
                stream_id=stream_id,
                sample_rate=self.sample_rate,
                channels=self.channels,
            )

            # Create chunker function
            chunker = lambda data: chunk_audio(
                data,
                sample_rate=self.sample_rate,
                chunk_duration_ms=chunk_duration_ms,
            )

            # Stream the audio with chunking
            await streamer.stream_audio_bytes(
                audio_buffer,
                chunker,
                send_start=True,
                send_end=True,
            )

            logger.info(f"Successfully streamed audio buffer: stream_id={stream_id}")

        except Exception as e:
            logger.error(f"Error streaming audio buffer: {e}", exc_info=True)
            raise

    async def stream_audio_chunks(
        self,
        audio_chunks: AsyncIterator[bytes],
        stream_id: Optional[str] = None,
    ) -> None:
        """
        Stream audio chunks directly over WebSocket.

        Takes an async iterator of audio chunks and streams them
        directly to the WebSocket consumer.

        Args:
            audio_chunks: Async iterator yielding audio chunk bytes
            stream_id: Optional unique identifier for this stream (auto-generated if None)

        Example:
            >>> async def generate_chunks():
            ...     for i in range(10):
            ...         yield audio_chunk_data
            >>> helper = AudioWebSocketHelper(websocket)
            >>> await helper.stream_audio_chunks(generate_chunks())
        """
        stream_id = stream_id or f"audio_chunks_{uuid.uuid4()}"

        logger.info(f"Streaming audio chunks: stream_id={stream_id}")

        try:
            # Create audio streamer
            streamer = AudioStreamer(
                websocket=self.websocket,
                stream_id=stream_id,
                sample_rate=self.sample_rate,
                channels=self.channels,
            )

            # Stream the audio chunks
            await streamer.stream_audio(
                audio_chunks,
                send_start=True,
                send_end=True,
            )

            logger.info(f"Successfully streamed audio chunks: stream_id={stream_id}")

        except Exception as e:
            logger.error(f"Error streaming audio chunks: {e}", exc_info=True)
            raise

    async def text_to_speech_stream(
        self,
        text: str,
        stream_id: Optional[str] = None,
        output_format: str = AudioFormat.DEFAULT_STREAMING_FORMAT,
    ) -> None:
        """
        Convert text to speech using TTS and stream it over WebSocket.

        This is the main end-to-end function that:
        1. Takes text as input
        2. Uses TTS service to generate audio
        3. Streams the audio over WebSocket for playback

        This is your primary use case - text in, audio playback out!

        Args:
            text: Text to convert to speech and play
            stream_id: Optional unique identifier for this stream (auto-generated if None)
            output_format: Audio format for TTS output (default: opus for streaming)

        Raises:
            TTSServiceError: If TTS generation fails

        Example:
            >>> helper = AudioWebSocketHelper(websocket)
            >>> await helper.text_to_speech_stream(
            ...     "Hello! This is Jin speaking.",
            ... )
        """
        if not text or not text.strip():
            logger.warning("Attempted to stream empty text")
            return

        stream_id = stream_id or f"tts_{uuid.uuid4()}"

        logger.info(
            f"Starting text-to-speech stream: stream_id={stream_id}, "
            f"text_length={len(text)}, format={output_format}"
        )

        try:
            # Create audio streamer
            streamer = AudioStreamer(
                websocket=self.websocket,
                stream_id=stream_id,
                sample_rate=self.sample_rate,
                channels=self.channels,
            )

            # Send audio start message
            await streamer.send_audio_start()

            # Generate and stream audio chunks from TTS
            chunk_count = 0
            total_bytes = 0

            # The TTS service returns a synchronous generator
            # We need to wrap it for async streaming
            # Note: sample_rate should only be passed for uncompressed formats (linear16, wav, pcm)
            # Compressed formats (opus, mp3, flac) don't accept sample_rate parameter
            tts_kwargs = {
                "text": text,
            }

            # Set encoding based on format - Deepgram uses 'encoding' parameter
            format_lower = output_format.lower()
            if format_lower in ["linear16", "pcm"]:
                tts_kwargs["encoding"] = "linear16"
                tts_kwargs["sample_rate"] = self.sample_rate
            elif format_lower in ["wav", "wave"]:
                tts_kwargs["encoding"] = "linear16"
                tts_kwargs["sample_rate"] = self.sample_rate
                tts_kwargs["container"] = "wav"
            elif format_lower == "opus":
                tts_kwargs["encoding"] = "opus"
            elif format_lower == "mp3":
                tts_kwargs["encoding"] = "mp3"
            elif format_lower == "flac":
                tts_kwargs["encoding"] = "flac"
            else:
                # Default to linear16
                tts_kwargs["encoding"] = "linear16"
                tts_kwargs["sample_rate"] = self.sample_rate

            audio_generator = self.tts_service.generate_audio(**tts_kwargs)

            for audio_chunk in audio_generator:
                if audio_chunk:
                    chunk_count += 1
                    total_bytes += len(audio_chunk)

                    # Send chunk over WebSocket
                    await streamer.send_audio_chunk(audio_chunk)

                    # Yield control to event loop to prevent blocking
                    await asyncio.sleep(0)

            # Send audio end message
            await streamer.send_audio_end()

            logger.info(
                f"Successfully completed text-to-speech stream: "
                f"stream_id={stream_id}, chunks={chunk_count}, "
                f"total_bytes={total_bytes}"
            )

        except TTSServiceError as e:
            logger.error(f"TTS error during streaming: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error during text-to-speech streaming: {e}", exc_info=True)
            raise

    async def stop_playback(self) -> None:
        """
        Send stop playback command to WebSocket consumer.

        Immediately stops any audio playback on the client side.
        """
        try:
            # Create a temporary streamer to send stop command
            stream_id = f"stop_{uuid.uuid4()}"
            streamer = AudioStreamer(
                websocket=self.websocket,
                stream_id=stream_id,
                sample_rate=self.sample_rate,
                channels=self.channels,
            )

            await streamer.send_stop_playback()
            logger.info("Stop playback command sent")

        except Exception as e:
            logger.error(f"Error sending stop playback: {e}", exc_info=True)
            raise


# Convenience function for quick usage
async def play_text_on_websocket(
    websocket,
    text: str,
    sample_rate: int = 16000,
    channels: int = 1,
) -> None:
    """
    Quick function to play text as audio on a WebSocket connection.

    This is a convenience function that creates an AudioWebSocketHelper
    and streams text-to-speech in one call.

    Args:
        websocket: WebSocket connection (AsyncWebsocketConsumer instance)
        text: Text to convert to speech and play
        sample_rate: Audio sample rate in Hz (default: 16000)
        channels: Number of audio channels (default: 1)

    Example:
        >>> await play_text_on_websocket(
        ...     websocket=self,
        ...     text="Hello! This is a test message.",
        ... )
    """
    helper = AudioWebSocketHelper(
        websocket=websocket,
        sample_rate=sample_rate,
        channels=channels,
    )
    await helper.text_to_speech_stream(text)
