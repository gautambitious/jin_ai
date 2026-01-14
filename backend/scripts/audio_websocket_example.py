"""
Example script demonstrating AudioWebSocketHelper usage.

This shows how to use the audio helper service to stream audio
over WebSocket connections in various ways.
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
import django

django.setup()

from agents.services.audio_websocket_helper import (
    AudioWebSocketHelper,
    play_text_on_websocket,
)


class MockWebSocket:
    """Mock WebSocket for testing without actual connection."""

    def __init__(self):
        self.sent_messages = []

    async def send(self, text_data=None, bytes_data=None):
        """Mock send method."""
        if text_data:
            self.sent_messages.append(("text", text_data))
            print(f"[Mock WS] Sent text: {text_data[:100]}...")
        if bytes_data:
            self.sent_messages.append(("bytes", len(bytes_data)))
            print(f"[Mock WS] Sent audio chunk: {len(bytes_data)} bytes")


async def example_1_stream_audio_buffer():
    """
    Example 1: Stream a pre-generated audio buffer.

    Use case: You already have audio data (from file, generated, etc.)
    and want to stream it to WebSocket consumers.
    """
    print("\n=== Example 1: Stream Audio Buffer ===")

    websocket = MockWebSocket()
    helper = AudioWebSocketHelper(websocket, sample_rate=16000, channels=1)

    # Simulate some audio data (1 second of silence at 16kHz, 16-bit PCM)
    audio_buffer = b"\x00\x00" * 16000  # 32000 bytes = 1 second

    await helper.stream_audio_buffer(
        audio_buffer,
        chunk_duration_ms=20,  # 20ms chunks
    )

    print(f"Total messages sent: {len(websocket.sent_messages)}")


async def example_2_text_to_speech_stream():
    """
    Example 2: Convert text to speech and stream it.

    Use case: This is the PRIMARY use case - take text input,
    generate audio using TTS, and play it over WebSocket.
    """
    print("\n=== Example 2: Text-to-Speech Streaming ===")

    websocket = MockWebSocket()
    helper = AudioWebSocketHelper(websocket, sample_rate=16000, channels=1)

    text = "Hello! This is Jin AI speaking. I can convert any text to speech and stream it over WebSocket for real-time playback."

    try:
        await helper.text_to_speech_stream(text)
        print(
            f"Successfully streamed TTS audio. Messages sent: {len(websocket.sent_messages)}"
        )
    except Exception as e:
        print(f"Error: {e}")


async def example_3_convenience_function():
    """
    Example 3: Using the convenience function.

    Use case: Quick one-liner to play text without creating helper instance.
    """
    print("\n=== Example 3: Convenience Function ===")

    websocket = MockWebSocket()

    try:
        await play_text_on_websocket(
            websocket=websocket,
            text="This is a quick test using the convenience function.",
        )
        print(
            f"Successfully played text. Messages sent: {len(websocket.sent_messages)}"
        )
    except Exception as e:
        print(f"Error: {e}")


async def example_4_in_consumer():
    """
    Example 4: How to use in an actual WebSocket consumer.

    This shows the typical usage pattern inside a consumer's method.
    """
    print("\n=== Example 4: Usage in Consumer ===")
    print(
        """
    # Inside your WebSocket consumer:
    
    from agents.services.audio_websocket_helper import AudioWebSocketHelper
    
    class MyConsumer(AsyncWebsocketConsumer):
        
        async def receive(self, text_data=None, bytes_data=None):
            # Get text from user message
            data = json.loads(text_data)
            user_text = data.get('message')
            
            # Create helper
            helper = AudioWebSocketHelper(
                websocket=self,  # Pass the consumer instance
                sample_rate=16000,
                channels=1,
            )
            
            # Convert text to speech and stream it
            await helper.text_to_speech_stream(
                text=f"You said: {user_text}"
            )
            
        async def send_custom_message(self, message_text):
            '''Custom method to speak a message'''
            helper = AudioWebSocketHelper(self)
            await helper.text_to_speech_stream(message_text)
    """
    )


async def main():
    """Run all examples."""
    print("AudioWebSocketHelper Examples")
    print("=" * 50)

    # Example 1: Stream audio buffer
    await example_1_stream_audio_buffer()

    # Example 2: Text to speech (main use case)
    await example_2_text_to_speech_stream()

    # Example 3: Convenience function
    await example_3_convenience_function()

    # Example 4: Usage pattern
    await example_4_in_consumer()

    print("\n" + "=" * 50)
    print("All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
