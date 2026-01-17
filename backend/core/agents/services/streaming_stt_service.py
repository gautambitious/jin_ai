"""
Streaming Speech-to-Text Service Module

This module provides real-time STT functionality using Deepgram's WebSocket API.
Optimized for low-latency voice interactions with interim results support.
"""

import logging
from typing import Optional, Dict, Any, Callable
import asyncio

from deepgram import AsyncDeepgramClient

from env_vars import DEEPGRAM_API_KEY, DEEPGRAM_STT_MODEL
from agents.constants import STTDefaults, ErrorMessages

logger = logging.getLogger(__name__)


class StreamingSTTServiceError(Exception):
    """Base exception for streaming STT service errors."""

    pass


class StreamingSTTService:
    """
    Real-time streaming Speech-to-Text service using Deepgram WebSocket API.

    Optimized for low-latency voice interactions with:
    - Interim transcript support
    - Immediate partial results
    - Minimal buffering
    - Early intent detection

    Example:
        >>> stt = StreamingSTTService()
        >>> await stt.start_stream(
        ...     on_transcript=lambda text, meta: print(text),
        ...     interim_results=True
        ... )
        >>> await stt.send_audio(audio_chunk)
        >>> await stt.close_stream()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize streaming STT service.

        Args:
            api_key: Deepgram API key. If None, uses env.DEEPGRAM_API_KEY
            model: STT model name. If None, uses env.DEEPGRAM_STT_MODEL

        Raises:
            StreamingSTTServiceError: If API key is not provided
        """
        self.api_key = api_key or DEEPGRAM_API_KEY
        if not self.api_key:
            raise StreamingSTTServiceError(ErrorMessages.API_KEY_MISSING)

        self.model = model or DEEPGRAM_STT_MODEL

        # Configure Deepgram async client (v5.3.1)
        self.client = AsyncDeepgramClient(api_key=self.api_key)

        # Connection state
        self.connection = None
        self.is_connected = False
        self.on_transcript_callback = None
        self.on_error_callback = None
        self.on_metadata_callback = None

        logger.info(f"StreamingSTTService initialized with model: {self.model}")

    async def start_stream(
        self,
        on_transcript: Callable[[str, Dict[str, Any]], None],
        on_error: Optional[Callable[[str], None]] = None,
        on_metadata: Optional[Callable[[Dict[str, Any]], None]] = None,
        language: str = STTDefaults.DEFAULT_LANGUAGE,
        smart_format: bool = True,
        punctuate: bool = True,
        interim_results: bool = True,
        encoding: str = "linear16",
        sample_rate: int = 16000,
        channels: int = 1,
        vad_events: bool = True,
        endpointing: int = 300,  # 300ms silence for utterance end
        **kwargs,
    ) -> bool:
        """
        Start a live streaming transcription session with Deepgram.

        Args:
            on_transcript: Callback(text: str, metadata: dict) for transcript results
            on_error: Optional callback(error_msg: str) for errors
            on_metadata: Optional callback(metadata: dict) for metadata events
            language: Language code (e.g., "en-US")
            smart_format: Enable smart formatting
            punctuate: Enable automatic punctuation
            interim_results: Enable interim (non-final) results for low latency
            encoding: Audio encoding (linear16, opus, etc.)
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
            vad_events: Enable voice activity detection events
            endpointing: Silence duration (ms) to consider utterance complete
            **kwargs: Additional LiveOptions parameters

        Returns:
            bool: True if connection established successfully

        Raises:
            StreamingSTTServiceError: If connection fails
        """
        try:
            if self.is_connected:
                raise StreamingSTTServiceError("Stream already active")

            # Validate API key format
            if not self.api_key or len(self.api_key) < 10:
                raise StreamingSTTServiceError(
                    "Invalid or missing DEEPGRAM_API_KEY. Check your .env file."
                )

            logger.info(
                f"Starting Deepgram connection: model={self.model}, "
                f"language={language}, sample_rate={sample_rate}Hz, "
                f"encoding={encoding}, API key={'*' * 8}{self.api_key[-4:]}"
            )

            # Store callbacks
            self.on_transcript_callback = on_transcript
            self.on_error_callback = on_error
            self.on_metadata_callback = on_metadata

            # SDK v5.3.1 uses async context manager pattern for websocket connections
            # The context manager returns an AsyncV1SocketClient that we use for the session
            # We'll store the context manager for later cleanup
            from deepgram.core.events import EventType

            self._connection_context = self.client.listen.v1.connect(
                model=self.model,
                language=language,
                smart_format=smart_format,
                punctuate=punctuate,
                interim_results=interim_results,
                encoding=encoding,
                sample_rate=sample_rate,
                channels=channels,
                vad_events=vad_events,
                endpointing=endpointing,
                **kwargs,
            )

            # Enter the async context manager to get the connection
            self.connection = await self._connection_context.__aenter__()
            logger.debug("Deepgram connection established")

            # Register event handlers using EventType enum
            # Available events: OPEN, MESSAGE, ERROR, CLOSE
            self.connection.on(EventType.OPEN, self._on_open)
            self.connection.on(EventType.MESSAGE, self._on_transcript)
            self.connection.on(EventType.ERROR, self._on_error)
            self.connection.on(EventType.CLOSE, self._on_close)
            logger.debug("Registered event handlers")

            # Start listening in a background task
            import asyncio

            self._listen_task = asyncio.create_task(self.connection.start_listening())
            logger.debug("Started listening task")

            # NOTE: Do NOT wait here! Deepgram expects audio within ~1 second.
            # The application must call send_audio() immediately after start_stream() returns.
            # If no audio is sent quickly, Deepgram will close with NET0001 timeout error.

            self.is_connected = True

            logger.info(
                f"Streaming STT started: model={self.model}, language={language}, "
                f"encoding={encoding}, sample_rate={sample_rate}, interim={interim_results}"
            )

            return True

        except Exception as e:
            error_msg = f"Failed to start streaming STT: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StreamingSTTServiceError(error_msg) from e

    async def send_audio(self, audio_data: bytes) -> bool:
        """
        Send audio data to the streaming transcription service.

        Args:
            audio_data: Raw audio bytes

        Returns:
            bool: True if sent successfully

        Raises:
            StreamingSTTServiceError: If no active connection
        """
        if not self.is_connected or not self.connection:
            raise StreamingSTTServiceError("No active streaming connection")

        try:
            # Check if websocket is still open
            if hasattr(self.connection, "_websocket") and hasattr(
                self.connection._websocket, "closed"
            ):
                if self.connection._websocket.closed:
                    self.is_connected = False
                    raise StreamingSTTServiceError("Deepgram websocket has closed")

            # SDK v5.3.1 send_media() accepts raw bytes directly
            await self.connection.send_media(audio_data)
            return True

        except Exception as e:
            error_msg = f"Failed to send audio: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if self.on_error_callback:
                self.on_error_callback(error_msg)
            raise StreamingSTTServiceError(error_msg) from e

    async def close_stream(self) -> None:
        """
        Close the streaming transcription session.
        Sends CloseStream message to force server to process remaining audio.
        """
        if not self.is_connected:
            logger.warning("No active stream to close")
            return

        try:
            self.is_connected = False

            if self.connection:
                try:
                    # Send CloseStream message to force server to process remaining audio
                    # and return final transcription results
                    await self.connection._send({"type": "CloseStream"})
                    logger.debug("Sent CloseStream message to Deepgram")

                    # Give server a moment to process and send final results
                    await asyncio.sleep(0.1)
                except Exception as close_error:
                    # Non-critical - log but continue with cleanup
                    logger.debug(f"Could not send CloseStream: {close_error}")

                # Cancel the listening task
                if hasattr(self, "_listen_task") and self._listen_task:
                    self._listen_task.cancel()
                    try:
                        await self._listen_task
                    except asyncio.CancelledError:
                        pass
                    logger.debug("Cancelled listening task")

                # Exit the async context manager - this closes the websocket properly
                if hasattr(self, "_connection_context") and self._connection_context:
                    try:
                        await self._connection_context.__aexit__(None, None, None)
                        logger.debug("Exited Deepgram connection context")
                    except Exception as exit_error:
                        logger.debug(f"Error exiting context manager: {exit_error}")

                logger.info("Streaming STT connection closed")

        except Exception as e:
            logger.error(f"Error closing stream: {e}", exc_info=True)
        finally:
            self.is_connected = False
            self.connection = None
            self._connection_context = None
            self._listen_task = None

    def _on_open(self, *args, **kwargs):
        """Handle connection open event"""
        logger.info("Deepgram connection opened")

    def _on_transcript(self, *args, **kwargs):
        """Handle transcript event"""
        try:
            # In v5.3.1, message is passed differently
            message = args[0] if args else kwargs.get("message")

            if not message:
                logger.warning("Received empty message from Deepgram")
                return

            # Check if it's a transcript message
            msg_type = getattr(message, "type", None)

            if msg_type != "Results":
                return

            # Extract transcript data
            channel = getattr(message, "channel", None)
            if not channel:
                return

            alternatives = getattr(channel, "alternatives", [])
            if not alternatives:
                return

            alternative = alternatives[0]
            transcript = getattr(alternative, "transcript", "")

            # Skip empty transcripts
            if not transcript or not transcript.strip():
                return

            # Build metadata
            is_final = message.is_final if hasattr(message, "is_final") else False
            speech_final = (
                message.speech_final if hasattr(message, "speech_final") else False
            )
            confidence = (
                alternative.confidence if hasattr(alternative, "confidence") else 0.0
            )

            metadata = {
                "is_final": is_final,
                "speech_final": speech_final,
                "confidence": confidence,
                "duration": message.duration if hasattr(message, "duration") else 0.0,
                "start": message.start if hasattr(message, "start") else 0.0,
            }

            # Add word-level data if available
            if hasattr(alternative, "words") and alternative.words:
                metadata["words"] = [
                    {
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "confidence": word.confidence,
                    }
                    for word in alternative.words
                ]

            # Log transcript with key info only
            final_indicator = "FINAL" if is_final else "interim"
            logger.info(
                f"TRANSCRIPT ({final_indicator}): '{transcript}' (confidence: {confidence:.2%})"
            )

            # Call transcript callback
            if self.on_transcript_callback:
                self.on_transcript_callback(transcript, metadata)

            # Log based on result type
            if metadata["is_final"]:
                logger.info(
                    f"Final transcript: '{transcript}' (confidence: {metadata['confidence']:.2f})"
                )
            else:
                logger.debug(f"Interim transcript: '{transcript}'")

        except Exception as e:
            logger.error(f"Error processing transcript: {e}", exc_info=True)

    def _on_metadata(self, *args, **kwargs):
        """Handle metadata event"""
        try:
            metadata = kwargs.get("metadata", {})

            if self.on_metadata_callback:
                self.on_metadata_callback(metadata)

            logger.debug(f"Metadata received: {metadata}")

        except Exception as e:
            logger.error(f"Error processing metadata: {e}", exc_info=True)

    def _on_error(self, *args, **kwargs):
        """Handle error event"""
        error = kwargs.get("error", args[0] if args else "Unknown error")
        error_msg = str(error)

        logger.error(f"Deepgram error: {error_msg}")
        logger.error(f"Error details - args: {args}, kwargs: {kwargs}")

        # Check if it's a connection close error
        if "1011" in error_msg or "internal error" in error_msg.lower():
            logger.error(
                "Connection closed with code 1011 (internal error). "
                "This usually indicates: invalid API key, model not available, "
                "invalid audio parameters, or account billing issue. "
                f"Current model: '{self.model}', API key ends with: ...{self.api_key[-4:]}"
            )

        if self.on_error_callback:
            self.on_error_callback(error_msg)

    def _on_close(self, *args, **kwargs):
        """Handle connection close event"""
        logger.info("Deepgram connection closed")
        self.is_connected = False

    def _on_speech_started(self, *args, **kwargs):
        """Handle speech started event"""
        logger.debug("Speech started detected")

    def _on_utterance_end(self, *args, **kwargs):
        """Handle utterance end event"""
        logger.debug("Utterance end detected")

    async def send_keepalive(self) -> None:
        """Send keepalive to maintain connection"""
        if self.connection and self.is_connected:
            try:
                from deepgram.listen.v1.types import ListenV1KeepAlive

                self.connection.send_keep_alive(ListenV1KeepAlive(type="KeepAlive"))
                logger.debug("Sent keepalive")
            except Exception as e:
                logger.error(f"Failed to send keepalive: {e}")
