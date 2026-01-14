"""
Main entry point for Jin Edge audio client.
Connects to backend WebSocket server and plays audio.
"""

import asyncio
import logging
import signal
import sys
from audio.buffer import AudioBuffer
from audio.player import AudioPlayer
from protocol.audio import AudioStreamHandler
from ws.client import WebSocketClient
import env_vars


# Configure logging
logging.basicConfig(
    level=getattr(logging, env_vars.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


class JinEdgeClient:
    """Main client that manages WebSocket connection and audio playback."""

    def __init__(self):
        self.audio_player = AudioPlayer(
            sample_rate=env_vars.AUDIO_SAMPLE_RATE,
            channels=env_vars.AUDIO_CHANNELS,
            buffer_size=env_vars.AUDIO_BUFFER_SIZE,
            chunk_size=env_vars.AUDIO_CHUNK_SIZE,
        )
        # Use the player's internal buffer directly
        self.protocol_handler = AudioStreamHandler(
            self.audio_player._buffer, self.audio_player
        )
        self.ws_client: WebSocketClient | None = None
        self.running = False

    def on_connect(self):
        """Called when WebSocket connection is established."""
        logger.info("✅ Connected to backend server")

    def on_disconnect(self):
        """Called when WebSocket connection is lost."""
        logger.warning("❌ Disconnected from backend server")

    async def start(self):
        """Start the audio client."""
        logger.info("🚀 Starting Jin Edge audio client...")

        # Start audio player
        logger.info("🔊 Initializing audio player...")
        await self.audio_player.start()

        # Create WebSocket client with protocol handler
        self.ws_client = WebSocketClient(
            url=env_vars.WEBSOCKET_URL,
            protocol_handler=self.protocol_handler,
            on_connect=self.on_connect,
            on_disconnect=self.on_disconnect,
            max_retries=env_vars.WS_MAX_RETRIES,
            initial_retry_delay=env_vars.WS_INITIAL_RETRY_DELAY,
            max_retry_delay=env_vars.WS_MAX_RETRY_DELAY,
        )

        # Connect to WebSocket server
        logger.info(f"🔌 Connecting to {env_vars.WEBSOCKET_URL}...")
        await self.ws_client.connect()

        # Keep running until stopped
        logger.info("🎵 Audio client running, waiting for audio streams...")
        self.running = True
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Main loop cancelled")

    async def stop(self):
        """Stop the audio client."""
        logger.info("🛑 Stopping Jin Edge audio client...")
        self.running = False

        if self.ws_client:
            await self.ws_client.close()

        await self.audio_player.stop()
        logger.info("✅ Stopped")


async def main():
    """Main entry point."""
    client = JinEdgeClient()

    # Setup signal handlers for graceful shutdown
    def signal_handler():
        logger.info("⚠️  Received shutdown signal")
        asyncio.create_task(client.stop())

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await client.start()
    except KeyboardInterrupt:
        logger.info("⚠️  Keyboard interrupt")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
    finally:
        await client.stop()


if __name__ == "__main__":
    logger.info("🎯 Jin Edge - Audio Client for Raspberry Pi")
    asyncio.run(main())
