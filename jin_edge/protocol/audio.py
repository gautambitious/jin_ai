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
        
    Features:
        - Single playback session per response
        - No buffering delays (player handles initial buffering)
        - Continuous playback across sentence boundaries

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
            audio_buffer: AudioBuffer instance (legacy, may not be used)
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
        self._led_control_enabled: bool = True  # Can be disabled during streaming input
        self._playback_monitor_task: Optional[asyncio.Task] = None

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

            # Feed chunk directly to audio player
            success = await self.audio_player.feed(data)
            if success:
                logger.debug(f"Fed {len(data)} bytes to audio player")
            else:
                logger.warning(f"Audio player buffer full, dropped {len(data)} bytes")

        except Exception as e:
            logger.error(f"Error handling binary message: {e}")

    async def _handle_audio_start(self, data: dict):
        """
        Handle audio_start message.
        Begins a new playback session.

        Args:
            data: Parsed JSON message
        """
        stream_id = data.get("stream_id")
        sample_rate = data.get("sample_rate", 16000)

        if not stream_id:
            logger.warning("audio_start missing stream_id, ignoring")
            return

        # If there's already an active stream, end it first
        if self._active_stream_id and self._active_stream_id != stream_id:
            logger.info(f"Stopping existing stream {self._active_stream_id}")
            await self.audio_player.end_session()

        self._active_stream_id = stream_id
        self._sample_rate = sample_rate

        # Begin new playback session
        await self.audio_player.begin_session()
        
        # Set LED to speaking state only if LED control is enabled
        if self.led_controller and self._led_control_enabled:
            await self.led_controller.set_speaking()
            logger.info("💡 LED: Speaking (bright blue)")
        
        # Start monitoring task to turn off LED when playback finishes
        if self._playback_monitor_task is None or self._playback_monitor_task.done():
            self._playback_monitor_task = asyncio.create_task(self._monitor_playback())

        logger.info(f"🎵 Started audio stream: {stream_id}, rate: {sample_rate}Hz")

    async def _handle_audio_end(self, data: dict):
        """
        Handle audio_end message.
        Ends the playback session (fade-out and stream close).

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

        logger.info(f"🎵 Ending audio stream: {stream_id}")
        
        # End playback session (will drain buffer with fade-out)
        await self.audio_player.end_session()
        
        self._active_stream_id = None

    async def _handle_stop_playback(self):
        """Handle stop_playback message (interrupt)."""
        logger.info("⚡ Stopping playback (interrupt)")
        
        # Interrupt playback immediately
        await self.audio_player.interrupt()
        
        self._active_stream_id = None
        
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
            logger.info("💡 LED: Off (playback stopped)")
    
    async def _monitor_playback(self):
        """Monitor playback and turn off LED when session finishes."""
        try:
            # Wait for playback session to finish
            while self.audio_player.is_session_active:
                await asyncio.sleep(0.1)
            
            # Wait a bit more to ensure audio has finished playing
            await asyncio.sleep(0.3)
            
            # Turn off LED only if LED control is enabled
            if self._led_control_enabled:
                logger.info("💡 LED: Off (playback complete)")
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
    
    def set_led_control(self, enabled: bool):
        """Enable or disable LED control from this handler.
        
        Useful when another component (like StreamingWakeWordController)
        needs to take over LED control temporarily.
        """
        self._led_control_enabled = enabled
        logger.debug(f"LED control {'enabled' if enabled else 'disabled'} in AudioStreamHandler")
