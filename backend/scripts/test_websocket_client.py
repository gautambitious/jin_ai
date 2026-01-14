"""
WebSocket Client for Testing TTS Audio Streaming
=================================================

This script connects to your running WebSocket server and sends
text messages to be converted to speech and played.

Requirements:
    pip install websockets

Usage:
    1. Start your WebSocket server:
       python manage.py start_ws_server --host 127.0.0.1 --port 8000

    2. Run this script:
       python scripts/test_websocket_client.py
"""

import asyncio
import json
import websockets


async def test_tts_websocket():
    """
    Connect to WebSocket server and test text-to-speech functionality.
    """
    uri = "ws://127.0.0.1:8000/ws/audio/"

    print("\n" + "=" * 60)
    print("🎤 WebSocket TTS Client")
    print("=" * 60)
    print(f"Connecting to: {uri}")

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            print("-" * 60)

            # Listen for welcome messages
            print("\n📥 Listening for welcome messages...")
            welcome_count = 0

            # Wait for initial messages (welcome tones + voice greeting)
            try:
                while welcome_count < 10:  # Listen for a few messages
                    message = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    welcome_count += 1

                    if isinstance(message, str):
                        data = json.loads(message)
                        print(f"   Control message: {data.get('type')}")
                    else:
                        print(f"   Audio chunk: {len(message)} bytes")

            except asyncio.TimeoutError:
                print(f"   Received {welcome_count} welcome messages")

            print("-" * 60)

            # Test sending text to be spoken
            test_messages = [
                "Hello! This is a test message from the client.",
                "I am Jin AI, your voice assistant.",
                "Text to speech is working perfectly!",
            ]

            for i, text in enumerate(test_messages, 1):
                print(f"\n🎤 Test {i}: Sending text to be spoken")
                print(f"   Text: {text}")

                # Send speak command
                message = {"type": "speak", "text": text}
                await websocket.send(json.dumps(message))
                print("   ✅ Sent!")

                # Listen for audio response
                print("   📥 Receiving audio...")
                audio_chunks = 0
                try:
                    while True:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)

                        if isinstance(response, str):
                            data = json.loads(response)
                            msg_type = data.get("type")
                            print(f"      Control: {msg_type}")
                            if msg_type == "audio_end":
                                break
                        else:
                            audio_chunks += 1

                except asyncio.TimeoutError:
                    pass

                print(f"   ✅ Received {audio_chunks} audio chunks")
                print("-" * 60)

                # Wait a bit between messages
                await asyncio.sleep(1)

            print("\n✨ All tests completed successfully!")
            print("=" * 60 + "\n")

    except ConnectionRefusedError:
        print("❌ Connection refused!")
        print("   Make sure your WebSocket server is running:")
        print("   python manage.py start_ws_server --host 127.0.0.1 --port 8000")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


async def interactive_mode():
    """
    Interactive mode - type messages to be spoken.
    """
    uri = "ws://127.0.0.1:8000/ws/audio/"

    print("\n" + "=" * 60)
    print("🎤 Interactive TTS Mode")
    print("=" * 60)
    print(f"Connecting to: {uri}")

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            print("Type messages to speak (or 'quit' to exit)")
            print("-" * 60)

            # Background task to receive messages
            async def receive_messages():
                try:
                    while True:
                        message = await websocket.recv()
                        if isinstance(message, str):
                            data = json.loads(message)
                            print(f"📥 {data.get('type')}")
                except:
                    pass

            # Start receiving in background
            receive_task = asyncio.create_task(receive_messages())

            # Interactive loop
            while True:
                try:
                    # Get user input (in a non-blocking way)
                    text = await asyncio.get_event_loop().run_in_executor(
                        None, input, "\n🎤 Enter text: "
                    )

                    if text.lower() in ["quit", "exit", "q"]:
                        print("👋 Goodbye!")
                        break

                    if text.strip():
                        # Send to WebSocket
                        message = {"type": "speak", "text": text}
                        await websocket.send(json.dumps(message))
                        print("✅ Sent!")

                except KeyboardInterrupt:
                    print("\n👋 Goodbye!")
                    break

            receive_task.cancel()

    except ConnectionRefusedError:
        print("❌ Connection refused!")
        print("   Make sure your WebSocket server is running:")
        print("   python manage.py start_ws_server --host 127.0.0.1 --port 8000")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Main entry point."""
    import sys

    print("\n🎙️  WebSocket TTS Test Client")

    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        # Interactive mode
        asyncio.run(interactive_mode())
    else:
        # Automated test mode
        asyncio.run(test_tts_websocket())

        print("\nℹ️  To use interactive mode:")
        print("   python scripts/test_websocket_client.py interactive")


if __name__ == "__main__":
    main()
