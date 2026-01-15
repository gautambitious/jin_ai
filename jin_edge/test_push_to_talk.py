"""
Test script for push-to-talk controller.
Demonstrates basic usage with WebSocket connection.
"""

import asyncio
import logging
from control.push_to_talk import PushToTalkController
from ws.client import WebSocketClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def main():
    """
    Test push-to-talk functionality.

    Make sure you have a WebSocket server running first.
    Default: ws://localhost:8000/ws
    """
    # Configuration
    WS_URL = "ws://localhost:8000/ws"

    logger.info("Starting push-to-talk test...")

    # Create WebSocket client
    ws_client = WebSocketClient(
        url=WS_URL,
        on_connect=lambda: logger.info("✓ Connected to server"),
        on_disconnect=lambda: logger.warning("✗ Disconnected from server"),
    )

    try:
        # Connect to WebSocket server
        logger.info(f"Connecting to {WS_URL}...")
        await ws_client.connect()

        # Wait for connection to establish
        await asyncio.sleep(1)

        # Create and start push-to-talk controller
        ptt = PushToTalkController(ws_client=ws_client)
        await ptt.start()

        # Run until interrupted
        logger.info("Press Ctrl+C to exit")
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        # Cleanup
        if "ptt" in locals():
            await ptt.stop()
        await ws_client.close()
        logger.info("Cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
