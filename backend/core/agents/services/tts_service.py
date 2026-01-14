"""
Text-to-Speech Service Module

This module provides TTS functionality using Deepgram API.
It generates audio from text input that can be streamed over WebSocket
to devices like Raspberry Pi.
"""

import os
import logging
from typing import Generator, Optional

# Setup Django environment
if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
    import django

    django.setup()

from deepgram import DeepgramClient

from env_vars import DEEPGRAM_API_KEY, DEEPGRAM_TTS_MODEL
from agents.constants import (
    AudioFormat,
    TTSDefaults,
    ErrorMessages,
)


logger = logging.getLogger(__name__)


class TTSServiceError(Exception):
    """Base exception for TTS service errors."""

    pass


class TTSService:
    """
    Text-to-Speech service using Deepgram API.

    This service converts text to audio using Deepgram's TTS API and returns
    audio data suitable for streaming over WebSocket to Raspberry Pi or other devices.

    Attributes:
        client: Deepgram client instance
        model: TTS model name from environment configuration

    Example:
        >>> tts = TTSService()
        >>> audio_chunks = tts.generate_audio("Hello, world!")
        >>> for chunk in audio_chunks:
        ...     # Stream chunk over WebSocket
        ...     websocket.send(chunk)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize TTS service.

        Args:
            api_key: Deepgram API key. If None, uses env.DEEPGRAM_API_KEY
            model: TTS model name. If None, uses env.DEEPGRAM_TTS_MODEL

        Raises:
            TTSServiceError: If API key is not provided or configured
        """
        self.api_key = api_key or DEEPGRAM_API_KEY
        if not self.api_key:
            raise TTSServiceError(ErrorMessages.API_KEY_MISSING)

        self.model = model or DEEPGRAM_TTS_MODEL
        self.client = DeepgramClient(api_key=self.api_key)

        logger.info(f"TTS Service initialized with model: {self.model}")

    def _validate_text(self, text: str) -> None:
        """
        Validate input text.

        Args:
            text: Input text to validate

        Raises:
            TTSServiceError: If text is invalid
        """
        if not text or not text.strip():
            raise TTSServiceError(ErrorMessages.EMPTY_TEXT)

        if len(text) > TTSDefaults.MAX_TEXT_LENGTH:
            raise TTSServiceError(ErrorMessages.TEXT_TOO_LONG)

    def generate_audio(
        self,
        text: str,
        output_format: str = AudioFormat.DEFAULT_STREAMING_FORMAT,
        encoding: Optional[str] = None,
        sample_rate: Optional[int] = None,
    ) -> Generator[bytes, None, None]:
        """
        Generate audio from text.

        This method generates audio chunks from the input text using Deepgram's TTS API.
        The audio is returned as a generator that yields chunks suitable for streaming.

        Args:
            text: Text to convert to speech
            output_format: Audio format (opus, wav, mp3, flac).
                          Default is opus for optimal WebSocket streaming
            encoding: Audio encoding (optional, usually inferred from format)
            sample_rate: Sample rate in Hz (optional, uses service default)

        Returns:
            Generator yielding audio data chunks as bytes

        Raises:
            TTSServiceError: If audio generation fails or input is invalid

        Example:
            >>> tts = TTSService()
            >>> audio_gen = tts.generate_audio(
            ...     "Hello from Jin!",
            ...     output_format="opus"
            ... )
            >>> for chunk in audio_gen:
            ...     websocket.send(chunk)
        """
        try:
            # Validate input
            self._validate_text(text)

            logger.info(
                f"Generating audio for text (length: {len(text)}, "
                f"format: {output_format}, model: {self.model})"
            )

            # Prepare options for Deepgram API
            options = {
                "model": self.model,
            }

            # Add optional parameters
            if encoding:
                options["encoding"] = encoding
            if sample_rate:
                options["sample_rate"] = str(sample_rate)

            # Generate audio using Deepgram API
            # Note: The speak API returns an iterable that yields chunks
            audio_response = self.client.speak.v1.audio.generate(text=text, **options)

            # Yield audio chunks for streaming
            chunk_count = 0
            total_bytes = 0

            for chunk in audio_response:
                if chunk:
                    chunk_count += 1
                    total_bytes += len(chunk)
                    yield chunk

            logger.info(
                f"Audio generation complete: {chunk_count} chunks, "
                f"{total_bytes} bytes total"
            )

        except TTSServiceError:
            # Re-raise our own exceptions
            raise
        except Exception as e:
            # Wrap other exceptions
            error_msg = f"{ErrorMessages.AUDIO_GENERATION_FAILED}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise TTSServiceError(error_msg) from e

    def generate_audio_to_file(
        self,
        text: str,
        output_path: str,
        output_format: str = AudioFormat.WAV,
        encoding: Optional[str] = None,
        sample_rate: Optional[int] = None,
    ) -> str:
        """
        Generate audio and save to a file.

        This is a convenience method for saving audio directly to a file
        instead of streaming.

        Args:
            text: Text to convert to speech
            output_path: Path where audio file will be saved
            output_format: Audio format (opus, wav, mp3, flac)
            encoding: Audio encoding (optional)
            sample_rate: Sample rate in Hz (optional)

        Returns:
            Path to the saved audio file

        Raises:
            TTSServiceError: If audio generation or file writing fails

        Example:
            >>> tts = TTSService()
            >>> file_path = tts.generate_audio_to_file(
            ...     "Hello from Jin!",
            ...     "/tmp/greeting.wav",
            ...     output_format="wav"
            ... )
            >>> print(f"Audio saved to: {file_path}")
        """
        try:
            logger.info(f"Generating audio to file: {output_path}")

            with open(output_path, "wb") as f:
                for chunk in self.generate_audio(
                    text=text,
                    output_format=output_format,
                    encoding=encoding,
                    sample_rate=sample_rate,
                ):
                    f.write(chunk)

            logger.info(f"Audio successfully saved to: {output_path}")
            return output_path

        except IOError as e:
            error_msg = f"Failed to write audio file: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise TTSServiceError(error_msg) from e

    def get_model_info(self) -> dict:
        """
        Get information about the current TTS model configuration.

        Returns:
            Dictionary containing model information
        """
        return {
            "model": self.model,
            "api_configured": bool(self.api_key),
            "default_format": AudioFormat.DEFAULT_STREAMING_FORMAT,
            "default_sample_rate": AudioFormat.DEFAULT_SAMPLE_RATE,
            "max_text_length": TTSDefaults.MAX_TEXT_LENGTH,
        }


# Convenience functions for simple use cases
def text_to_audio(
    text: str,
    output_format: str = AudioFormat.DEFAULT_STREAMING_FORMAT,
) -> Generator[bytes, None, None]:
    """
    Quick function to convert text to audio chunks.

    This is a convenience function that creates a TTSService instance
    and generates audio in one call.

    Args:
        text: Text to convert to speech
        output_format: Audio format for output

    Returns:
        Generator yielding audio data chunks

    Example:
        >>> for chunk in text_to_audio("Hello, world!"):
        ...     websocket.send(chunk)
    """
    service = TTSService()
    return service.generate_audio(text, output_format=output_format)


def text_to_audio_file(
    text: str,
    output_path: str,
    output_format: str = AudioFormat.WAV,
) -> str:
    """
    Quick function to convert text to audio and save to file.

    This is a convenience function that creates a TTSService instance
    and saves the audio to a file in one call.

    Args:
        text: Text to convert to speech
        output_path: Path where audio file will be saved
        output_format: Audio format (opus, wav, mp3, flac)

    Returns:
        Path to the saved audio file

    Example:
        >>> file_path = text_to_audio_file(
        ...     "Hello, world!",
        ...     "output.wav",
        ...     output_format="wav"
        ... )
        >>> print(f"Saved to: {file_path}")
    """
    service = TTSService()
    return service.generate_audio_to_file(
        text, output_path, output_format=output_format
    )
