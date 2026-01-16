"""
Streaming Speech-to-Text Service Module

This module provides real-time STT functionality using Deepgram's WebSocket API.
Optimized for low-latency voice interactions with interim results support.
"""

import logging
from typing import Optional, Dict, Any, Callable
import asyncio

from deepgram import DeepgramClient

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

        # Configure Deepgram client (v5.3.1 uses default config)
        self.client = DeepgramClient(api_key=self.api_key)

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

            # Store callbacks
            self.on_transcript_callback = on_transcript
            self.on_error_callback = on_error
            self.on_metadata_callback = on_metadata

            # Create live transcription connection using context manager
            # SDK v5.3.1 uses deepgram.listen.v1.connect() as context manager
            self.connection = self.client.listen.v1.connect(
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

            # Enter the context manager
            self.connection = self.connection.__enter__()

            # Register event handlers
            self.connection.on("open", self._on_open)
            self.connection.on("message", self._on_transcript)
            self.connection.on("metadata", self._on_metadata)
            self.connection.on("error", self._on_error)
            self.connection.on("close", self._on_close)
            self.connection.on("speech_started", self._on_speech_started)
            self.connection.on("utterance_end", self._on_utterance_end)

            # Start listening
            self.connection.start_listening()
            
            # Give it a moment to connect
            await asyncio.sleep(0.1)
            
            if True:
                raise StreamingSTTServiceError("Failed to start Deepgram connection")

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
            self.connection.send_media(audio_data)
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
        Sends finalize signal to get any remaining transcripts.
        """
        if not self.is_connected:
            logger.warning("No active stream to close")
            return

        try:
            if self.connection:
                # Finalize to get any remaining transcripts
                self.connection.send_finalize()
                # Exit context manager
                self.connection.__exit__(None, None, None)
                self.is_connected = False
                logger.info("Streaming STT connection closed")

        except Exception as e:
            logger.error(f"Error closing stream: {e}", exc_info=True)
        finally:
            self.is_connected = False
            self.connection = None

    def _on_open(self, *args, **kwargs):
        """Handle connection open event"""
        logger.info("Deepgram connection opened")

    def _on_transcript(self, *args, **kwargs):
        """Handle transcript event"""
        try:
            # In v5.3.1, message is passed differently
            message = args[0] if args else kwargs.get("message")
            if not message:
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
            metadata = {
                "is_final": result.is_final if hasattr(result, "is_final") else False,
                "speech_final": (
                    result.speech_final if hasattr(result, "speech_final") else False
                ),
                "confidence": (
                    alternative.confidence
                    if hasattr(alternative, "confidence")
                    else 0.0
                ),
                "duration": result.duration if hasattr(result, "duration") else 0.0,
                "start": result.start if hasattr(result, "start") else 0.0,
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
        error = kwargs.get("error", "Unknown error")
        error_msg = str(error)

        logger.error(f"Deepgram error: {error_msg}")

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
                await self.connection.keep_alive()
            except Exception as e:
                logger.error(f"Failed to send keepalive: {e}")
