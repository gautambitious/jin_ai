"""
WebSocket Consumer for Real-time Speech-to-Text

This module provides a WebSocket consumer that receives audio chunks
from clients (e.g., mobile apps, web apps) and transcribes them in real-time
using Deepgram's STT service.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from agents.services.stt_service import STTService

logger = logging.getLogger(__name__)


class STTConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time speech-to-text transcription.

    This consumer:
    1. Accepts WebSocket connections from clients
    2. Receives audio chunks via WebSocket
    3. Sends audio to Deepgram STT service
    4. Streams transcript results back to client in real-time

    Message Protocol:

    Client -> Server:
    - Binary messages: Raw audio data chunks
    - Text messages: Control commands (JSON)
      {
        "type": "start",
        "config": {
          "language": "en-US",
          "encoding": "linear16",
          "sample_rate": 24000
        }
      }
      {
        "type": "stop"
      }

    Server -> Client:
    - Text messages: Transcript results (JSON)
      {
        "type": "transcript",
        "text": "Hello world",
        "is_final": true,
        "confidence": 0.98
      }
      {
        "type": "error",
        "message": "Error message"
      }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stt_service = None
        self.session_id = None

    async def connect(self):
        """Handle WebSocket connection"""
        self.session_id = self.scope["url_route"]["kwargs"].get("session_id", "unknown")
        await self.accept()

        logger.info(f"STT WebSocket connected: session={self.session_id}")

        await self.send(
            text_data=json.dumps(
                {
                    "type": "connected",
                    "session_id": self.session_id,
                    "message": "Ready to receive audio",
                }
            )
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        logger.info(
            f"STT WebSocket disconnected: session={self.session_id}, code={close_code}"
        )

        # Clean up STT service
        if self.stt_service:
            await sync_to_async(self.stt_service.stop_transcription)()

    async def receive(self, text_data=None, bytes_data=None):
        """
        Handle incoming messages from client.

        Args:
            text_data: JSON control messages
            bytes_data: Raw audio chunks
        """
        try:
            # Handle text/JSON control messages
            if text_data:
                await self._handle_control_message(text_data)

            # Handle binary audio data
            elif bytes_data:
                await self._handle_audio_chunk(bytes_data)

        except Exception as e:
            logger.error(f"Error in STT receive: {str(e)}", exc_info=True)
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    async def _handle_control_message(self, text_data):
        """Handle control messages (start, stop, config)"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "start":
                await self._start_transcription(data.get("config", {}))

            elif message_type == "stop":
                await self._stop_transcription()

            elif message_type == "keepalive":
                if self.stt_service:
                    await sync_to_async(self.stt_service.send_keepalive)()

            else:
                logger.warning(f"Unknown control message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in control message: {str(e)}")
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Invalid JSON format"}
                )
            )

    async def _start_transcription(self, config):
        """Start STT transcription with given configuration"""
        try:
            # Create STT service if not exists
            if not self.stt_service:
                self.stt_service = await sync_to_async(STTService)()

            # Extract configuration
            language = config.get("language", "en-US")
            encoding = config.get("encoding", "linear16")
            sample_rate = config.get("sample_rate", 24000)
            channels = config.get("channels", 1)
            smart_format = config.get("smart_format", True)
            interim_results = config.get("interim_results", True)

            # Define transcript callback
            def on_transcript(text, metadata):
                """Send transcript to client"""
                # Note: This runs in a thread, need to use async_to_sync
                from asgiref.sync import async_to_sync

                async_to_sync(self.send)(
                    text_data=json.dumps(
                        {
                            "type": "transcript",
                            "text": text,
                            "is_final": metadata.get("is_final", False),
                            "speech_final": metadata.get("speech_final", False),
                            "confidence": metadata.get("confidence", 0),
                            "duration": metadata.get("duration", 0),
                            "words": metadata.get("words", []),
                        }
                    )
                )

            def on_error(error_message):
                """Send error to client"""
                from asgiref.sync import async_to_sync

                logger.error(f"STT error: {error_message}")
                async_to_sync(self.send)(
                    text_data=json.dumps({"type": "error", "message": error_message})
                )

            # Start transcription
            success = await sync_to_async(self.stt_service.start_transcription)(
                on_transcript=on_transcript,
                on_error=on_error,
                language=language,
                encoding=encoding,
                sample_rate=sample_rate,
                channels=channels,
                smart_format=smart_format,
                interim_results=interim_results,
            )

            if success:
                logger.info(
                    f"STT started: language={language}, encoding={encoding}, rate={sample_rate}"
                )
                await self.send(
                    text_data=json.dumps({"type": "started", "config": config})
                )
            else:
                raise Exception("Failed to start STT service")

        except Exception as e:
            logger.error(f"Error starting transcription: {str(e)}", exc_info=True)
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "message": f"Failed to start transcription: {str(e)}",
                    }
                )
            )

    async def _stop_transcription(self):
        """Stop STT transcription"""
        try:
            if self.stt_service:
                await sync_to_async(self.stt_service.finalize)()
                await sync_to_async(self.stt_service.stop_transcription)()

                await self.send(
                    text_data=json.dumps(
                        {"type": "stopped", "message": "Transcription stopped"}
                    )
                )

                logger.info("STT transcription stopped")

        except Exception as e:
            logger.error(f"Error stopping transcription: {str(e)}", exc_info=True)

    async def _handle_audio_chunk(self, bytes_data):
        """Handle incoming audio chunk"""
        if not self.stt_service or not self.stt_service.is_connected:
            logger.warning("Received audio but STT service not started")
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "message": "Transcription not started. Send 'start' message first.",
                    }
                )
            )
            return

        try:
            # Send audio chunk to STT service
            await sync_to_async(self.stt_service.send_audio)(bytes_data)
            logger.debug(f"Sent {len(bytes_data)} bytes to STT")

        except Exception as e:
            logger.error(f"Error sending audio to STT: {str(e)}", exc_info=True)
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": f"Error processing audio: {str(e)}"}
                )
            )
