"""
Audio streaming protocol handler.

Simple, lightweight handler for audio streaming over WebSocket.
No business logic, just protocol parsing and forwarding.
"""

import json
import logging
from typing import Optional, TYPE_CHECKING
from audio.buffer import AudioBuffer

if TYPE_CHECKING:
    from audio.player import AudioPlayer

logger = logging.getLogger(__name__)


class AudioStreamHandler:
    """
    Handle audio streaming protocol over WebSocket.

    Protocol:
        - JSON: {"type": "audio_start", "stream_id": "...", "sample_rate": 16000}
        - Binary: raw PCM audio chunks
        - JSON: {"type": "audio_end", "stream_id": "..."}
        - JSON: {"type": "stop_playback"}

    Usage:
        handler = AudioStreamHandler(audio_buffer, audio_player)

        # In WebSocket message callback:
        if isinstance(message, str):
            await handler.handle_json_message(message)
        else:
            await handler.handle_binary_message(message)
    """

    def __init__(self, audio_buffer: AudioBuffer, audio_player: "AudioPlayer"):
        """
        Initialize audio stream handler.

        Args:
            audio_buffer: AudioBuffer instance to receive audio chunks
            audio_player: AudioPlayer instance for playback control
        """
        self.audio_buffer = audio_buffer
        self.audio_player = audio_player
        self._active_stream_id: Optional[str] = None
        self._sample_rate: int = 16000  # Default sample rate
        self._playback_started: bool = False

    async def handle_json_message(self, message: str):
        """
        Handle JSON control messages.

        Args:
            message: JSON string message
        """
        try:
            data = json.loads(message)

            if not isinstance(data, dict) or "type" not in data:
                logger.warning("Invalid JSON message format, ignoring")
                return

            msg_type = data.get("type")

            if msg_type == "audio_start":
                await self._handle_audio_start(data)
            elif msg_type == "audio_end":
                await self._handle_audio_end(data)
            elif msg_type == "stop_playback":
                await self._handle_stop_playback()
            else:
                logger.debug(f"Unknown message type: {msg_type}, ignoring")

        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON message, ignoring")
        except Exception as e:
            logger.error(f"Error handling JSON message: {e}")

    async def handle_binary_message(self, data: bytes):
        """
        Handle binary audio chunk messages.

        Args:
            data: Raw PCM audio data
        """
        try:
            # Only forward audio if we have an active stream
            if not self._active_stream_id:
                logger.debug("Received audio chunk without active stream, ignoring")
                return

            if not data:
                logger.debug("Received empty audio chunk, ignoring")
                return

            # Start playback on first chunk
            if not self._playback_started:
                logger.info(f"Starting audio playback (first chunk: {len(data)} bytes)")
                self._playback_started = True
                self.audio_player._is_playing = True

            # Forward chunk to audio buffer
            success = await self.audio_buffer.push(data)
            if success:
                logger.debug(f"Forwarded {len(data)} bytes to audio buffer")
            else:
                logger.warning(f"Audio buffer full, dropped {len(data)} bytes")

        except Exception as e:
            logger.error(f"Error handling binary message: {e}")

    async def _handle_audio_start(self, data: dict):
        """
        Handle audio_start message.

        Args:
            data: Parsed JSON message
        """
        stream_id = data.get("stream_id")
        sample_rate = data.get("sample_rate", 16000)

        if not stream_id:
            logger.warning("audio_start missing stream_id, ignoring")
            return

        # If there's already an active stream, stop it first
        if self._active_stream_id and self._active_stream_id != stream_id:
            logger.info(f"Stopping existing stream {self._active_stream_id}")
            await self.audio_buffer.clear()
            self._playback_started = False

        self._active_stream_id = stream_id
        self._sample_rate = sample_rate

        logger.info(f"Started audio stream: {stream_id}, rate: {sample_rate}Hz")

    async def _handle_audio_end(self, data: dict):
        """
        Handle audio_end message.

        Args:
            data: Parsed JSON message
        """
        stream_id = data.get("stream_id")

        if not stream_id:
            logger.warning("audio_end missing stream_id, ignoring")
            return

        # Only process if it matches the active stream
        if self._active_stream_id != stream_id:
            logger.debug(f"audio_end for non-active stream {stream_id}, ignoring")
            return

        logger.info(f"Ended audio stream: {stream_id}")
        self._active_stream_id = None
        self._playback_started = False

    async def _handle_stop_playback(self):
        """Handle stop_playback message."""
        logger.info("Stopping playback")
        self.audio_player._is_playing = False
        await self.audio_buffer.clear()
        self._playback_started = False
        self._active_stream_id = None

    @property
    def active_stream_id(self) -> Optional[str]:
        """Get current active stream ID."""
        return self._active_stream_id

    @property
    def sample_rate(self) -> int:
        """Get current sample rate."""
        return self._sample_rate

    @property
    def is_streaming(self) -> bool:
        """Check if actively streaming."""
        return self._active_stream_id is not None
