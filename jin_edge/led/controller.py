"""LED controller for smart speaker visual feedback.

This is a wrapper around the LED daemon client.
The actual LED control runs in a privileged daemon.
"""

import asyncio
import logging

from led.client import LEDClient

logger = logging.getLogger(__name__)


class LEDController:
    """Async LED controller - communicates with privileged daemon."""

    def __init__(self):
        """Initialize the LED controller."""
        self.client = LEDClient()
        logger.info("LED controller initialized (daemon client mode)")

    async def initialize(self):
        """Initialize is a no-op for client mode."""
        pass

    async def set_listening(self):
        """Blue spinning animation when listening/recording."""
        await asyncio.to_thread(self.client.listening)

    async def set_speaking(self):
        """Brighter blue animation while speaking."""
        await asyncio.to_thread(self.client.speaking)

    async def set_thinking(self):
        """Dim blue animation while processing/thinking."""
        await asyncio.to_thread(self.client.thinking)

    async def set_idle(self):
        """Idle state - dim breathing."""
        await asyncio.to_thread(self.client.idle)

    async def set_off(self):
        """Turn off all LEDs."""
        await asyncio.to_thread(self.client.off)

    async def wakeword_detected(self):
        """Blue pulse animation when wake word is detected."""
        await asyncio.to_thread(self.client.listening)

    async def listening(self):
        """Spinning blue animation while listening."""
        await asyncio.to_thread(self.client.listening)

    async def thinking(self):
        """Dim blue animation while processing/thinking."""
        await asyncio.to_thread(self.client.thinking)

    async def speaking(self):
        """Brighter blue animation while speaking."""
        await asyncio.to_thread(self.client.speaking)

    async def idle(self):
        """Idle state - dim breathing."""
        await asyncio.to_thread(self.client.idle)

    async def off(self):
        """Turn off all LEDs."""
        await asyncio.to_thread(self.client.off)

    async def cleanup(self):
        """Cleanup - turn off LEDs."""
        await self.off()
        logger.info("LED controller cleaned up")