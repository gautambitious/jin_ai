"""
Server-side script to broadcast TTS messages to WebSocket clients.

This script can be run from anywhere on the server to send
text-to-speech messages to connected clients.

Requirements:
    - WebSocket server must be running
    - Redis must be running (for channel layer)

Usage:
    python scripts/server_broadcast_tts.py "Your message here"
    python scripts/server_broadcast_tts.py "Alert!" --group alerts
"""

import sys
import os
import asyncio
import argparse

# Add parent directory to path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
core_dir = os.path.join(backend_dir, "core")

sys.path.insert(0, core_dir)
sys.path.insert(0, backend_dir)

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
import django

django.setup()

from agents.services.websocket_tts_broadcaster import broadcast_tts_message


async def send_message(text: str, group_name: str = "edge_devices"):
    """
    Send a TTS message to connected WebSocket clients.

    Args:
        text: Message to broadcast
        group_name: Channel layer group name
    """
    print("\n" + "=" * 60)
    print("🎤 Broadcasting TTS Message")
    print("=" * 60)
    print(f"Group: {group_name}")
    print(f"Text: {text}")
    print("-" * 60)

    try:
        await broadcast_tts_message(text, group_name=group_name)
        print("✅ Message broadcast successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Broadcast TTS messages to WebSocket clients"
    )
    parser.add_argument("text", type=str, help="Text message to broadcast")
    parser.add_argument(
        "--group",
        type=str,
        default="edge_devices",
        help="Channel layer group name (default: edge_devices)",
    )

    args = parser.parse_args()

    # Send the message
    asyncio.run(send_message(args.text, args.group))


if __name__ == "__main__":
    main()
