"""
Test WebSocket client with echo server.
"""

import asyncio
import json
import logging
from ws.client import WebSocketClient


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


class TestWebSocketClient:
    """Test class for WebSocket client."""

    def __init__(self):
        self.message_count = 0
        self.client: WebSocketClient | None = None

    def on_connect(self):
        """Called when connection is established."""
        logger.info("✅ Connected to WebSocket server")

    def on_disconnect(self):
        """Called when connection is lost."""
        logger.info("❌ Disconnected from WebSocket server")

    async def on_message(self, message: bytes | str):
        """
        Called when a message is received.

        Args:
            message: Received message (text or binary)
        """
        self.message_count += 1

        if isinstance(message, str):
            logger.info(f"📨 Received text message #{self.message_count}: {message}")
        else:
            logger.info(
                f"📨 Received binary message #{self.message_count}: {len(message)} bytes"
            )

    async def run_test(self):
        """Run the WebSocket client test."""
        # Create client
        self.client = WebSocketClient(
            url="wss://echo.websocket.org",
            on_connect=self.on_connect,
            on_disconnect=self.on_disconnect,
            on_message=self.on_message,
            max_retries=3,
            initial_retry_delay=1.0,
            max_retry_delay=10.0,
        )

        try:
            # Connect to server
            logger.info("🔌 Connecting to wss://echo.websocket.events...")
            await self.client.connect()

            # Wait a bit for connection to establish
            await asyncio.sleep(2)

            if not self.client.is_connected:
                logger.error("Failed to connect")
                return

            # Send some test messages
            logger.info("📤 Sending text message...")
            await self.client.send_text(
                json.dumps(
                    {
                        "type": "test",
                        "message": "Hello from WebSocket client!",
                        "timestamp": asyncio.get_event_loop().time(),
                    }
                )
            )

            await asyncio.sleep(1)

            logger.info("📤 Sending another text message...")
            await self.client.send_text("Simple text message")

            await asyncio.sleep(1)

            logger.info("📤 Sending binary message...")
            await self.client.send_binary(b"Binary test data: \x00\x01\x02\x03")

            # Wait for responses
            logger.info("⏳ Waiting for responses...")
            await asyncio.sleep(3)

            # Show stats
            logger.info(f"📊 Total messages received: {self.message_count}")

        except Exception as e:
            logger.error(f"❌ Test error: {e}")

        finally:
            # Close connection
            logger.info("🔌 Closing connection...")
            if self.client:
                await self.client.close()

            logger.info("✅ Test complete")


async def main():
    """Main entry point."""
    test = TestWebSocketClient()
    await test.run_test()


if __name__ == "__main__":
    asyncio.run(main())
