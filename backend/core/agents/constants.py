"""
Constants for Agents Module

This module contains all constants used throughout the agents module,
including TTS configuration, audio formats, and service defaults.
"""


# Audio Format Constants
class AudioFormat:
    """Audio format specifications for TTS output."""

    # Supported output formats for Deepgram TTS
    WAV = "wav"
    MP3 = "mp3"
    OPUS = "opus"
    FLAC = "flac"

    # Default format for streaming (LINEAR16 for raw PCM audio)
    # Use LINEAR16 for simple clients that expect raw PCM data
    # OPUS is more efficient but requires decoding on client side
    DEFAULT_STREAMING_FORMAT = "linear16"

    # Sample rates
    SAMPLE_RATE_8KHZ = 8000  # Telephony quality
    SAMPLE_RATE_16KHZ = 16000  # Wide band speech
    SAMPLE_RATE_24KHZ = 24000  # High quality speech
    SAMPLE_RATE_48KHZ = 48000  # Studio quality

    # Default sample rate for Raspberry Pi streaming
    DEFAULT_SAMPLE_RATE = SAMPLE_RATE_24KHZ


# TTS Service Constants
class TTSDefaults:
    """Default values for Text-to-Speech service."""

    # Encoding for text input
    TEXT_ENCODING = "utf-8"

    # Chunk size for streaming audio (in bytes)
    CHUNK_SIZE = 8192

    # Maximum text length for single TTS request (characters)
    MAX_TEXT_LENGTH = 2000

    # Timeout for TTS API requests (seconds)
    API_TIMEOUT = 30


# Error Messages
class ErrorMessages:
    """Standard error messages for TTS service."""

    EMPTY_TEXT = "Input text cannot be empty"
    TEXT_TOO_LONG = (
        f"Input text exceeds maximum length of {TTSDefaults.MAX_TEXT_LENGTH} characters"
    )
    API_KEY_MISSING = "Deepgram API key is not configured"
    MODEL_NOT_FOUND = "Specified TTS model is not available"
    AUDIO_GENERATION_FAILED = "Failed to generate audio from text"
    INVALID_FORMAT = "Invalid audio output format specified"
