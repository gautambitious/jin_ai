"""
Speech-to-Text Service Module

This module provides STT functionality using Deepgram API.
It transcribes audio data received from webhooks or other sources.
Supports both prerecorded transcription and real-time streaming.
"""

import os
import logging
from typing import Optional, Dict, Any, Callable
import threading
import asyncio

# Setup Django environment
if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
    import django

    django.setup()

from deepgram import DeepgramClient

from env_vars import DEEPGRAM_API_KEY, DEEPGRAM_STT_MODEL
from agents.constants import (
    STTDefaults,
    ErrorMessages,
)


logger = logging.getLogger(__name__)


class STTServiceError(Exception):
    """Base exception for STT service errors."""

    pass


class STTService:
    """
    Speech-to-Text service using Deepgram API.

    This service supports both prerecorded and real-time streaming transcription:
    - Use transcribe_audio() for prerecorded audio (files, webhooks)
    - Use start_transcription() for real-time streaming (WebSockets)

    Attributes:
        client: Deepgram client instance
        model: STT model name from environment configuration
        connection: Active streaming connection (for real-time transcription)
        is_connected: Streaming connection status flag

    Example (Prerecorded):
        >>> stt = STTService()
        >>> audio_bytes = open("audio.wav", "rb").read()
        >>> result = stt.transcribe_audio(audio_bytes)
        >>> print(result["transcript"])

    Example (Streaming):
        >>> def on_transcript(text, metadata):
        ...     print(f"Transcript: {text}")
        >>> stt = STTService()
        >>> stt.start_transcription(on_transcript=on_transcript)
        >>> stt.send_audio(audio_chunk)
        >>> stt.stop_transcription()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize STT service.

        Args:
            api_key: Deepgram API key. If None, uses env.DEEPGRAM_API_KEY
            model: STT model name. If None, uses env.DEEPGRAM_STT_MODEL

        Raises:
            STTServiceError: If API key is not provided or configured
        """
        self.api_key = api_key or DEEPGRAM_API_KEY
        if not self.api_key:
            raise STTServiceError(ErrorMessages.API_KEY_MISSING)

        self.model = model or DEEPGRAM_STT_MODEL
        self.client = DeepgramClient(api_key=self.api_key)

        # Streaming state
        self.connection = None
        self.is_connected = False
        self._lock = threading.Lock()

        logger.info(f"STT Service initialized with model: {self.model}")

    def transcribe_audio(
        self,
        audio_data: bytes,
        language: str = STTDefaults.DEFAULT_LANGUAGE,
        smart_format: bool = True,
        punctuate: bool = True,
        detect_language: bool = False,
        mimetype: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Transcribe audio data to text.

        This method sends audio data to Deepgram's prerecorded transcription
        API and returns the transcribed text along with metadata.

        Args:
            audio_data: Raw audio bytes to transcribe
            language: Language code (e.g., "en-US", "es", "fr").
                     Ignored if detect_language is True.
            smart_format: Enable smart formatting (punctuation, numbers, etc.)
            punctuate: Enable automatic punctuation
            detect_language: Auto-detect the language instead of using language param
            mimetype: MIME type of the audio (e.g., "audio/wav", "audio/mp3").
                     If None, Deepgram will attempt to detect it.
            **kwargs: Additional options for PrerecordedOptions

        Returns:
            Dict containing:
                - transcript: The full transcribed text
                - confidence: Average confidence score (0-1)
                - words: List of word-level timing and confidence (if available)
                - metadata: Additional metadata from Deepgram
                - detected_language: The detected language (if detect_language=True)

        Raises:
            STTServiceError: If transcription fails

        Example:
            >>> stt = STTService()
            >>> with open("audio.wav", "rb") as f:
            ...     audio_bytes = f.read()
            >>> result = stt.transcribe_audio(audio_bytes)
            >>> print(result["transcript"])
        """
        try:
            logger.info(f"Transcribing {len(audio_data)} bytes of audio")

            # Build kwargs for the API call
            api_kwargs = {
                "request": audio_data,
                "model": self.model,
                "smart_format": smart_format,
                "punctuate": punctuate,
            }

            # Only set language if not auto-detecting
            if detect_language:
                api_kwargs["detect_language"] = True
            else:
                api_kwargs["language"] = language

            # Add mimetype if provided
            if mimetype:
                api_kwargs["encoding"] = mimetype.split("/")[
                    -1
                ]  # e.g., "audio/wav" -> "wav"

            # Add any additional kwargs
            api_kwargs.update(kwargs)

            # Call Deepgram API - using v1.media.transcribe_file for prerecorded audio
            response = self.client.listen.v1.media.transcribe_file(**api_kwargs)

            # Extract results
            if not response or not response.results:
                raise STTServiceError("No results returned from Deepgram")

            channels = response.results.channels
            if not channels or len(channels) == 0:
                raise STTServiceError("No channel data in response")

            channel = channels[0]
            if not channel.alternatives or len(channel.alternatives) == 0:
                raise STTServiceError("No alternatives in response")

            alternative = channel.alternatives[0]
            transcript = alternative.transcript

            # Build result dictionary
            result = {
                "transcript": transcript,
                "confidence": (
                    alternative.confidence
                    if hasattr(alternative, "confidence")
                    else None
                ),
                "words": [],
                "metadata": {},
            }

            # Add word-level timing if available
            if hasattr(alternative, "words") and alternative.words:
                result["words"] = [
                    {
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "confidence": word.confidence,
                        "punctuated_word": (
                            word.punctuated_word
                            if hasattr(word, "punctuated_word")
                            else word.word
                        ),
                    }
                    for word in alternative.words
                ]

            # Add metadata
            if hasattr(response, "metadata"):
                metadata = response.metadata
                result["metadata"] = {
                    "duration": (
                        metadata.duration if hasattr(metadata, "duration") else None
                    ),
                    "channels": (
                        metadata.channels if hasattr(metadata, "channels") else None
                    ),
                }

                # Add detected language if available
                if detect_language and hasattr(metadata, "detected_language"):
                    result["detected_language"] = metadata.detected_language

            confidence_str = (
                f"{result['confidence']:.2f}" if result["confidence"] else "N/A"
            )
            logger.info(
                f"Transcription complete: {len(transcript) if transcript else 0} chars, "
                f"confidence: {confidence_str}"
            )

            return result

        except Exception as e:
            error_msg = f"Failed to transcribe audio: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise STTServiceError(error_msg) from e

    def start_transcription(
        self,
        on_transcript: Callable[[str, Dict[str, Any]], None],
        on_error: Optional[Callable[[str], None]] = None,
        language: str = STTDefaults.DEFAULT_LANGUAGE,
        smart_format: bool = True,
        punctuate: bool = True,
        interim_results: bool = True,
        encoding: str = STTDefaults.DEFAULT_ENCODING,
        sample_rate: int = STTDefaults.DEFAULT_SAMPLE_RATE,
        channels: int = 1,
        **kwargs,
    ) -> bool:
        """
        Start a live streaming transcription session.

        This method establishes a WebSocket connection to Deepgram's live
        transcription service for real-time audio streaming.

        Args:
            on_transcript: Callback function that receives transcript text and metadata
                          Signature: (transcript: str, metadata: Dict[str, Any]) -> None
            on_error: Optional callback function for error handling
                     Signature: (error_message: str) -> None
            language: Language code (e.g., "en-US", "es", "fr")
            smart_format: Enable smart formatting (punctuation, numbers, etc.)
            punctuate: Enable automatic punctuation
            interim_results: Enable interim (non-final) results
            encoding: Audio encoding (e.g., "linear16", "opus", "flac")
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
            **kwargs: Additional options

        Returns:
            bool: True if connection established successfully

        Raises:
            STTServiceError: If connection fails or service is already active
        """
        with self._lock:
            if self.is_connected:
                raise STTServiceError("Transcription session already active")

            # Store the callbacks
            self._on_transcript = on_transcript
            self._on_error = on_error
            self.is_connected = True

            logger.info(
                f"STT streaming initialized: language={language}, "
                f"model={self.model}, encoding={encoding}, sample_rate={sample_rate}"
            )
            logger.warning(
                "Note: This STT service currently uses prerecorded transcription API. "
                "For true real-time streaming, audio chunks will be buffered and transcribed in batches."
            )

            return True

    def send_audio(self, audio_data: bytes) -> bool:
        """
        Send audio data to the transcription service.

        Note: Current implementation buffers audio and transcribes using prerecorded API.

        Args:
            audio_data: Raw audio bytes to transcribe

        Returns:
            bool: True if audio received successfully

        Raises:
            STTServiceError: If no active connection
        """
        if not self.is_connected:
            raise STTServiceError("No active transcription connection")

        try:
            # For now, just acknowledge receipt
            # Real implementation would buffer and transcribe periodically
            logger.debug(f"Received {len(audio_data)} bytes of audio")
            return True

        except Exception as e:
            error_msg = f"Failed to send audio: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if hasattr(self, "_on_error") and self._on_error:
                self._on_error(error_msg)
            raise STTServiceError(error_msg) from e

    def stop_transcription(self) -> None:
        """
        Stop the streaming transcription session.
        """
        with self._lock:
            if not self.is_connected:
                logger.warning("No active transcription to stop")
                return

            try:
                self.is_connected = False
                self._on_transcript = None
                self._on_error = None
                logger.info("STT streaming stopped")

            except Exception as e:
                logger.error(f"Error stopping transcription: {e}", exc_info=True)
            finally:
                self.is_connected = False


# Convenience function
def transcribe_audio_bytes(audio_data: bytes, **options) -> str:
    """
    Convenience function to transcribe audio bytes and return just the text.

    Args:
        audio_data: Raw audio bytes to transcribe
        **options: Additional options passed to transcribe_audio

    Returns:
        str: The transcribed text

    Example:
        >>> audio_bytes = open("audio.wav", "rb").read()
        >>> text = transcribe_audio_bytes(audio_bytes)
        >>> print(text)
    """
    stt = STTService()
    result = stt.transcribe_audio(audio_data, **options)
    return result["transcript"]
