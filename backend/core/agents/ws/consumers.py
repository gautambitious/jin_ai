"""
WebSocket consumer for audio streaming from edge devices.
"""

import asyncio
import json
import logging
import os
import struct
import uuid
from pathlib import Path
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import async_to_sync

from agents.ws.audio_generator import generate_tone_sequence, NOTES
from agents.ws.audio_chunker import chunk_audio
from agents.ws.audio_streamer import AudioStreamer
from agents.services.audio_websocket_helper import AudioWebSocketHelper
from agents.services.tts_service import TTSService
from agents.services.stt_service import STTService
from agents.services.websocket_tts_broadcaster import broadcast_tts_message
from agents.constants import AudioFormat
from agents.voice_router import VoiceRouter
from env_vars import DEEPGRAM_TTS_MODEL

logger = logging.getLogger(__name__)


def pcm_to_wav(
    pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2
) -> bytes:
    """
    Convert raw PCM audio data to WAV format.

    Args:
        pcm_data: Raw PCM audio bytes
        sample_rate: Sample rate in Hz (default: 16000)
        channels: Number of audio channels (default: 1 for mono)
        sample_width: Bytes per sample (default: 2 for 16-bit)

    Returns:
        bytes: WAV formatted audio data
    """
    # Calculate data size
    data_size = len(pcm_data)

    # Create WAV header
    header = struct.pack("<4sI4s", b"RIFF", data_size + 36, b"WAVE")

    # Format chunk
    fmt_chunk = struct.pack(
        "<4sIHHIIHH",
        b"fmt ",  # Chunk ID
        16,  # Chunk size
        1,  # Audio format (1 = PCM)
        channels,  # Number of channels
        sample_rate,  # Sample rate
        sample_rate * channels * sample_width,  # Byte rate
        channels * sample_width,  # Block align
        sample_width * 8,  # Bits per sample
    )

    # Data chunk
    data_chunk = struct.pack("<4sI", b"data", data_size)

    # Combine all parts
    return header + fmt_chunk + data_chunk + pcm_data


class AudioStreamConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling audio streams from edge devices.

    Handles connections at /ws/audio/
    Each connection is assigned a unique ID and added to the edge_devices group.
    """

    # Class-level cache for welcome message audio
    _welcome_audio_cache = None
    _welcome_audio_model = None

    async def connect(self):
        """
        Handle new WebSocket connection.

        - Assigns a unique connection_id
        - Adds connection to edge_devices group
        - Accepts the WebSocket connection
        - Plays a welcome tone sequence
        - Greets with voice message
        """
        # Generate unique connection ID
        self.connection_id = str(uuid.uuid4())
        self.group_name = "edge_devices"

        # Initialize STT-related attributes
        self.stt_service = None
        self.is_receiving_audio = False
        self.audio_buffer = []
        self.audio_config = {}

        # Initialize Voice Router for transcript processing
        self.voice_router = VoiceRouter()
        logger.info(
            f"[{self.connection_id}] Voice Router initialized for transcript routing"
        )

        # Add to edge_devices group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Accept the WebSocket connection
        await self.accept()

        logger.info(
            f"WebSocket connected: connection_id={self.connection_id}, "
            f"channel_name={self.channel_name}, group={self.group_name}"
        )

        # Play welcome tone sequence
        await self._play_welcome_tones()

        # Play welcome voice message
        await self.play_text_message(
            "Hello! Connection established. I'm ready to speak."
        )

    async def disconnect(self, code):
        """
        Handle WebSocket disconnection.

        - Removes connection from edge_devices group
        - Stops STT service if active
        - Logs disconnection

        Args:
            code: WebSocket close code
        """
        # Stop STT service if active
        if self.stt_service:
            try:
                self.stt_service.stop_transcription()
                logger.info(
                    f"Stopped STT service for connection_id={self.connection_id}"
                )
            except Exception as e:
                logger.error(f"Error stopping STT service: {e}", exc_info=True)

        # Remove from edge_devices group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

        logger.info(
            f"WebSocket disconnected: connection_id={self.connection_id}, "
            f"close_code={code}"
        )

    async def receive(self, text_data=None, bytes_data=None):
        """
        Handle incoming WebSocket messages.

        Supports commands:
        - {"type": "speak", "text": "..."} - Convert text to speech and play
        - {"type": "stop"} - Stop current audio playback
        - {"type": "audio_input_start", ...} - Start receiving audio for STT
        - {"type": "audio_input_end"} - Stop receiving audio

        Args:
            text_data: Text message data (JSON)
            bytes_data: Binary message data (audio chunks)
        """
        if text_data:
            try:
                data = json.loads(text_data)
                message_type = data.get("type")

                if message_type == "speak":
                    # Convert text to speech and play
                    text = data.get("text", "")
                    if text:
                        logger.info(f"Speaking text: {text[:50]}...")
                        await self.play_text_message(text)
                    else:
                        logger.warning("Received speak command with no text")

                elif message_type == "stop":
                    # Stop audio playback
                    logger.info("Stop playback requested")
                    helper = AudioWebSocketHelper(self)
                    await helper.stop_playback()

                elif message_type == "audio_input_start":
                    # Start receiving audio from edge device
                    await self._handle_audio_input_start(data)

                elif message_type == "audio_input_end":
                    # Stop receiving audio and finalize transcription
                    await self._handle_audio_input_end()

                else:
                    logger.warning(f"Unknown message type: {message_type}")

            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {text_data}")
            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)

        if bytes_data:
            # Handle binary audio chunks for STT
            if self.is_receiving_audio:
                await self._handle_audio_chunk(bytes_data)
            else:
                logger.debug(
                    f"Received binary data but not in audio input mode: {len(bytes_data)} bytes"
                )

    async def _play_welcome_tones(self):
        """
        Play a welcome message on successful connection using TTS.

        Converts a greeting text to speech and plays it.
        Uses cached audio from memory or filesystem if available and model hasn't changed.
        """
        try:
            current_model = DEEPGRAM_TTS_MODEL

            # Define cache directory and file path
            cache_dir = Path(__file__).parent.parent.parent / ".cache" / "audio"
            cache_file = cache_dir / f"welcome_{current_model.replace('/', '_')}.pcm"

            # Check if we need to load/generate audio
            if (
                AudioStreamConsumer._welcome_audio_cache is None
                or AudioStreamConsumer._welcome_audio_model != current_model
            ):
                # Try to load from filesystem first
                if cache_file.exists():
                    logger.info(f"Loading welcome audio from cache file: {cache_file}")
                    with open(cache_file, "rb") as f:
                        AudioStreamConsumer._welcome_audio_cache = f.read()
                    AudioStreamConsumer._welcome_audio_model = current_model
                    logger.info(
                        f"Welcome audio loaded from disk: {len(AudioStreamConsumer._welcome_audio_cache)} bytes"
                    )
                else:
                    # Generate new audio using TTS
                    logger.info(f"Generating welcome audio for model: {current_model}")

                    tts_service = TTSService()
                    audio_chunks = []

                    for chunk in tts_service.generate_audio(
                        text="Connected.",
                        encoding="linear16",
                        sample_rate=AudioFormat.DEFAULT_SAMPLE_RATE,
                    ):
                        audio_chunks.append(chunk)

                    # Cache the audio data and model
                    AudioStreamConsumer._welcome_audio_cache = b"".join(audio_chunks)
                    AudioStreamConsumer._welcome_audio_model = current_model

                    # Save to filesystem
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    with open(cache_file, "wb") as f:
                        f.write(AudioStreamConsumer._welcome_audio_cache)

                    logger.info(
                        f"Welcome audio cached: {len(AudioStreamConsumer._welcome_audio_cache)} bytes, saved to {cache_file}"
                    )
            else:
                logger.debug("Using in-memory cached welcome audio")

            # Stream the cached audio
            streamer = AudioStreamer(
                websocket=self,
                stream_id=f"welcome_{self.connection_id}",
                sample_rate=AudioFormat.DEFAULT_SAMPLE_RATE,
                channels=1,
            )

            # Stream the audio with chunking
            chunker = lambda data: chunk_audio(
                data, sample_rate=AudioFormat.DEFAULT_SAMPLE_RATE, chunk_duration_ms=20
            )
            await streamer.stream_audio_bytes(
                AudioStreamConsumer._welcome_audio_cache, chunker
            )

            logger.info(
                f"Welcome message played for connection_id={self.connection_id}"
            )

        except Exception as e:
            logger.error(f"Error playing welcome message: {e}", exc_info=True)

    async def play_text_message(self, text: str) -> None:
        """
        Convert text to speech and play it over WebSocket.

        Uses the AudioWebSocketHelper to handle the complete pipeline:
        text -> TTS -> audio streaming -> playback

        Args:
            text: Text message to convert to speech and play

        Example:
            >>> await self.play_text_message("Hello! Welcome to Jin AI.")
        """
        try:
            helper = AudioWebSocketHelper(
                websocket=self,
                sample_rate=AudioFormat.DEFAULT_SAMPLE_RATE,
                channels=1,
            )

            await helper.text_to_speech_stream(text)

            logger.info(f"Successfully played text message: {text[:50]}...")

        except Exception as e:
            logger.error(f"Error playing text message: {e}", exc_info=True)

    async def speak_message(self, event):
        """
        Handle speak_message event from channel layer.

        This is called when a message is broadcast via channel layer
        (e.g., from broadcast_tts_message or send_tts_to_channel).

        Args:
            event: Event dictionary with 'text' field
        """
        text = event.get("text", "")
        if text:
            await self.play_text_message(text)

    # ===== STT Audio Input Handlers =====

    async def _handle_audio_input_start(self, data: dict):
        """
        Handle audio_input_start message from edge device.

        Initializes STT service and starts transcription session.

        Args:
            data: Message data containing audio configuration
                - sample_rate: Audio sample rate (e.g., 16000)
                - channels: Number of audio channels (e.g., 1 for mono)
                - format: Audio format (e.g., "pcm_s16le")
        """
        try:
            # Extract audio configuration
            sample_rate = data.get("sample_rate", 16000)
            channels = data.get("channels", 1)
            audio_format = data.get("format", "pcm_s16le")

            self.audio_config = {
                "sample_rate": sample_rate,
                "channels": channels,
                "format": audio_format,
            }

            logger.info(
                f"[{self.connection_id}] Audio input started: "
                f"{sample_rate}Hz, {channels}ch, format={audio_format}"
            )

            # Initialize STT service
            self.stt_service = STTService()

            # Set flag to start accepting audio chunks
            self.is_receiving_audio = True
            self.audio_buffer = []

            logger.info(
                f"[{self.connection_id}] Ready to receive audio chunks for batch transcription"
            )

        except Exception as e:
            logger.error(
                f"[{self.connection_id}] Error starting audio input: {e}", exc_info=True
            )
            self.is_receiving_audio = False

    async def _handle_audio_chunk(self, audio_bytes: bytes):
        """
        Handle binary audio chunk from edge device.

        Buffers audio data for batch transcription when input ends.

        Args:
            audio_bytes: Raw audio data bytes
        """
        try:
            if not self.stt_service or not self.is_receiving_audio:
                logger.warning(
                    f"[{self.connection_id}] Received audio chunk but not ready"
                )
                return

            # Buffer audio for batch transcription
            self.audio_buffer.append(audio_bytes)

            logger.debug(
                f"[{self.connection_id}] Buffered audio chunk: {len(audio_bytes)} bytes "
                f"(total: {len(self.audio_buffer)} chunks)"
            )

        except Exception as e:
            logger.error(
                f"[{self.connection_id}] Error buffering audio chunk: {e}",
                exc_info=True,
            )

    async def _handle_audio_input_end(self):
        """
        Handle audio_input_end message from edge device.

        Transcribes all buffered audio and logs the result.
        """
        try:
            if not self.is_receiving_audio:
                logger.warning(
                    f"[{self.connection_id}] Received audio_input_end but not receiving audio"
                )
                return

            total_chunks = len(self.audio_buffer)
            total_bytes = sum(len(chunk) for chunk in self.audio_buffer)
            duration_seconds = total_bytes / (
                self.audio_config.get("sample_rate", 16000)
                * self.audio_config.get("channels", 1)
                * 2  # 2 bytes per sample for 16-bit audio
            )

            logger.info(
                f"[{self.connection_id}] Audio input ended: "
                f"{total_chunks} chunks, {total_bytes} bytes, "
                f"~{duration_seconds:.2f}s duration"
            )

            # Transcribe all buffered audio
            if self.stt_service and self.audio_buffer:
                try:
                    # Combine all audio chunks into one buffer
                    combined_audio = b"".join(self.audio_buffer)

                    logger.info(
                        f"[{self.connection_id}] Transcribing {len(combined_audio)} bytes of raw PCM audio..."
                    )

                    # Convert raw PCM to WAV format
                    sample_rate = self.audio_config.get("sample_rate", 16000)
                    channels = self.audio_config.get("channels", 1)
                    wav_audio = pcm_to_wav(
                        combined_audio, sample_rate=sample_rate, channels=channels
                    )

                    logger.info(
                        f"[{self.connection_id}] Converted to WAV: {len(wav_audio)} bytes"
                    )

                    # Transcribe using batch API
                    result = await asyncio.to_thread(
                        self.stt_service.transcribe_audio,
                        wav_audio,
                    )

                    # Log the transcript
                    transcript = result.get("transcript", "")
                    confidence = result.get("confidence", 0)

                    logger.info(
                        f"[{self.connection_id}] TRANSCRIPT: '{transcript}' "
                        f"(confidence: {confidence:.2%})"
                    )

                    # Process transcript through Voice Router
                    if transcript.strip():
                        try:
                            logger.info(
                                f"[{self.connection_id}] Routing transcript to Voice Router..."
                            )

                            # Prepare routing metadata
                            routing_metadata = {
                                "confidence": confidence,
                                "connection_id": self.connection_id,
                                "audio_duration_seconds": duration_seconds,
                            }

                            # Route transcript through Voice Router
                            response = await self.voice_router.process_transcript(
                                transcript=transcript,
                                session_id=self.connection_id,
                                metadata=routing_metadata,
                            )

                            # Extract response text
                            response_text = response.get("response", "")
                            routing_decision = response.get(
                                "routing_decision", "unknown"
                            )

                            logger.info(
                                f"[{self.connection_id}] Voice Router response "
                                f"(decision: {routing_decision}): '{response_text[:100]}...'"
                            )

                            # Broadcast response via TTS to all edge devices
                            if response_text:
                                logger.info(
                                    f"[{self.connection_id}] Broadcasting TTS response..."
                                )
                                await broadcast_tts_message(response_text)
                                logger.info(
                                    f"[{self.connection_id}] TTS broadcast complete"
                                )

                        except Exception as e:
                            logger.error(
                                f"[{self.connection_id}] Error routing transcript: {e}",
                                exc_info=True,
                            )

                except Exception as e:
                    logger.error(
                        f"[{self.connection_id}] Error transcribing audio: {e}",
                        exc_info=True,
                    )

            # Clean up
            self.stt_service = None
            self.is_receiving_audio = False

            logger.info(f"[{self.connection_id}] STT session finalized")

            # Clear buffer to free memory
            self.audio_buffer = []

        except Exception as e:
            logger.error(
                f"[{self.connection_id}] Error ending audio input: {e}", exc_info=True
            )
            self.is_receiving_audio = False
            if self.stt_service:
                try:
                    self.stt_service.stop_transcription()
                except:
                    pass
                self.stt_service = None
