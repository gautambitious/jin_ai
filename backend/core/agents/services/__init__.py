"""
Services Module

This module contains reusable services for the agents application,
including text-to-speech, external API integrations, audio streaming,
WebSocket broadcasting, and other shared functionality.
"""

from .tts_service import TTSService, TTSServiceError, text_to_audio, text_to_audio_file
from .audio_websocket_helper import AudioWebSocketHelper, play_text_on_websocket
from .websocket_tts_broadcaster import (
    broadcast_tts_message,
    send_tts_to_channel,
    broadcast_tts_message_sync,
    send_tts_to_channel_sync,
)


__all__ = [
    "TTSService",
    "TTSServiceError",
    "text_to_audio",
    "text_to_audio_file",
    "AudioWebSocketHelper",
    "play_text_on_websocket",
    "broadcast_tts_message",
    "send_tts_to_channel",
    "broadcast_tts_message_sync",
    "send_tts_to_channel_sync",
]
