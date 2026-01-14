"""
WebSocket TTS Broadcast Service
================================

Server-side service for sending text-to-speech audio to WebSocket consumers.
Can be called from anywhere in your Django application (views, tasks, management commands, etc.)

Usage:
    from agents.services.websocket_tts_broadcaster import broadcast_tts_message

    # Broadcast to all connected clients
    await broadcast_tts_message("Hello everyone!")

    # Send to specific channel
    await send_tts_to_channel(channel_name, "Hello specific client!")
"""

import logging
from typing import Optional
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


async def broadcast_tts_message(
    text: str,
    group_name: str = "edge_devices",
) -> None:
    """
    Broadcast a text-to-speech message to all connected WebSocket clients in a group.

    This sends a "speak" command to all clients in the specified group.
    Each client will convert the text to speech and play it.

    Args:
        text: Text message to be converted to speech
        group_name: Channel layer group name (default: "edge_devices")

    Example:
        >>> await broadcast_tts_message("System update in progress")
        >>> await broadcast_tts_message("New alert received", group_name="alerts")
    """
    if not text or not text.strip():
        logger.warning("Attempted to broadcast empty text")
        return

    channel_layer = get_channel_layer()

    if not channel_layer:
        logger.error("Channel layer not configured")
        return

    try:
        # Send speak command to all clients in the group
        await channel_layer.group_send(
            group_name,
            {
                "type": "speak_message",
                "text": text,
            },
        )

        logger.info(f"Broadcast TTS message to group '{group_name}': {text[:50]}...")

    except Exception as e:
        logger.error(f"Error broadcasting TTS message: {e}", exc_info=True)


async def send_tts_to_channel(
    channel_name: str,
    text: str,
) -> None:
    """
    Send a text-to-speech message to a specific WebSocket channel.

    Args:
        channel_name: Specific channel name to send to
        text: Text message to be converted to speech

    Example:
        >>> await send_tts_to_channel("specific.channel.name", "Hello!")
    """
    if not text or not text.strip():
        logger.warning("Attempted to send empty text")
        return

    channel_layer = get_channel_layer()

    if not channel_layer:
        logger.error("Channel layer not configured")
        return

    try:
        await channel_layer.send(
            channel_name,
            {
                "type": "speak_message",
                "text": text,
            },
        )

        logger.info(f"Sent TTS message to channel '{channel_name}': {text[:50]}...")

    except Exception as e:
        logger.error(f"Error sending TTS message: {e}", exc_info=True)


def broadcast_tts_message_sync(
    text: str,
    group_name: str = "edge_devices",
) -> None:
    """
    Synchronous version of broadcast_tts_message.

    Use this from synchronous code (views, management commands, etc.)

    Args:
        text: Text message to be converted to speech
        group_name: Channel layer group name (default: "edge_devices")

    Example:
        >>> from agents.services.websocket_tts_broadcaster import broadcast_tts_message_sync
        >>> broadcast_tts_message_sync("Alert from Django view!")
    """
    if not text or not text.strip():
        logger.warning("Attempted to broadcast empty text")
        return

    channel_layer = get_channel_layer()

    if not channel_layer:
        logger.error("Channel layer not configured")
        return

    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "speak_message",
                "text": text,
            },
        )

        logger.info(f"Broadcast TTS message to group '{group_name}': {text[:50]}...")

    except Exception as e:
        logger.error(f"Error broadcasting TTS message: {e}", exc_info=True)


def send_tts_to_channel_sync(
    channel_name: str,
    text: str,
) -> None:
    """
    Synchronous version of send_tts_to_channel.

    Use this from synchronous code.

    Args:
        channel_name: Specific channel name to send to
        text: Text message to be converted to speech

    Example:
        >>> send_tts_to_channel_sync("specific.channel.name", "Message!")
    """
    if not text or not text.strip():
        logger.warning("Attempted to send empty text")
        return

    channel_layer = get_channel_layer()

    if not channel_layer:
        logger.error("Channel layer not configured")
        return

    try:
        async_to_sync(channel_layer.send)(
            channel_name,
            {
                "type": "speak_message",
                "text": text,
            },
        )

        logger.info(f"Sent TTS message to channel '{channel_name}': {text[:50]}...")

    except Exception as e:
        logger.error(f"Error sending TTS message: {e}", exc_info=True)
