"""
Wake-word-driven audio streaming controller.

Continuously listens for wake word, then streams mic audio until silence detected.
Clean state management prevents overlapping sessions.
"""

import asyncio
import json
import logging
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


class WakeWordStreamer:
    """
    Wake-word-driven audio streaming controller.

    Workflow:
        1. Continuously listen for wake word
        2. On wake word → send audio_input_start, start streaming
        3. Stream mic audio chunks to WebSocket
        4. On silence detected → send audio_input_end, stop streaming
        5. Return to listening for wake word

    Usage:
        streamer = WakeWordStreamer(
            ws_client=client,
            wake_word="hey jin",
            silence_threshold=500,
            silence_duration_ms=800
        )
        await streamer.start()
        # Runs until stopped
        await streamer.stop()

    Features:
        - Non-blocking async design
        - Prevents overlapping sessions
        - Clean state management
        - Integrates wake word + silence detection
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
    ):
        """
        Initialize wake word streamer.

        Args:
            ws_client: WebSocketClient instance for sending audio/messages
            wake_word: Wake word phrase (default: "hey jin")
            wake_word_detector: Optional custom wake word detector
            mic_stream: Optional MicStream instance (creates one if None)
            sample_rate: Audio sample rate in Hz (default: 16000)
            channels: Number of audio channels (default: 1 for mono)
            silence_threshold: RMS threshold for silence detection (used as fallback)
            silence_duration_ms: Milliseconds of silence before stopping (default: from env_vars)
            listening_timeout_seconds: Maximum seconds to listen after wake word (default: from env_vars)
            use_relative_silence: Use relative energy threshold based on wake word level (default: True)
            relative_silence_threshold: Ratio of wake word energy for silence threshold (default: from env_vars)
            led_controller: Optional LED controller for visual feedback
        """
        self.ws_client = ws_client
        self.wake_word = wake_word
        self.sample_rate = sample_rate
        self.channels = channels
        self.led_controller = led_controller

        # Get silence duration from env_vars if not provided
        if silence_duration_ms is None:
            silence_duration_ms = env_vars.SILENCE_DURATION_MS
        self.silence_duration_ms = silence_duration_ms

        # Get listening timeout from env_vars if not provided
        if listening_timeout_seconds is None:
            listening_timeout_seconds = env_vars.LISTENING_TIMEOUT_SECONDS
        self.listening_timeout_seconds = listening_timeout_seconds

        # Get relative silence settings from env_vars if not provided
        if use_relative_silence is None:
            use_relative_silence = True  # Enable by default
        self.use_relative_silence = use_relative_silence

        if relative_silence_threshold is None:
            relative_silence_threshold = env_vars.RELATIVE_SILENCE_THRESHOLD
        self.relative_silence_threshold = relative_silence_threshold

        # Create mic stream
        self.mic_stream = mic_stream or MicStream(
            sample_rate=sample_rate, channels=channels
        )

        # Create wake word detector (Porcupine if available, else stub)
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
                logger.info("Falling back to stub detector")
                from wakeword.stub_detector import StubWakeWordDetector

                self.wake_word_detector = StubWakeWordDetector(
                    wake_word=wake_word,
                    on_detection=None,
                )
        else:
            if HAS_PORCUPINE:
                logger.info("PORCUPINE_ACCESS_KEY not set, using stub detector")
            else:
                logger.info("Porcupine not installed, using stub detector")
            from wakeword.stub_detector import StubWakeWordDetector

            self.wake_word_detector = StubWakeWordDetector(
                wake_word=wake_word,
                on_detection=None,
            )

        # Create silence detector
        self.silence_detector = SilenceDetector(
            sample_rate=sample_rate,
            silence_threshold=silence_threshold,
            silence_duration_ms=silence_duration_ms,
            on_speech_start=None,  # We'll handle in process loop
            on_speech_end=None,
            use_relative_threshold=use_relative_silence,
            relative_threshold_ratio=relative_silence_threshold,
        )

        # State management
        self._is_running = False
        self._is_streaming = False
        self._stream_task: Optional[asyncio.Task] = None
        self._audio_buffer = []  # Buffer all chunks from wake word to silence
        self._chunk_duration_ms = 30  # Each chunk is ~30ms
        self._streaming_start_time: Optional[float] = None
        self._wake_word_energy_samples = []  # Store energy samples during wake word detection

    async def start(self):
        """
        Start the wake word streamer.
        Begins listening for wake word continuously.
        """
        if self._is_running:
            logger.warning("Streamer already running")
            return

        self._is_running = True
        logger.info(
            f"🎤 Wake word streamer started. Listening for '{self.wake_word}'..."
        )

        # Start main processing loop
        self._stream_task = asyncio.create_task(self._processing_loop())

    async def stop(self):
        """Stop the wake word streamer and cleanup."""
        self._is_running = False

        # Stop any active streaming
        if self._is_streaming:
            await self._stop_streaming()

        # Cancel processing task
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
            self._stream_task = None

        logger.info("🛑 Wake word streamer stopped")

    async def _processing_loop(self):
        """
        Main processing loop.
        Runs mic capture and handles wake word + silence detection.
        """
        try:
            # Run mic capture in executor to avoid blocking
            for chunk in self.mic_stream.stream():
                if not self._is_running:
                    self.mic_stream.stop()
                    break

                if self._is_streaming:
                    # Actively streaming mode
                    await self._handle_streaming_chunk(chunk)
                else:
                    # Listening for wake word mode
                    await self._handle_listening_chunk(chunk)

                # Yield control to event loop
                await asyncio.sleep(0)

        except Exception as e:
            logger.error(f"Processing loop error: {e}")
            self._is_running = False
        finally:
            logger.debug("Processing loop completed")

    async def _handle_listening_chunk(self, chunk: bytes):
        """
        Process audio chunk while listening for wake word.
        Tracks energy levels to establish baseline for relative silence detection.

        Args:
            chunk: PCM audio bytes
        """
        # Track energy levels during listening phase (for baseline)
        rms = self.silence_detector._calculate_rms(chunk)
        self._wake_word_energy_samples.append(rms)
        
        # Keep only recent samples (last 2 seconds worth)
        max_samples = int(2000 / self._chunk_duration_ms)
        if len(self._wake_word_energy_samples) > max_samples:
            self._wake_word_energy_samples.pop(0)

        # Check for wake word
        event = self.wake_word_detector.process_chunk(chunk)

        if event == WakeWordEvent.DETECTED:
            logger.info(f"🎤 Wake word '{self.wake_word}' detected!")
            await self._start_streaming()

    async def _handle_streaming_chunk(self, chunk: bytes):
        """
        Process audio chunk while actively streaming.
        Buffers chunks instead of sending immediately.
        Checks for timeout and silence conditions.

        Args:
            chunk: PCM audio bytes
        """
        try:
            # Buffer the audio chunk
            self._audio_buffer.append(chunk)

            # Check for hard timeout
            if self._streaming_start_time is not None:
                elapsed = asyncio.get_event_loop().time() - self._streaming_start_time
                if elapsed >= self.listening_timeout_seconds:
                    logger.info(
                        f"⏱️  Listening timeout reached ({self.listening_timeout_seconds}s), stopping"
                    )
                    await self._stop_streaming()
                    return

            # Check for silence
            event = self.silence_detector.process(chunk)

            if event == SpeechEvent.SPEECH_ENDED:
                logger.info("🤐 Silence detected, sending buffered audio")
                await self._stop_streaming()

        except Exception as e:
            logger.error(f"Error buffering chunk: {e}")
            await self._stop_streaming()

    async def _start_streaming(self):
        """Start buffering microphone audio."""
        if self._is_streaming:
            logger.warning("Already streaming, ignoring duplicate start")
            return

        try:
            # Calculate baseline energy from recent samples
            if self._wake_word_energy_samples and self.use_relative_silence:
                # Use average of recent energy levels as baseline
                baseline_energy = sum(self._wake_word_energy_samples) / len(
                    self._wake_word_energy_samples
                )
                self.silence_detector.set_baseline_energy(baseline_energy)
                logger.info(
                    f"Set baseline energy from wake word: {baseline_energy:.1f} RMS"
                )

            # Reset detectors
            self.silence_detector.reset()
            self.wake_word_detector.stop_listening()

            # Initialize audio buffer and start time
            self._audio_buffer = []
            self._streaming_start_time = asyncio.get_event_loop().time()

            # Update state
            self._is_streaming = True
            logger.info(
                f"🔴 Started buffering audio (timeout: {self.listening_timeout_seconds}s)"
            )

            # Set LED to listening state
            if self.led_controller:
                await self.led_controller.set_listening()

        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            self._is_streaming = False

    async def _stop_streaming(self):
        """Stop streaming and send buffered audio with silence trimmed."""
        if not self._is_streaming:
            return

        try:
            # Update state first
            self._is_streaming = False
            self._streaming_start_time = None

            # Calculate how many chunks to trim (silence duration)
            chunks_to_trim = int(self.silence_duration_ms / self._chunk_duration_ms)

            # Trim silence from the end of buffer
            audio_to_send = (
                self._audio_buffer[:-chunks_to_trim]
                if len(self._audio_buffer) > chunks_to_trim
                else self._audio_buffer
            )

            if audio_to_send:
                # Send audio_input_start control message
                control_msg = json.dumps(
                    {
                        "type": "audio_input_start",
                        "sample_rate": self.sample_rate,
                        "channels": self.channels,
                        "format": "pcm_s16le",
                    }
                )
                await self.ws_client.send_text(control_msg)
                logger.info("📤 Sent audio_input_start message")

                # Send all buffered audio chunks (without the silence at the end)
                total_chunks = len(audio_to_send)
                trimmed_chunks = len(self._audio_buffer) - len(audio_to_send)
                logger.info(
                    f"📤 Sending {total_chunks} chunks ({total_chunks * self._chunk_duration_ms}ms audio, trimmed {trimmed_chunks} chunks)"
                )

                for chunk in audio_to_send:
                    await self.ws_client.send_binary(chunk)

                # Send audio_input_end control message
                control_msg = json.dumps({"type": "audio_input_end"})
                await self.ws_client.send_text(control_msg)
                logger.info("📤 Sent audio_input_end message")
            else:
                logger.warning("No audio to send (buffer too short)")

            # Clear buffer
            self._audio_buffer = []

            # Reset detectors and resume wake word listening
            self.silence_detector.reset()
            self.silence_detector.clear_baseline()  # Clear baseline for next session
            self._wake_word_energy_samples = []  # Clear energy samples
            self.wake_word_detector.start_listening()
            
            # Turn off LED
            if self.led_controller:
                await self.led_controller.set_off()

            logger.info(f"⏹️  Stopped streaming. Listening for '{self.wake_word}'...")

        except Exception as e:
            logger.error(f"Failed to stop streaming: {e}")

    @property
    def is_streaming(self) -> bool:
        """Check if currently streaming audio."""
        return self._is_streaming

    @property
    def is_listening(self) -> bool:
        """Check if listening for wake word (not streaming)."""
        return self._is_running and not self._is_streaming


async def main():
    """
    Example usage of WakeWordStreamer.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create WebSocket client
    ws_url = "ws://localhost:8000/ws"
    ws_client = WebSocketClient(url=ws_url)

    # Connect to server
    await ws_client.connect()
    await asyncio.sleep(1)

    # Create wake word streamer
    streamer = WakeWordStreamer(
        ws_client=ws_client,
        wake_word="hey jin",
        silence_threshold=500,
        # silence_duration_ms will use env_vars.SILENCE_DURATION_MS (default 3000ms)
    )

    try:
        await streamer.start()

        # Run indefinitely (until Ctrl+C)
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await streamer.stop()
        await ws_client.close()


if __name__ == "__main__":
    asyncio.run(main())
