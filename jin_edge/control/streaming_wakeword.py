"""
Optimized streaming wake-word controller.

OPTIMIZED for low-latency:
- Streams audio chunks IMMEDIATELY (no buffering)
- Uses new streaming endpoint
- Receives interim transcripts
- Supports interruption
"""

import asyncio
import json
import logging
import time
from typing import Optional, TYPE_CHECKING
from audio.mic_stream import MicStream
from audio.silence_detector import SilenceDetector, SpeechEvent
from wakeword.base import WakeWordEvent, WakeWordDetector
from ws.client import WebSocketClient
import env_vars

if TYPE_CHECKING:
    from led.controller import LEDController

# Try to import Porcupine, fall back to stub
try:
    from wakeword.porcupine_detector import PorcupineDetector

    HAS_PORCUPINE = True
except ImportError:
    from wakeword.stub_detector import StubWakeWordDetector

    HAS_PORCUPINE = False

logger = logging.getLogger(__name__)


class StreamingWakeWordController:
    """
    OPTIMIZED streaming wake-word controller.

    Key Differences from WakeWordStreamer:
    - Streams audio chunks IMMEDIATELY (no buffering)
    - Connects to optimized streaming endpoint
    - Receives interim transcripts for feedback
    - Supports interruption during response playback
    - Lower latency by eliminating all buffering

    Workflow:
        1. Listen for wake word
        2. On wake word → send audio_input_start
        3. Stream EACH audio chunk immediately (NO BUFFERING!)
        4. On silence → send stop_audio_input
        5. Receive and play response
        6. Return to listening
    """

    def __init__(
        self,
        ws_client: WebSocketClient,
        wake_word: str = "hey jin",
        wake_word_detector: Optional[WakeWordDetector] = None,
        mic_stream: Optional[MicStream] = None,
        sample_rate: int = 16000,
        channels: int = 1,
        silence_threshold: float = 500.0,
        silence_duration_ms: Optional[int] = None,
        listening_timeout_seconds: Optional[int] = None,
        use_relative_silence: Optional[bool] = None,
        relative_silence_threshold: Optional[float] = None,
        led_controller: Optional["LEDController"] = None,
        protocol_handler: Optional[object] = None,
    ):
        """Initialize optimized streaming wake word controller."""
        self.ws_client = ws_client
        self.wake_word = wake_word
        self.sample_rate = sample_rate
        self.channels = channels
        self.led_controller = led_controller
        self.protocol_handler = protocol_handler

        # Get settings from env_vars if not provided
        self.silence_duration_ms = silence_duration_ms or env_vars.SILENCE_DURATION_MS
        self.listening_timeout_seconds = (
            listening_timeout_seconds or env_vars.LISTENING_TIMEOUT_SECONDS
        )
        self.use_relative_silence = (
            use_relative_silence if use_relative_silence is not None else True
        )
        self.relative_silence_threshold = (
            relative_silence_threshold or env_vars.RELATIVE_SILENCE_THRESHOLD
        )

        # Create mic stream
        self.mic_stream = mic_stream or MicStream(
            sample_rate=sample_rate, channels=channels
        )

        # Create wake word detector
        if wake_word_detector:
            self.wake_word_detector = wake_word_detector
        elif HAS_PORCUPINE and env_vars.PORCUPINE_ACCESS_KEY:
            try:
                self.wake_word_detector = PorcupineDetector(
                    access_key=env_vars.PORCUPINE_ACCESS_KEY,
                    model_path=env_vars.PORCUPINE_MODEL_PATH,
                    wake_word=wake_word,
                    on_detection=None,
                )
                logger.info("Using Porcupine wake word detector")
            except Exception as e:
                logger.warning(f"Failed to initialize Porcupine: {e}")
                from wakeword.stub_detector import StubWakeWordDetector

                self.wake_word_detector = StubWakeWordDetector(
                    wake_word=wake_word, on_detection=None
                )
        else:
            from wakeword.stub_detector import StubWakeWordDetector

            self.wake_word_detector = StubWakeWordDetector(
                wake_word=wake_word, on_detection=None
            )

        # Create silence detector
        self.silence_detector = SilenceDetector(
            sample_rate=sample_rate,
            silence_threshold=silence_threshold,
            silence_duration_ms=self.silence_duration_ms,
            on_speech_start=None,
            on_speech_end=None,
            use_relative_threshold=self.use_relative_silence,
            relative_threshold_ratio=self.relative_silence_threshold,
        )

        # State management
        self._is_running = False
        self._is_streaming = False
        self._is_playing_response = False
        self._stream_task: Optional[asyncio.Task] = None
        self._chunk_duration_ms = 30
        self._streaming_start_time: Optional[float] = None
        self._wake_word_energy_samples = []

        # Metrics
        self._last_transcript = ""
        self._stream_start_time: Optional[float] = None

    async def start(self):
        """Start the optimized streaming controller."""
        if self._is_running:
            logger.warning("Controller already running")
            return

        self._is_running = True
        
        logger.info(
            f"🎤 Streaming controller started. Listening for '{self.wake_word}'..."
        )

        # Start processing loop
        self._stream_task = asyncio.create_task(self._processing_loop())

    async def stop(self):
        """Stop the controller and cleanup."""
        self._is_running = False

        # Stop streaming if active
        if self._is_streaming:
            await self._stop_streaming()

        # Cancel tasks
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass

        logger.info("🛑 Streaming controller stopped")

    async def _processing_loop(self):
        """Main mic processing loop."""
        try:
            for chunk in self.mic_stream.stream():
                if not self._is_running:
                    self.mic_stream.stop()
                    break

                if self._is_streaming:
                    await self._handle_streaming_chunk(chunk)
                else:
                    await self._handle_listening_chunk(chunk)

                await asyncio.sleep(0)

        except Exception as e:
            logger.error(f"Processing loop error: {e}")
            self._is_running = False

    async def _on_server_message(self, data: dict):
        """Callback for non-audio messages from server (called by protocol handler)."""
        try:
            await self._handle_server_message(data)
        except Exception as e:
            logger.error(f"Error handling server message: {e}")

    async def _handle_server_message(self, data: dict):
        """Handle JSON message from server."""
        msg_type = data.get("type")

        if msg_type == "transcript":
            text = data.get("text", "")
            is_final = data.get("is_final", False)

            if text:
                self._last_transcript = text

                if is_final:
                    # Calculate latency
                    if self._stream_start_time:
                        latency = (time.time() - self._stream_start_time) * 1000
                        logger.info(f"📝 Final transcript ({latency:.0f}ms): '{text}'")
                    else:
                        logger.info(f"📝 Final: '{text}'")
                else:
                    logger.debug(f"📝 Interim: '{text}'")

        elif msg_type == "intent_detected":
            route = data.get("route", "unknown")
            logger.info(f"🎯 Intent: {route}")

        elif msg_type == "audio_input_stopped":
            logger.debug("Audio input stopped on server")

        elif msg_type == "response_complete":
            # Response generation complete
            self._is_playing_response = False
            logger.debug("Response complete")

        elif msg_type == "error":
            logger.error(f"❌ Server error: {data.get('message')}")

    async def _handle_listening_chunk(self, chunk: bytes):
        """Process audio while listening for wake word."""
        # Track energy for baseline
        rms = self.silence_detector._calculate_rms(chunk)
        self._wake_word_energy_samples.append(rms)

        # Keep recent samples only
        max_samples = int(2000 / self._chunk_duration_ms)
        if len(self._wake_word_energy_samples) > max_samples:
            self._wake_word_energy_samples.pop(0)

        # Check for wake word
        event = self.wake_word_detector.process_chunk(chunk)

        if event == WakeWordEvent.DETECTED:
            logger.info(f"🎤 Wake word '{self.wake_word}' detected!")

            # If currently playing response, interrupt it
            if self._is_playing_response:
                logger.info("⚠️ Interrupting current response")
                await self._send_interrupt()
                
                # Interrupt audio player directly
                if hasattr(self.protocol_handler, 'audio_player'):
                    await self.protocol_handler.audio_player.interrupt()
                
                self._is_playing_response = False

            await self._start_streaming()

    async def _handle_streaming_chunk(self, chunk: bytes):
        """
        Process audio while streaming.
        Send chunks immediately to backend for processing.
        """
        try:
            # Check timeout
            if self._streaming_start_time:
                elapsed = asyncio.get_event_loop().time() - self._streaming_start_time
                if elapsed >= self.listening_timeout_seconds:
                    logger.info(f"⏱️ Timeout ({self.listening_timeout_seconds}s)")
                    await self._stop_streaming()
                    return

            # Send chunk immediately to backend
            await self.ws_client.send_binary(chunk)

            # Check for silence to stop streaming
            event = self.silence_detector.process(chunk)
            if event == SpeechEvent.SPEECH_ENDED:
                logger.info("🤐 Silence detected")
                await self._stop_streaming()

        except Exception as e:
            logger.error(f"Error streaming chunk: {e}")
            await self._stop_streaming()

    async def _start_streaming(self):
        """Start streaming audio to server."""
        if self._is_streaming:
            logger.warning("Already streaming")
            return

        try:
            # Disable LED control in protocol handler - we're taking over during input
            if self.protocol_handler and hasattr(self.protocol_handler, 'set_led_control'):
                self.protocol_handler.set_led_control(False)
                logger.debug("LED control disabled in AudioStreamHandler during streaming")
            
            # Set baseline energy
            if self._wake_word_energy_samples and self.use_relative_silence:
                baseline = sum(self._wake_word_energy_samples) / len(
                    self._wake_word_energy_samples
                )
                self.silence_detector.set_baseline_energy(baseline)
                logger.debug(f"Baseline energy: {baseline:.1f} RMS")

            # Reset detectors
            self.silence_detector.reset()
            self.wake_word_detector.stop_listening()

            # Send start message
            control_msg = json.dumps(
                {
                    "type": "start_audio_input",
                    "config": {
                        "sample_rate": self.sample_rate,
                        "channels": self.channels,
                        "encoding": "linear16",
                        "language": "en-US",
                    },
                }
            )
            await self.ws_client.send_text(control_msg)

            # Update state
            self._is_streaming = True
            self._streaming_start_time = asyncio.get_event_loop().time()
            self._stream_start_time = time.time()

            logger.info(
                f"🔴 Streaming started (timeout: {self.listening_timeout_seconds}s)"
            )

            # Set LED to listening (blue spinning)
            if self.led_controller:
                await self.led_controller.set_listening()
                logger.info("💡 LED: Listening (blue spinning)")

        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            self._is_streaming = False

    async def _stop_streaming(self):
        """Stop streaming audio."""
        if not self._is_streaming:
            return

        try:
            # Update state
            self._is_streaming = False
            self._streaming_start_time = None

            # Send stop message
            control_msg = json.dumps({"type": "stop_audio_input"})
            await self.ws_client.send_text(control_msg)

            logger.info("⏹️ Streaming stopped")

            # Reset detectors
            self.silence_detector.reset()
            self.silence_detector.clear_baseline()
            self._wake_word_energy_samples = []
            self.wake_word_detector.start_listening()

            # Turn off LED immediately - waiting for response
            if self.led_controller:
                await self.led_controller.set_off()
                logger.info("💡 LED: Off (waiting for response)")
            
            # Re-enable LED control in protocol handler for response playback
            if self.protocol_handler and hasattr(self.protocol_handler, 'set_led_control'):
                self.protocol_handler.set_led_control(True)
                logger.debug("LED control re-enabled in AudioStreamHandler for response playback")

            logger.info(f"👂 Listening for '{self.wake_word}'...")

        except Exception as e:
            logger.error(f"Failed to stop streaming: {e}")

    async def _send_interrupt(self):
        """Send interrupt signal to server."""
        try:
            control_msg = json.dumps({"type": "interrupt"})
            await self.ws_client.send_text(control_msg)
            logger.info("⚠️ Interrupt sent")
        except Exception as e:
            logger.error(f"Failed to send interrupt: {e}")

    @property
    def is_streaming(self) -> bool:
        """Check if currently streaming audio."""
        return self._is_streaming

    @property
    def is_listening(self) -> bool:
        """Check if listening for wake word."""
        return self._is_running and not self._is_streaming
