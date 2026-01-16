#!/usr/bin/env python3
"""
Optimized Streaming Client Example

Demonstrates usage of the new optimized streaming endpoint for minimal latency.

This client:
1. Streams mic audio directly to server (no buffering)
2. Receives interim transcripts for immediate feedback
3. Gets early intent detection notifications
4. Receives audio response sentence-by-sentence
5. Supports interruption with new input
"""

import asyncio
import json
import logging
import pyaudio
import websockets
from typing import Optional

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class OptimizedStreamingClient:
    """
    Optimized client for low-latency voice interactions.
    """

    def __init__(
        self,
        server_url: str = "ws://localhost:8000/ws/stream/test_session",
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
    ):
        self.server_url = server_url
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size

        # Audio
        self.audio = pyaudio.PyAudio()
        self.input_stream: Optional[pyaudio.Stream] = None
        self.output_stream: Optional[pyaudio.Stream] = None

        # WebSocket
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None

        # State
        self.is_recording = False
        self.is_playing = False
        self.should_stop = False

    async def connect(self):
        """Connect to server"""
        try:
            self.websocket = await websockets.connect(self.server_url)
            logger.info(f"Connected to {self.server_url}")

            # Wait for connection message
            msg = await self.websocket.recv()
            data = json.loads(msg)
            logger.info(f"Server: {data.get('message')}")
            logger.info(f"Optimizations: {data.get('optimizations', [])}")

            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from server"""
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected")

    async def start_conversation(self):
        """Start voice conversation loop"""
        try:
            # Start message receiver
            receive_task = asyncio.create_task(self._receive_messages())

            logger.info("\n=== Ready for voice interaction ===")
            logger.info("Press ENTER to start speaking, ENTER again to stop")
            logger.info("Type 'quit' to exit\n")

            while not self.should_stop:
                # Wait for user to start speaking
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, input, "Press ENTER to speak (or 'quit'): "
                )

                if user_input.lower() == "quit":
                    break

                # Start recording and streaming
                await self._record_and_stream()

                # Wait a bit for response to complete
                await asyncio.sleep(1)

            # Cancel receiver
            receive_task.cancel()

        except KeyboardInterrupt:
            logger.info("\nInterrupted by user")
        finally:
            await self.disconnect()

    async def _record_and_stream(self):
        """Record audio and stream to server"""
        try:
            # Interrupt any ongoing playback
            if self.is_playing:
                await self._send_control({"type": "interrupt"})
                await asyncio.sleep(0.1)

            # Start audio input
            await self._send_control(
                {
                    "type": "start_audio_input",
                    "config": {
                        "sample_rate": self.sample_rate,
                        "channels": self.channels,
                        "encoding": "linear16",
                    },
                }
            )

            # Open microphone
            self.input_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
            )

            self.is_recording = True
            logger.info("🎤 Recording... Press ENTER to stop")

            # Stream audio in background
            stream_task = asyncio.create_task(self._stream_audio())

            # Wait for user to stop
            await asyncio.get_event_loop().run_in_executor(None, input, "")

            # Stop recording
            self.is_recording = False
            await stream_task

            if self.input_stream:
                self.input_stream.stop_stream()
                self.input_stream.close()
                self.input_stream = None

            # Stop audio input
            await self._send_control({"type": "stop_audio_input"})

            logger.info("🎤 Recording stopped")

        except Exception as e:
            logger.error(f"Recording error: {e}")
            self.is_recording = False

    async def _stream_audio(self):
        """Stream audio chunks to server"""
        try:
            while self.is_recording and self.input_stream:
                # Read audio chunk
                audio_data = self.input_stream.read(
                    self.chunk_size, exception_on_overflow=False
                )

                # Send to server immediately (no buffering!)
                await self.websocket.send(audio_data)

                # Small delay to avoid overwhelming
                await asyncio.sleep(0.01)

        except Exception as e:
            logger.error(f"Streaming error: {e}")

    async def _receive_messages(self):
        """Receive and handle messages from server"""
        try:
            async for message in self.websocket:
                # Handle binary (audio) messages
                if isinstance(message, bytes):
                    await self._play_audio(message)
                    continue

                # Handle text (JSON) messages
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON: {message}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Receive error: {e}")

    async def _handle_message(self, data: dict):
        """Handle JSON message from server"""
        msg_type = data.get("type")

        if msg_type == "transcript":
            # Transcript received
            text = data.get("text", "")
            is_final = data.get("is_final", False)
            confidence = data.get("confidence", 0)

            if is_final:
                logger.info(f"📝 Final: '{text}' (confidence: {confidence:.2f})")
            else:
                logger.debug(f"📝 Interim: '{text}'")

        elif msg_type == "intent_detected":
            # Early intent detection
            route = data.get("route", "unknown")
            logger.info(f"🎯 Intent detected early: {route}")

        elif msg_type == "route_decision":
            # Routing decision
            route = data.get("route", "unknown")
            logger.info(f"🔀 Routed to: {route}")

        elif msg_type == "response_complete":
            # Response complete
            text = data.get("text", "")
            logger.info(f"✅ Response complete: '{text[:100]}...'")

        elif msg_type == "audio_input_started":
            logger.debug("Audio input started")

        elif msg_type == "audio_input_stopped":
            logger.debug("Audio input stopped")

        elif msg_type == "interrupted":
            logger.info("⚠️ Playback interrupted")

        elif msg_type == "error":
            logger.error(f"❌ Error: {data.get('message')}")

        else:
            logger.debug(f"Message: {msg_type}")

    async def _play_audio(self, audio_data: bytes):
        """Play audio chunk"""
        try:
            if not self.is_playing:
                # Initialize output stream on first chunk
                self.output_stream = self.audio.open(
                    format=pyaudio.paInt16,
                    channels=self.channels,
                    rate=self.sample_rate,
                    output=True,
                )
                self.is_playing = True
                logger.info("🔊 Playing response...")

            # Play audio chunk
            self.output_stream.write(audio_data)

        except Exception as e:
            logger.error(f"Playback error: {e}")

    async def _send_control(self, message: dict):
        """Send control message to server"""
        try:
            await self.websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Send error: {e}")

    def cleanup(self):
        """Cleanup resources"""
        if self.input_stream:
            self.input_stream.close()
        if self.output_stream:
            self.output_stream.close()
        self.audio.terminate()


async def main():
    """Main entry point"""
    import sys

    # Parse arguments
    server_url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "ws://localhost:8000/ws/stream/test_session"
    )

    client = OptimizedStreamingClient(server_url=server_url)

    try:
        if await client.connect():
            await client.start_conversation()
    finally:
        client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
