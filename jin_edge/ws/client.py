"""
Asyncio-based WebSocket client with auto-reconnect.
Simple, lightweight, no business logic.
"""

import asyncio
import logging
from typing import Awaitable, Callable, Optional, Protocol, Union
import websockets
from websockets.asyncio.client import ClientConnection


logger = logging.getLogger(__name__)


class MessageHandler(Protocol):
    """Protocol for message handlers (e.g., AudioStreamHandler)."""

    async def handle_json_message(self, message: str) -> None:
        """Handle JSON text message."""
        ...

    async def handle_binary_message(self, data: bytes) -> None:
        """Handle binary message."""
        ...


class WebSocketClient:
    """
    Persistent WebSocket client with auto-reconnect.

    Supports text (JSON) and binary messages.
    Uses callbacks for events, no embedded business logic.

    Usage with callbacks:
        client = WebSocketClient(
            url="ws://localhost:8000/ws",
            on_connect=handle_connect,
            on_disconnect=handle_disconnect,
            on_message=handle_message
        )
        await client.connect()
        await client.send_text('{"type": "hello"}')
        await client.send_binary(audio_bytes)
        await client.close()

    Usage with protocol handler:
        handler = AudioStreamHandler(audio_buffer)
        client = WebSocketClient(
            url="ws://localhost:8000/ws",
            protocol_handler=handler
        )
        await client.connect()
    """

    def __init__(
        self,
        url: str,
        protocol_handler: Optional[MessageHandler] = None,
        on_connect: Optional[Callable[[], Union[None, Awaitable[None]]]] = None,
        on_disconnect: Optional[Callable[[], Union[None, Awaitable[None]]]] = None,
        on_message: Optional[
            Callable[[bytes | str], Union[None, Awaitable[None]]]
        ] = None,
        max_retries: int = 10,
        initial_retry_delay: float = 1.0,
        max_retry_delay: float = 60.0,
    ):
        """
        Initialize WebSocket client.

        Args:
            url: WebSocket server URL (ws:// or wss://)
            protocol_handler: Optional message handler (e.g., AudioStreamHandler)
            on_connect: Callback when connection established
            on_disconnect: Callback when connection lost
            on_message: Callback for incoming messages (text or binary)
            max_retries: Max reconnection attempts (0 = infinite)
            initial_retry_delay: Initial retry delay in seconds
            max_retry_delay: Maximum retry delay in seconds
        """
        self.url = url
        self.protocol_handler = protocol_handler
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_message = on_message

        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.max_retry_delay = max_retry_delay

        self._ws: Optional[ClientConnection] = None
        self._running = False
        self._connection_task: Optional[asyncio.Task] = None
        self._retry_count = 0

    async def connect(self):
        """Start the persistent connection with auto-reconnect."""
        if self._running:
            logger.warning("Client already running")
            return

        self._running = True
        self._retry_count = 0
        self._connection_task = asyncio.create_task(self._connection_loop())

    async def close(self):
        """Close the connection and stop reconnection attempts."""
        self._running = False

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
            self._connection_task = None

    async def send_text(self, message: str):
        """
        Send text message (typically JSON).

        Args:
            message: Text string to send

        Raises:
            RuntimeError: If not connected
        """
        if not self._ws:
            raise RuntimeError("Not connected to WebSocket server")

        await self._ws.send(message)

    async def send_binary(self, data: bytes):
        """
        Send binary message.

        Args:
            data: Binary data to send

        Raises:
            RuntimeError: If not connected
        """
        if not self._ws:
            raise RuntimeError("Not connected to WebSocket server")

        await self._ws.send(data)

    async def _connection_loop(self):
        """
        Main connection loop with auto-reconnect and exponential backoff.
        Runs until close() is called.
        """
        while self._running:
            try:
                # Attempt connection
                async with websockets.connect(self.url) as ws:
                    self._ws = ws
                    self._retry_count = 0  # Reset on successful connect

                    logger.info(f"Connected to {self.url}")

                    # Trigger on_connect callback
                    if self.on_connect:
                        await self._safe_callback(self.on_connect)

                    # Receive loop
                    await self._receive_loop()

            except asyncio.CancelledError:
                logger.info("Connection loop cancelled")
                break

            except Exception as e:
                logger.error(f"Connection error: {e}")

                # Trigger on_disconnect callback
                if self.on_disconnect:
                    await self._safe_callback(self.on_disconnect)

                self._ws = None

                # Check if we should retry
                if not self._running:
                    break

                if self.max_retries > 0 and self._retry_count >= self.max_retries:
                    logger.error(f"Max retries ({self.max_retries}) reached, giving up")
                    self._running = False
                    break

                # Exponential backoff
                delay = self._calculate_retry_delay()
                self._retry_count += 1

                logger.info(
                    f"Reconnecting in {delay:.1f}s (attempt {self._retry_count})..."
                )
                await asyncio.sleep(delay)

    async def _receive_loop(self):
        """
        Receive messages from WebSocket.
        Runs until connection closes or error occurs.
        """
        try:
            async for message in self._ws:
                if not self._running:
                    break

                # Route message through protocol handler if available
                if self.protocol_handler:
                    if isinstance(message, str):
                        await self.protocol_handler.handle_json_message(message)
                    else:
                        await self.protocol_handler.handle_binary_message(message)

                # Also call on_message callback if provided
                if self.on_message:
                    await self._safe_callback(self.on_message, message)

        except websockets.ConnectionClosed:
            logger.info("Connection closed")
        except Exception as e:
            logger.error(f"Error in receive loop: {e}")

    def _calculate_retry_delay(self) -> float:
        """
        Calculate exponential backoff delay.

        Returns:
            Delay in seconds (capped at max_retry_delay)
        """
        delay = self.initial_retry_delay * (2**self._retry_count)
        return min(delay, self.max_retry_delay)

    async def _safe_callback(self, callback: Callable, *args):
        """
        Execute callback safely, catching and logging exceptions.

        Args:
            callback: Callback function to execute
            *args: Arguments to pass to callback
        """
        try:
            result = callback(*args)
            # Handle async callbacks
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Error in callback {callback.__name__}: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._ws is not None

    @property
    def is_running(self) -> bool:
        """Check if connection loop is running."""
        return self._running
