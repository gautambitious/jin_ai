"""
Protocol helper module for audio WebSocket messages.

This module provides utilities for building and parsing WebSocket messages
for audio streaming. No Django or Channels dependencies.
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def audio_start(stream_id: str, sample_rate: int, channels: int = 1) -> str:
    """
    Build an audio_start message.

    Args:
        stream_id: Unique identifier for the audio stream
        sample_rate: Sample rate in Hz (e.g., 16000, 24000, 48000)
        channels: Number of audio channels (default: 1 for mono)

    Returns:
        JSON string of the audio_start message

    Example:
        >>> audio_start("stream_123", 16000, 1)
        '{"type": "audio_start", "stream_id": "stream_123", "sample_rate": 16000, "channels": 1}'
    """
    message: Dict[str, Any] = {
        "type": "audio_start",
        "stream_id": stream_id,
        "sample_rate": sample_rate,
        "channels": channels,
    }
    return json.dumps(message)


def audio_end(stream_id: str) -> str:
    """
    Build an audio_end message.

    Args:
        stream_id: Unique identifier for the audio stream

    Returns:
        JSON string of the audio_end message

    Example:
        >>> audio_end("stream_123")
        '{"type": "audio_end", "stream_id": "stream_123"}'
    """
    message: Dict[str, Any] = {
        "type": "audio_end",
        "stream_id": stream_id,
    }
    return json.dumps(message)


def stop_playback() -> str:
    """
    Build a stop_playback message.

    Returns:
        JSON string of the stop_playback message

    Example:
        >>> stop_playback()
        '{"type": "stop_playback"}'
    """
    message: Dict[str, Any] = {
        "type": "stop_playback",
    }
    return json.dumps(message)


def safe_json_parse(text_data: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Safely parse JSON text data.

    Args:
        text_data: JSON string to parse

    Returns:
        Tuple of (parsed_data, error_message)
        - If successful: (dict, None)
        - If failed: (None, error_message)

    Example:
        >>> safe_json_parse('{"type": "ping"}')
        ({'type': 'ping'}, None)
        >>> safe_json_parse('invalid json')
        (None, 'Invalid JSON: Expecting value: line 1 column 1 (char 0)')
    """
    try:
        data = json.loads(text_data)
        if not isinstance(data, dict):
            return None, f"Invalid JSON: Expected object, got {type(data).__name__}"
        return data, None
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON: {str(e)}"
        logger.warning(f"JSON parse error: {error_msg}")
        return None, error_msg
    except Exception as e:
        error_msg = f"Unexpected error parsing JSON: {str(e)}"
        logger.error(error_msg)
        return None, error_msg


def validate_message_type(data: Dict[str, Any], expected_type: str) -> bool:
    """
    Validate that a message has the expected type.

    Args:
        data: Parsed JSON message
        expected_type: Expected value for the "type" field

    Returns:
        True if message type matches, False otherwise

    Example:
        >>> validate_message_type({"type": "audio_start"}, "audio_start")
        True
        >>> validate_message_type({"type": "audio_end"}, "audio_start")
        False
    """
    message_type = data.get("type")
    if message_type != expected_type:
        logger.warning(
            f"Message type mismatch: expected '{expected_type}', got '{message_type}'"
        )
        return False
    return True
