"""
Quick Shell Test for TTS
=========================

Copy and paste this into your Python shell:

import asyncio, sys, os
sys.path.insert(0, 'core')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
import django
django.setup()

from agents.services.audio_websocket_helper import AudioWebSocketHelper

class MockWS:
    async def send(self, text_data=None, bytes_data=None):
        if text_data: print(f"📤 {text_data[:50]}")
        if bytes_data: print(f"🔊 {len(bytes_data)} bytes")

ws = MockWS()
helper = AudioWebSocketHelper(ws)
asyncio.run(helper.text_to_speech_stream("Hello! This is Jin AI speaking."))
"""

# For direct execution
if __name__ == "__main__":
    import asyncio
    import sys
    import os

    # Get the backend and core directories
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    core_dir = os.path.join(backend_dir, "core")

    # Add both to path so Django can find env_vars and other modules
    sys.path.insert(0, core_dir)
    sys.path.insert(0, backend_dir)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
    import django

    django.setup()

    from agents.services.audio_websocket_helper import AudioWebSocketHelper

    class MockWebSocket:
        async def send(self, text_data=None, bytes_data=None):
            if text_data:
                print(f"📤 Control: {text_data[:60]}")
            if bytes_data:
                print(f"🔊 Audio: {len(bytes_data)} bytes")

    async def run():
        ws = MockWebSocket()
        helper = AudioWebSocketHelper(ws)
        await helper.text_to_speech_stream("Hello! This is Jin AI speaking.")
        print("✅ Done!")

    asyncio.run(run())
