"""
Standalone TTS Test Script - Shell Ready
=========================================

Run this script directly to test text-to-speech without WebSocket:
    python scripts/test_tts_standalone.py

Or import and run in Python shell:
    >>> from scripts.test_tts_standalone import test_tts
    >>> test_tts("Hello from Jin AI!")
"""

import asyncio
import sys
import os

# Get the backend directory (parent of scripts)
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
core_dir = os.path.join(backend_dir, "core")

# Add both to path so Django can find env_vars and other modules
sys.path.insert(0, core_dir)
sys.path.insert(0, backend_dir)

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
import django

django.setup()

from agents.services.audio_websocket_helper import AudioWebSocketHelper


class MockWebSocket:
    """Mock WebSocket for standalone testing."""

    def __init__(self):
        self.messages_sent = 0
        self.audio_bytes_sent = 0

    async def send(self, text_data=None, bytes_data=None):
        """Mock send method."""
        if text_data:
            self.messages_sent += 1
            print(f"📤 Control message sent: {text_data[:80]}...")
        if bytes_data:
            self.audio_bytes_sent += len(bytes_data)
            print(f"🔊 Audio chunk sent: {len(bytes_data)} bytes")


async def test_tts(text="Hello! This is Jin AI speaking."):
    """
    Test text-to-speech without real WebSocket.

    Args:
        text: Text to convert to speech
    """
    print("\n" + "=" * 60)
    print("🎤 Testing Text-to-Speech")
    print("=" * 60)
    print(f"Text: {text}")
    print("-" * 60)

    # Create mock WebSocket
    mock_websocket = MockWebSocket()

    # Create helper with mock
    helper = AudioWebSocketHelper(mock_websocket)

    # Stream text as audio
    try:
        await helper.text_to_speech_stream(text)

        print("-" * 60)
        print(f"✅ Success!")
        print(f"   Messages sent: {mock_websocket.messages_sent}")
        print(f"   Audio bytes: {mock_websocket.audio_bytes_sent:,}")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


async def test_multiple_messages():
    """Test sending multiple messages in sequence."""
    print("\n" + "=" * 60)
    print("🎤 Testing Multiple Messages")
    print("=" * 60)

    mock_websocket = MockWebSocket()
    helper = AudioWebSocketHelper(mock_websocket)

    messages = [
        "First message.",
        "Second message.",
        "Third message.",
    ]

    for i, msg in enumerate(messages, 1):
        print(f"\nMessage {i}: {msg}")
        print("-" * 60)
        await helper.text_to_speech_stream(msg)
        print(f"✅ Sent message {i}")

    print("-" * 60)
    print(f"✅ All messages sent!")
    print(f"   Total messages: {mock_websocket.messages_sent}")
    print(f"   Total audio bytes: {mock_websocket.audio_bytes_sent:,}")
    print("=" * 60 + "\n")


async def test_custom_text():
    """Test with custom user input."""
    print("\n" + "=" * 60)
    print("🎤 Custom Text-to-Speech Test")
    print("=" * 60)

    text = input("Enter text to convert to speech: ")

    if text.strip():
        await test_tts(text)
    else:
        print("❌ No text entered")


def main():
    """Main entry point."""
    print("\n🎙️  Text-to-Speech Standalone Test")
    print("=" * 60)
    print("This script tests TTS without requiring a WebSocket connection")
    print("=" * 60)

    # Test basic TTS
    asyncio.run(test_tts())

    # Test multiple messages
    asyncio.run(test_multiple_messages())

    print("\n✨ All tests completed!")
    print("\nTo test with custom text, run:")
    print(
        "    python -c 'from scripts.test_tts_standalone import test_custom_text; import asyncio; asyncio.run(test_custom_text())'"
    )


# Shell-ready functions
def quick_test(text="Hello! This is a quick test."):
    """Quick test function for shell usage."""
    asyncio.run(test_tts(text))


if __name__ == "__main__":
    main()
