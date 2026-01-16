"""
Audio streaming protocol handler.

Simple, lightweight handler for audio streaming over WebSocket.
No business logic, just protocol parsing and forwarding.
"""

import asyncio
import json
import logging
from typing import Optional, TYPE_CHECKING
from audio.buffer import AudioBuffer

if TYPE_CHECKING:
    from audio.player import AudioPlayer
    from led.controller import LEDController

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

    def __init__(self, audio_buffer: AudioBuffer, audio_player: "AudioPlayer", led_controller: Optional["LEDController"] = None, on_message: Optional[callable] = None):
        """
        Initialize audio stream handler.

        Args:
            audio_buffer: AudioBuffer instance to receive audio chunks
            audio_player: AudioPlayer instance for playback control
            led_controller: Optional LED controller for visual feedback
            on_message: Optional callback for non-audio messages (transcript, etc.)
        """
        self.audio_buffer = audio_buffer
        self.audio_player = audio_player
        self.led_controller = led_controller
        self.on_message = on_message
        self._active_stream_id: Optional[str] = None
        self._sample_rate: int = 16000  # Default sample rate
        self._playback_started: bool = False
        self._playback_monitor_task: Optional[asyncio.Task] = None
        self._silence_filler_task: Optional[asyncio.Task] = None
        self._stop_silence_filler = asyncio.Event()

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
                # Forward non-audio messages to callback if registered
                if self.on_message:
                    try:
                        await self.on_message(data)
                    except Exception as e:
                        logger.error(f"Error in message callback: {e}")
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

            # Pre-buffer audio before starting playback to prevent clicks
            if not self._playback_started:
                # Get current buffer size
                buffer_size = await self.audio_buffer.size()
                # Start playback once we have at least 8KB buffered (0.25s at 16kHz 16-bit mono)
                if buffer_size >= 8192:
                    logger.info(f"Starting audio playback (buffer: {buffer_size} bytes)")
                    self._playback_started = True
                    self.audio_player._is_playing = True
                    
                    # Set LED to speaking state
                    if self.led_controller:
                        await self.led_controller.set_speaking()
                        
                    # Start monitoring task to turn off LED when buffer empties
                    if self._playback_monitor_task is None or self._playback_monitor_task.done():
                        self._playback_monitor_task = asyncio.create_task(self._monitor_playback())
                    
                    # Start silence filler task to keep buffer from emptying
                    if self._silence_filler_task is None or self._silence_filler_task.done():
                        self._stop_silence_filler.clear()
                        self._silence_filler_task = asyncio.create_task(self._fill_silence())
                else:
                    logger.debug(f"Pre-buffering audio: {buffer_size}/8192 bytes")

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
        
        # Don't turn off LED yet - audio is still playing from buffer
        # The monitoring task will handle turning off LED when buffer empties

    async def _handle_stop_playback(self):
        """Handle stop_playback message."""
        logger.info("Stopping playback")
        self.audio_player._is_playing = False
        await self.audio_buffer.clear()
        self._playback_started = False
        self._active_stream_id = None
        
        # Stop silence filler
        self._stop_silence_filler.set()
        if self._silence_filler_task and not self._silence_filler_task.done():
            self._silence_filler_task.cancel()
            try:
                await self._silence_filler_task
            except asyncio.CancelledError:
                pass
        
        # Cancel monitoring task
        if self._playback_monitor_task and not self._playback_monitor_task.done():
            self._playback_monitor_task.cancel()
            try:
                await self._playback_monitor_task
            except asyncio.CancelledError:
                pass
        
        # Turn off LED
        if self.led_controller:
            await self.led_controller.set_off()
    
    async def _fill_silence(self):
        """Continuously fill buffer with silence to prevent it from emptying completely."""
        try:
            # 100ms of silence = 3200 bytes at 16kHz, 16-bit mono
            silence_chunk = b'\x00' * 3200
            
            while not self._stop_silence_filler.is_set():
                # Only add silence if buffer is getting low and stream is active
                buffer_size = await self.audio_buffer.size()
                
                # If buffer drops below 8KB, add silence aggressively
                if buffer_size < 8192 and self._active_stream_id:
                    success = await self.audio_buffer.push(silence_chunk)
                    if success:
                        logger.debug(f"Added silence padding, buffer now: {buffer_size + 3200} bytes")
                
                # Check every 50ms for more responsive filling
                await asyncio.sleep(0.05)
                
        except asyncio.CancelledError:
            logger.debug("Silence filler cancelled")
        except Exception as e:
            logger.error(f"Error in silence filler: {e}")
    
    async def _monitor_playback(self):
        """Monitor audio buffer and turn off LED when playback finishes."""
        try:
            # Wait for stream to end
            while self._active_stream_id is not None:
                await asyncio.sleep(0.1)
            
            # Stream ended, wait for buffer to empty and stay empty
            logger.debug("Audio stream ended, monitoring buffer...")
            empty_count = 0
            while empty_count < 3:  # Buffer must be empty for 3 consecutive checks (300ms)
                buffer_size = await self.audio_buffer.size()
                if buffer_size == 0:
                    empty_count += 1
                else:
                    empty_count = 0  # Reset if buffer has data
                await asyncio.sleep(0.1)
            
            # Buffer has been empty for a while, turn off LED
            logger.debug("Audio buffer empty, turning off LED")
            if self.led_controller:
                await self.led_controller.set_off()
                
        except asyncio.CancelledError:
            logger.debug("Playback monitoring cancelled")
        except Exception as e:
            logger.error(f"Error monitoring playback: {e}")

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
