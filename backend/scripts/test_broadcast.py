"""
Test Broadcasting from Django Shell/Script
===========================================

This script properly sets up Django and tests broadcasting.
"""

import sys
import os
import asyncio

# Setup paths
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
core_dir = os.path.join(backend_dir, "core")

sys.path.insert(0, core_dir)
sys.path.insert(0, backend_dir)

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
import django

django.setup()

from agents.services import broadcast_tts_message


async def test_broadcast():
    """Test broadcasting a message."""
    print("\n" + "=" * 60)
    print("🎤 Testing TTS Broadcast")
    print("=" * 60)

    message = "Hello from test script! This is a broadcast message."
    print(f"Sending: {message}")
    print("-" * 60)

    try:
        await broadcast_tts_message(message)
        print("✅ Message sent successfully!")
        print("   Check your connected WebSocket client for audio playback")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_broadcast())
