"""
WebSocket consumer for audio streaming from edge devices.
"""

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from channels.generic.websocket import AsyncWebsocketConsumer

from agents.ws.audio_generator import generate_tone_sequence, NOTES
from agents.ws.audio_chunker import chunk_audio
from agents.ws.audio_streamer import AudioStreamer
from agents.services.audio_websocket_helper import AudioWebSocketHelper
from agents.services.tts_service import TTSService
from env_vars import DEEPGRAM_TTS_MODEL

logger = logging.getLogger(__name__)


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
        - Logs disconnection

        Args:
            code: WebSocket close code
        """
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

        Args:
            text_data: Text message data (JSON)
            bytes_data: Binary message data
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

                else:
                    logger.warning(f"Unknown message type: {message_type}")

            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {text_data}")
            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)

        if bytes_data:
            logger.debug(f"Received binary data: {len(bytes_data)} bytes")

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
                        sample_rate=16000,
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
                sample_rate=16000,
                channels=1,
            )

            # Stream the audio with chunking
            chunker = lambda data: chunk_audio(
                data, sample_rate=16000, chunk_duration_ms=20
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
                sample_rate=16000,
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
