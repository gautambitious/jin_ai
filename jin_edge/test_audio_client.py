"""
Test audio client that connects to test server and plays received audio.
"""

import asyncio
import logging
from audio.buffer import AudioBuffer
from audio.player import AudioPlayer
from protocol.audio import AudioStreamHandler
from ws.client import WebSocketClient


logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AudioTestClient:
    """Test client for audio streaming over WebSocket."""

    def __init__(self):
        self.buffer = AudioBuffer(max_size=2 * 1024 * 1024)  # 2MB buffer
        self.player = AudioPlayer(
            sample_rate=16000, channels=1, dtype="int16", buffer_size=2 * 1024 * 1024
        )
        self.handler = AudioStreamHandler(self.buffer)
        self.client: WebSocketClient | None = None

        # Start player feeder task
        self._feeder_task: asyncio.Task | None = None
        self._running = False

    async def on_connect(self):
        """Called when connected to server."""
        logger.info("✅ Connected to audio server")

    async def on_disconnect(self):
        """Called when disconnected from server."""
        logger.info("❌ Disconnected from audio server")

    async def start(self, url: str):
        """
        Start the audio client.

        Args:
            url: WebSocket server URL
        """
        logger.info(f"Starting audio client for {url}")

        # Start audio player
        await self.player.start()
        logger.info("Audio player started")

        # Start buffer feeder
        self._running = True
        self._feeder_task = asyncio.create_task(self._feed_player())

        # Create WebSocket client with protocol handler
        self.client = WebSocketClient(
            url=url,
            protocol_handler=self.handler,
            on_connect=self.on_connect,
            on_disconnect=self.on_disconnect,
            max_retries=3,
        )

        # Connect
        await self.client.connect()

    async def _feed_player(self):
        """
        Continuously feed audio from buffer to player.
        Runs in background task.
        """
        logger.info("Buffer feeder started")
        playback_started = False

        while self._running:
            # Check if there's audio in the buffer
            buffer_size = await self.buffer.size()

            if buffer_size > 0:
                # Pull chunk from buffer
                chunk = await self.buffer.pop(chunk_size=4096)
                if chunk:
                    # Start playback with first chunk
                    if not playback_started:
                        logger.info("Starting audio playback with first chunk...")
                        await self.player.play(chunk)
                        playback_started = True
                    else:
                        # Feed subsequent chunks
                        success = await self.player.feed(chunk)
                        if not success:
                            logger.warning("Player buffer full, waiting...")
                            await asyncio.sleep(0.01)
                        else:
                            logger.debug(f"Fed {len(chunk)} bytes to player")
            else:
                # No data, sleep to avoid busy waiting
                await asyncio.sleep(0.01)

        logger.info("Buffer feeder stopped")

    async def stop(self):
        """Stop the audio client."""
        logger.info("Stopping audio client")

        # Stop feeder
        self._running = False
        if self._feeder_task:
            await self._feeder_task

        # Close WebSocket
        if self.client:
            await self.client.close()

        # Stop player
        await self.player.stop()

        logger.info("Audio client stopped")

    async def run(self, url: str, duration: float = 10.0):
        """
        Run the audio client for a specified duration.

        Args:
            url: WebSocket server URL
            duration: How long to run in seconds
        """
        try:
            await self.start(url)

            # Show status updates
            for i in range(int(duration)):
                await asyncio.sleep(1)
                buffer_size = await self.buffer.size()
                player_buffer = await self.player.buffer_size()
                stream_id = self.handler.active_stream_id
                logger.info(
                    f"[{i+1}s] Buffer: {buffer_size} bytes, "
                    f"Player: {player_buffer} bytes, "
                    f"Stream: {stream_id or 'none'}"
                )

        except Exception as e:
            logger.error(f"Error running client: {e}")
        finally:
            await self.stop()


async def main():
    """Main entry point."""
    client = AudioTestClient()
    await client.run(url="ws://127.0.0.1:8000/ws/audio/", duration=10)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Client stopped by user")
