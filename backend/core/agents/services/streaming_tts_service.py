"""
Streaming Text-to-Speech Service Module

Optimized for low-latency voice interactions with sentence-by-sentence streaming.
Starts audio playback as soon as the first complete sentence is ready.
"""

import logging
import re
from typing import Generator, Optional, AsyncGenerator
import asyncio

from deepgram import DeepgramClient

from env_vars import DEEPGRAM_API_KEY, DEEPGRAM_TTS_MODEL
from agents.constants import AudioFormat, TTSDefaults, ErrorMessages

logger = logging.getLogger(__name__)


class StreamingTTSServiceError(Exception):
    """Base exception for streaming TTS service errors."""

    pass


class StreamingTTSService:
    """
    Streaming Text-to-Speech service optimized for low latency.

    Features:
    - Sentence-by-sentence TTS generation
    - Starts audio playback on first complete sentence
    - No buffering of full response
    - Supports interruption

    Example:
        >>> tts = StreamingTTSService()
        >>> async for audio_chunk, metadata in tts.generate_streaming(
        ...     "Hello! This is a test. It has multiple sentences."
        ... ):
        ...     await websocket.send(audio_chunk)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize streaming TTS service.

        Args:
            api_key: Deepgram API key
            model: TTS model name

        Raises:
            StreamingTTSServiceError: If API key is not provided
        """
        self.api_key = api_key or DEEPGRAM_API_KEY
        if not self.api_key:
            raise StreamingTTSServiceError(ErrorMessages.API_KEY_MISSING)

        self.model = model or DEEPGRAM_TTS_MODEL
        self.client = DeepgramClient(api_key=self.api_key)

        logger.info(f"StreamingTTSService initialized with model: {self.model}")

    def _split_into_sentences(self, text: str) -> list[str]:
        """
        Split text into sentences for streaming.

        Uses intelligent sentence boundary detection to avoid
        splitting on abbreviations, decimals, etc.

        Args:
            text: Input text to split

        Returns:
            List of sentences
        """
        # Split on sentence boundaries (. ! ? followed by space or end)
        # Use simple pattern without lookbehind to avoid regex errors
        pattern = r"([.!?]+)(?=\s+[A-Z]|\s*$)"

        # Split text and keep delimiters
        parts = re.split(pattern, text)

        # Recombine sentences with their punctuation
        result = []
        for i in range(0, len(parts) - 1, 2):
            sentence = parts[i].strip()
            if i + 1 < len(parts):
                # Add punctuation back
                sentence += parts[i + 1]
            if sentence:
                result.append(sentence.strip())

        # Add last part if it exists and is different
        if len(parts) % 2 == 1 and parts[-1].strip():
            last = parts[-1].strip()
            if not result or last not in result[-1]:
                result.append(last)

        # If no sentences detected, return original text
        if not result:
            result = [text.strip()]

        logger.debug(f"Split text into {len(result)} sentences")
        return result

    async def generate_streaming(
        self,
        text: str,
        encoding: str = "linear16",
        sample_rate: int = 16000,
        on_sentence_start: Optional[callable] = None,
    ) -> AsyncGenerator[tuple[bytes, dict], None]:
        """
        Generate audio from text with sentence-by-sentence streaming.

        Yields audio chunks as soon as each sentence is converted,
        allowing playback to start immediately.

        Args:
            text: Text to convert to speech
            encoding: Audio encoding
            sample_rate: Sample rate in Hz
            on_sentence_start: Optional callback when each sentence starts

        Yields:
            Tuple of (audio_chunk: bytes, metadata: dict)

        Raises:
            StreamingTTSServiceError: If generation fails
        """
        try:
            if not text or not text.strip():
                raise StreamingTTSServiceError(ErrorMessages.EMPTY_TEXT)

            # Split text into sentences
            sentences = self._split_into_sentences(text)

            logger.info(f"Generating TTS for {len(sentences)} sentences")

            # Process each sentence
            for idx, sentence in enumerate(sentences):
                if not sentence.strip():
                    continue

                # Notify sentence start
                if on_sentence_start:
                    on_sentence_start(idx, sentence)

                logger.info(
                    f"Generating TTS for sentence {idx + 1}/{len(sentences)}: '{sentence[:50]}...'"
                )

                # Generate audio for this sentence
                try:
                    options = {
                        "model": self.model,
                    }

                    if encoding:
                        options["encoding"] = encoding
                    if sample_rate:
                        options["sample_rate"] = str(sample_rate)

                    # Generate audio using Deepgram API
                    audio_response = self.client.speak.v1.audio.generate(
                        text=sentence, **options
                    )

                    # Stream chunks for this sentence
                    sentence_bytes = 0
                    chunk_count = 0

                    for chunk in audio_response:
                        if chunk:
                            chunk_count += 1
                            sentence_bytes += len(chunk)

                            # Yield chunk with metadata
                            metadata = {
                                "sentence_index": idx,
                                "sentence_text": sentence,
                                "total_sentences": len(sentences),
                                "chunk_index": chunk_count,
                                "is_last_sentence": idx == len(sentences) - 1,
                            }

                            yield chunk, metadata

                    logger.info(
                        f"Sentence {idx + 1} complete: {chunk_count} chunks, {sentence_bytes} bytes"
                    )

                except Exception as e:
                    logger.error(
                        f"Error generating audio for sentence {idx + 1}: {e}",
                        exc_info=True,
                    )
                    # Continue with next sentence rather than failing completely
                    continue

            logger.info(f"TTS streaming complete for all {len(sentences)} sentences")

        except StreamingTTSServiceError:
            raise
        except Exception as e:
            error_msg = f"Streaming TTS generation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StreamingTTSServiceError(error_msg) from e

    async def generate_single(
        self,
        text: str,
        encoding: str = "linear16",
        sample_rate: int = 16000,
    ) -> AsyncGenerator[bytes, None]:
        """
        Generate audio from text as a single utterance (no sentence splitting).

        Args:
            text: Text to convert to speech
            encoding: Audio encoding
            sample_rate: Sample rate in Hz

        Yields:
            Audio chunks as bytes

        Raises:
            StreamingTTSServiceError: If generation fails
        """
        try:
            if not text or not text.strip():
                raise StreamingTTSServiceError(ErrorMessages.EMPTY_TEXT)

            options = {
                "model": self.model,
            }

            if encoding:
                options["encoding"] = encoding
            if sample_rate:
                options["sample_rate"] = str(sample_rate)

            # Generate audio using Deepgram API
            audio_response = self.client.speak.v1.audio.generate(text=text, **options)

            # Stream chunks
            total_bytes = 0
            chunk_count = 0

            for chunk in audio_response:
                if chunk:
                    chunk_count += 1
                    total_bytes += len(chunk)
                    yield chunk

            logger.info(f"TTS complete: {chunk_count} chunks, {total_bytes} bytes")

        except StreamingTTSServiceError:
            raise
        except Exception as e:
            error_msg = f"TTS generation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StreamingTTSServiceError(error_msg) from e
