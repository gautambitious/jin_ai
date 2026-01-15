"""
Constants for Agents Module

This module contains all constants used throughout the agents module,
including TTS/STT configuration, audio formats, and service defaults.
"""


# Audio Format Constants
class AudioFormat:
    """Audio format specifications for TTS/STT."""

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

    # Default sample rate for streaming (16kHz for compatibility with all clients)
    DEFAULT_SAMPLE_RATE = SAMPLE_RATE_16KHZ


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


# STT Service Constants
class STTDefaults:
    """Default values for Speech-to-Text service."""

    # Default language for transcription
    DEFAULT_LANGUAGE = "en-US"

    # Default audio encoding for incoming audio
    DEFAULT_ENCODING = "linear16"

    # Default sample rate (matches AudioFormat.DEFAULT_SAMPLE_RATE)
    DEFAULT_SAMPLE_RATE = AudioFormat.SAMPLE_RATE_24KHZ

    # Default number of audio channels
    DEFAULT_CHANNELS = 1

    # Chunk size for receiving audio (in bytes)
    CHUNK_SIZE = 8192

    # Connection timeout (seconds)
    CONNECTION_TIMEOUT = 30

    # Keepalive interval when no audio (seconds)
    KEEPALIVE_INTERVAL = 5


# Error Messages
class ErrorMessages:
    """Standard error messages for TTS/STT services."""

    EMPTY_TEXT = "Input text cannot be empty"
    TEXT_TOO_LONG = (
        f"Input text exceeds maximum length of {TTSDefaults.MAX_TEXT_LENGTH} characters"
    )
    API_KEY_MISSING = "Deepgram API key is not configured"
    MODEL_NOT_FOUND = "Specified model is not available"
    AUDIO_GENERATION_FAILED = "Failed to generate audio from text"
    TRANSCRIPTION_FAILED = "Failed to transcribe audio"
    INVALID_FORMAT = "Invalid audio format specified"
    CONNECTION_FAILED = "Failed to establish connection to Deepgram"
    NO_ACTIVE_CONNECTION = "No active transcription connection"
